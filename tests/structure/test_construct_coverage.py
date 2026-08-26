"""Tests for construct vs coordinate coverage helpers."""

import warnings

import pandas as pd
from biotite.structure.io.pdbx import CIFFile, get_structure

from tests.test_utils import _make_chain, _make_residue
from topos.structure.construct_coverage import (
    CONSTRUCT_SOURCE_COORDINATES,
    CONSTRUCT_SOURCE_POLYMER,
    build_construct_residue_table,
)
from topos.structure.structure_context import ensure_altloc_annotation


def _write_mmcif_with_scheme(path, pdb_id, construct_residues, modeled_mask, chain="A"):
    """Write mmCIF with polymer scheme and atoms only for modeled residues."""
    lines = [
        f"data_{pdb_id}",
        f"_entry.id {pdb_id}",
        "loop_",
        "_atom_site.group_PDB",
        "_atom_site.id",
        "_atom_site.type_symbol",
        "_atom_site.label_atom_id",
        "_atom_site.label_alt_id",
        "_atom_site.label_comp_id",
        "_atom_site.label_asym_id",
        "_atom_site.label_entity_id",
        "_atom_site.label_seq_id",
        "_atom_site.pdbx_PDB_ins_code",
        "_atom_site.Cartn_x",
        "_atom_site.Cartn_y",
        "_atom_site.Cartn_z",
        "_atom_site.occupancy",
        "_atom_site.B_iso_or_equiv",
        "_atom_site.pdbx_formal_charge",
        "_atom_site.auth_seq_id",
        "_atom_site.auth_comp_id",
        "_atom_site.auth_asym_id",
        "_atom_site.auth_atom_id",
        "_atom_site.pdbx_PDB_model_num",
    ]
    atom_id = 1
    for res_idx, (aa, modeled) in enumerate(zip(construct_residues, modeled_mask), start=1):
        if not modeled:
            continue
        residue = _make_residue(aa, res_id=res_idx, chain_id=chain)
        for i in range(len(residue)):
            atom_name = residue.atom_name[i]
            x, y, z = residue.coord[i]
            lines.append(
                f"ATOM  {atom_id:>5} {residue.element[i]:<2} {atom_name:<4} . {aa:<3} "
                f"{chain} 1 {res_idx} . {x:>8.3f} {y:>8.3f} {z:>8.3f} 1.00 20.00 . "
                f"{res_idx} {aa} {chain} {atom_name} 1"
            )
            atom_id += 1

    lines.extend(
        [
            "loop_",
            "_pdbx_poly_seq_scheme.asym_id",
            "_pdbx_poly_seq_scheme.entity_id",
            "_pdbx_poly_seq_scheme.seq_id",
            "_pdbx_poly_seq_scheme.mon_id",
            "_pdbx_poly_seq_scheme.ndb_seq_num",
            "_pdbx_poly_seq_scheme.pdb_seq_num",
            "_pdbx_poly_seq_scheme.auth_seq_num",
            "_pdbx_poly_seq_scheme.pdb_mon_id",
            "_pdbx_poly_seq_scheme.auth_mon_id",
            "_pdbx_poly_seq_scheme.pdb_strand_id",
            "_pdbx_poly_seq_scheme.pdb_ins_code",
            "_pdbx_poly_seq_scheme.hetero",
        ]
    )
    for i, aa in enumerate(construct_residues, start=1):
        modeled = modeled_mask[i - 1]
        pdb_mon = aa if modeled else "?"
        auth_mon = aa if modeled else "?"
        auth_seq_num = str(i) if modeled else "?"
        lines.append(
            f"{chain} 1 {i} {aa} {i} {i} {auth_seq_num} {pdb_mon} {auth_mon} {chain} . n"
        )

    path.write_text("\n".join(lines) + "\n")


def test_build_construct_from_coordinates_fallback():
    arr = _make_chain(["ALA", "CYS", "ASP"], chain_id="A")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        table, source = build_construct_residue_table(arr, cif_file=None)
        assert any("coordinate residues as the construct" in str(x.message) for x in w)

    assert source == CONSTRUCT_SOURCE_COORDINATES
    assert list(table["resn"]) == ["ALA", "CYS", "ASP"]
    assert table["modeled"].all()
    assert list(table["seq_id"]) == [1, 2, 3]


def test_build_construct_from_polymer_scheme(tmp_path):
    cif_path = tmp_path / "scheme.cif"
    construct = ["ALA", "CYS", "ASP", "GLU"]
    modeled = [True, True, False, True]
    _write_mmcif_with_scheme(cif_path, "TEST", construct, modeled)

    cif = CIFFile.read(str(cif_path))
    arr = ensure_altloc_annotation(
        get_structure(cif, model=1, extra_fields=["occupancy"], altloc="occupancy")
    )

    table, source = build_construct_residue_table(arr, cif_file=cif)
    assert source == CONSTRUCT_SOURCE_POLYMER
    assert list(table["resn"]) == construct
    assert list(table["modeled"]) == modeled
    assert list(table.loc[table["modeled"], "resi"]) == [1, 2, 4]
    assert pd.isna(table.loc[~table["modeled"], "resi"]).all()
