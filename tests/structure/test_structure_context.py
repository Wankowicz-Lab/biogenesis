"""Tests for structure loading utilities."""

import warnings

import biotite.structure as struc
import numpy as np
import pandas as pd
import pytest

from topos.structure.structure_context import (
    download_alphafold_pdb,
    drop_duplicate_residue_keys,
    load_structure,
    residue_table,
)
from tests.test_utils import _make_chain, _make_residue, _write_mmcif_file


def test_residue_table_altloc():
    """Test that residue_table properly captures altloc information."""
    # Create chain with mixed altloc identifiers
    aa_list = ['ALA', 'CYS', 'ASP', 'GLU']
    altlocs = ['A', '', 'B', '']
    arr = _make_chain(aa_list=aa_list, chain_id='A', altloc=altlocs)
    
    res_table = residue_table(arr)
    
    # Check that altloc column exists
    assert 'altloc' in res_table.columns
    
    # Check that altloc values are correct
    assert res_table['altloc'].iloc[0] == 'A'
    assert res_table['altloc'].iloc[1] == ''
    assert res_table['altloc'].iloc[2] == 'B'
    assert res_table['altloc'].iloc[3] == ''
    
    # Check other columns are correct
    assert list(res_table['resn']) == ['ALA', 'CYS', 'ASP', 'GLU']
    assert list(res_table['resi']) == [1, 2, 3, 4]
    assert all(res_table['chain'] == 'A')


def test_residue_table_warns_and_drops_duplicate_chain_resi_resn():
    """Insertion-code collisions share (chain, resi, resn); warn then keep last."""
    # Fab-like case: same author resi/resn, distinct ins_code (100A vs 100E).
    r1 = _make_residue("SER", res_id=100, chain_id="H")
    r2 = _make_residue("SER", res_id=100, chain_id="H")
    r2.coord = r2.coord + np.array([10.0, 0.0, 0.0])
    r1.ins_code[:] = "A"
    r2.ins_code[:] = "E"
    arr = struc.concatenate([r1, r2])

    with pytest.warns(UserWarning, match="Duplicate residue keys in residue_table creation"):
        table = residue_table(arr)

    assert len(table) == 1
    assert not table.duplicated(subset=["chain", "resi", "resn"]).any()


def test_drop_duplicate_residue_keys_no_warning_when_unique():
    df = pd.DataFrame(
        {"chain": ["A", "A"], "resi": [1, 2], "resn": ["ALA", "GLY"]}
    )
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        out = drop_duplicate_residue_keys(df, ["chain", "resi", "resn"], context="test")
    assert not any(issubclass(w.category, UserWarning) for w in recorded)
    assert len(out) == 2


def test_drop_duplicate_residue_keys_keeps_last():
    df = pd.DataFrame(
        {
            "chain": ["A", "A", "A"],
            "resi": [1, 1, 2],
            "resn": ["ALA", "ALA", "GLY"],
            "value": [10, 20, 30],
        }
    )
    with pytest.warns(UserWarning, match="Duplicate residue keys in test"):
        out = drop_duplicate_residue_keys(df, ["chain", "resi", "resn"], context="test")
    assert len(out) == 2
    assert list(out["value"]) == [20, 30]


def test_drop_duplicate_residue_keys_ignores_incomplete_keys():
    """Null structure keys on mutation-only rows must not collapse distinct positions."""
    df = pd.DataFrame(
        {
            "chain": ["A", "A", "A"],
            "resi_struct": [pd.NA, pd.NA, 10],
            "resn_struct": ["ASP", "ASP", "ALA"],
            "resm": ["ALA", "ALA", "GLY"],
            "resi_mut": [2, 3, 10],
        }
    )
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        out = drop_duplicate_residue_keys(
            df, ["chain", "resi_struct", "resn_struct", "resm"], context="test"
        )
    assert not any(issubclass(w.category, UserWarning) for w in recorded)
    assert len(out) == 3


def test_load_structure_from_pdb_id():
    """Test loading structure from PDB ID by fetching from RCSB."""
    pdb_id = '8smv'
    
    arr, cif = load_structure(pdb_id=pdb_id)
    
    assert arr is not None
    assert arr.array_length() > 0
    assert cif is not None


def test_load_structure_pdb_format(tmp_path):
    """Test loading structure with PDB format (not just CIF)."""
    # Create a simple PDB file
    residues = ['ALA', 'VAL', 'GLY', 'SER', 'THR']
    pdb_path = tmp_path / "test_structure.pdb"
    
    # Write a minimal valid PDB file
    pdb_content = []
    atom_id = 1
    for res_idx, res_name in enumerate(residues, start=1):
        # Add backbone atoms for each residue
        for atom_name in ['N', 'CA', 'C', 'O']:
            x, y, z = float(atom_id), 0.0, 0.0
            pdb_content.append(
                f"ATOM  {atom_id:5d}  {atom_name:4s}{res_name:3s} A{res_idx:4d}    "
                f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           {atom_name[0]:>2s}\n"
            )
            atom_id += 1
    pdb_content.append("END\n")
    
    with pdb_path.open("w") as f:
        f.writelines(pdb_content)
    
    # Test loading PDB format
    arr, cif = load_structure(path=pdb_path)
    
    assert arr is not None
    assert arr.array_length() > 0
    assert cif is None


def test_load_structure_cif_format(tmp_path):
    """Test loading structure with CIF format to verify extension handling."""
    residues = ['ALA', 'VAL', 'GLY', 'SER', 'THR']
    cif_path = tmp_path / "test_structure.cif"
    _write_mmcif_file(file_path=cif_path, pdb_id="TEST", chains={"A": residues})
    
    arr, cif = load_structure(path=cif_path)
    
    assert arr is not None
    assert arr.array_length() > 0
    assert cif is not None


def test_load_structure_altloc_policy():
    """Test loading structure with altloc policy."""

    arr_altloc_all, _ = load_structure(pdb_id='5C1M', altloc_policy='all')
    assert set(np.unique(arr_altloc_all.altloc_id)) == {'.', 'A', 'B'}

    arr_altloc_highest, _ = load_structure(pdb_id='5C1M', altloc_policy='highest')
    assert len(arr_altloc_highest) < len(arr_altloc_all)


def test_download_alphafold_pdb(tmp_path):
    """Test downloading an AlphaFold PDB from the live AlphaFold API."""
    out_path = download_alphafold_pdb("P00533", out_dir=tmp_path)

    assert out_path == tmp_path / "P00533_alphafold.pdb"
    assert out_path.exists()
    assert out_path.stat().st_size > 0
    assert b"ATOM" in out_path.read_bytes()


def test_download_alphafold_pdb_invalid_uniprot_id(tmp_path):
    """Test AlphaFold helper failure for an invalid UniProt accession."""
    with pytest.raises(RuntimeError, match="Failed to fetch AlphaFold metadata for NOT_A_REAL_UNIPROT_ID"):
        download_alphafold_pdb("NOT_A_REAL_UNIPROT_ID", out_dir=tmp_path)
