"""
Construct vs coordinate residue coverage from mmCIF polymer scheme.

Builds a uniform construct residue table used as the DMS alignment target.
When ``_pdbx_poly_seq_scheme`` is available, rows are the deposited polymer
(including unmodeled residues). Otherwise the table is the coordinate
amino-acid sequence with all residues marked modeled.
"""
from __future__ import annotations

import logging
import warnings
from typing import Optional

import biotite.structure as struc
import numpy as np
import pandas as pd
from biotite.structure.io.pdbx import CIFFile

logger = logging.getLogger(__name__)

CONSTRUCT_SOURCE_POLYMER = "polymer_scheme"
CONSTRUCT_SOURCE_COORDINATES = "coordinates"
# Catalog SS label for construct residues without coordinates (not a real domain)
UNMODELED_SS_LABEL = "unmodeled"

_MISSING = frozenset({"?", ".", ""})


def _normalize_ins_code(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    text = str(value).strip()
    if text in _MISSING:
        return ""
    return text


def _parse_auth_seq(value):
    if value is None:
        return pd.NA
    text = str(value).strip()
    if text in _MISSING:
        return pd.NA
    return int(text)


def _atom_residue_keys(atom_array: struc.AtomArray) -> set[tuple]:
    """Return (chain, resi, ins_code) keys for amino-acid residues with coordinates."""
    aa = atom_array[struc.filter_amino_acids(atom_array)]
    starts = struc.get_residue_starts(aa)
    chains = aa.chain_id[starts]
    resis = aa.res_id[starts]
    if "ins_code" in aa.get_annotation_categories():
        inscodes = [_normalize_ins_code(v) for v in aa.ins_code[starts]]
    else:
        inscodes = [""] * len(starts)
    return {(str(c), int(r), ic) for c, r, ic in zip(chains, resis, inscodes)}


def _coordinates_construct_table(atom_array: struc.AtomArray) -> pd.DataFrame:
    """Build construct rows from modeled amino acids only (all modeled=True)."""
    aa = atom_array[struc.filter_amino_acids(atom_array)]
    starts = struc.get_residue_starts(aa)
    chains = [str(c) for c in aa.chain_id[starts]]
    resis = [int(r) for r in aa.res_id[starts]]
    resns = [str(n) for n in aa.res_name[starts]]
    if "ins_code" in aa.get_annotation_categories():
        inscodes = [_normalize_ins_code(v) for v in aa.ins_code[starts]]
    else:
        inscodes = [""] * len(starts)

    df = pd.DataFrame(
        {
            "chain": chains,
            "resi": resis,
            "ins_code": inscodes,
            "resn": resns,
            "modeled": True,
        }
    )
    # Sequential construct index within each chain in structure order
    df["seq_id"] = df.groupby("chain", sort=False).cumcount() + 1
    return df[["chain", "seq_id", "resi", "ins_code", "resn", "modeled"]]


def _scheme_construct_table(cif_file: CIFFile) -> Optional[pd.DataFrame]:
    """Parse ``_pdbx_poly_seq_scheme`` into construct rows, or None if unavailable."""
    block = cif_file.block
    if "pdbx_poly_seq_scheme" not in block:
        return None

    cat = block["pdbx_poly_seq_scheme"]
    n = cat["pdb_strand_id"].as_array(str).shape[0]
    if n == 0:
        return None

    chains = [str(c) for c in cat["pdb_strand_id"].as_array(str)]
    seq_ids = [int(s) for s in cat["seq_id"].as_array(str)]
    resns = [str(m) for m in cat["mon_id"].as_array(str)]
    resis = [_parse_auth_seq(v) for v in cat["auth_seq_num"].as_array(str)]
    if "pdb_ins_code" in cat:
        inscodes = [_normalize_ins_code(v) for v in cat["pdb_ins_code"].as_array(str)]
    else:
        inscodes = [""] * n

    df = pd.DataFrame(
        {
            "chain": chains,
            "seq_id": seq_ids,
            "resi": resis,
            "ins_code": inscodes,
            "resn": resns,
        }
    )
    # Drop non-standard placeholders if present; keep standard polymer residues
    df = df[df["resn"].notna() & ~df["resn"].isin(_MISSING)].copy()
    if df.empty:
        return None
    return df.reset_index(drop=True)


def _mark_modeled_from_atoms(scheme_df: pd.DataFrame, atom_array: struc.AtomArray) -> pd.DataFrame:
    """Set modeled from presence in the amino-acid AtomArray."""
    keys = _atom_residue_keys(atom_array)
    modeled = []
    for row in scheme_df.itertuples(index=False):
        if pd.isna(row.resi):
            modeled.append(False)
            continue
        modeled.append((str(row.chain), int(row.resi), str(row.ins_code)) in keys)
    out = scheme_df.copy()
    out["modeled"] = modeled
    return out


def _crosscheck_scheme_vs_atoms(construct_df: pd.DataFrame, atom_array: struc.AtomArray) -> None:
    """Log when scheme modeled flags disagree with coordinate residue keys."""
    keys = _atom_residue_keys(atom_array)
    scheme_modeled = set()
    for row in construct_df.itertuples(index=False):
        if row.modeled and not pd.isna(row.resi):
            scheme_modeled.add((str(row.chain), int(row.resi), str(row.ins_code)))
    only_atoms = keys - scheme_modeled
    only_scheme = scheme_modeled - keys
    if only_atoms or only_scheme:
        logger.warning(
            "Construct scheme vs coordinates disagree: %s atom-only residue(s), "
            "%s scheme-modeled residue(s) missing from atoms.",
            len(only_atoms),
            len(only_scheme),
        )


def build_construct_residue_table(
    atom_array: struc.AtomArray,
    cif_file: Optional[CIFFile] = None,
) -> tuple[pd.DataFrame, str]:
    """
    Build a construct residue table and report its source.

    Returns
    -------
    construct_table : pd.DataFrame
        Columns: chain, seq_id, resi, ins_code, resn, modeled.
    construct_source : str
        ``polymer_scheme`` or ``coordinates``.
    """
    if cif_file is not None:
        scheme = _scheme_construct_table(cif_file)
        if scheme is not None:
            construct = _mark_modeled_from_atoms(scheme, atom_array)
            construct = construct[["chain", "seq_id", "resi", "ins_code", "resn", "modeled"]]
            _crosscheck_scheme_vs_atoms(construct, atom_array)
            return construct.reset_index(drop=True), CONSTRUCT_SOURCE_POLYMER

    warnings.warn(
        "mmCIF polymer scheme unavailable; using coordinate residues as the construct. "
        "Unmodeled construct residues cannot be distinguished from residues absent from "
        "the modeled chain. Provide a deposited mmCIF or pdb_id for full construct coverage QC.",
        UserWarning,
    )
    return _coordinates_construct_table(atom_array), CONSTRUCT_SOURCE_COORDINATES
