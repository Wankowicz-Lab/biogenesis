import pandas as pd

from topos.metrics.averaging_metrics import (
    assert_poolable_numeric_columns,
    column_needs_synonym_mask,
    spatial_pool_metric_columns,
)
from topos.metrics.secondary_structure import ss_domain_lengths, ss_domain_log2_aa_group_ratios
from topos.pipeline.context import Context
from topos.structure.construct_coverage import UNMODELED_SS_LABEL


def _is_aggregatable_ss_domain(ss_domains: pd.Series) -> pd.Series:
    """True for real SS domain labels (excludes missing and the unmodeled catalog label)."""
    return ss_domains.notna() & (ss_domains != UNMODELED_SS_LABEL)


def calculate_secondary_structure_features(
    context: Context,
    features: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate residue-level features onto secondary-structure domains.

    Residues labeled ``unmodeled`` keep that catalog value in the output but are
    excluded from domain length / composition aggregations.
    """
    merge_cols = ["chain", "resi_struct", "resn_struct"]

    rt_subset = context.residue_table[merge_cols + ["ss_domains"]].drop_duplicates(merge_cols)
    # Prefer residue_table labels; features may already carry ss_domains from the scaffold
    feature_cols = [c for c in features.columns if c != "ss_domains"]
    merged = pd.merge(features[feature_cols], rt_subset, on=merge_cols, how="left")
    # Catalog label for missing coordinates is not a secondary-structure domain
    merged = merged.loc[_is_aggregatable_ss_domain(merged["ss_domains"])].copy()

    cols_to_avg = [column for column in spatial_pool_metric_columns(features) if column in merged.columns]
    assert_poolable_numeric_columns(cols_to_avg, merged)

    if "type" in merged.columns:
        synonymous_mask = merged["type"].eq("synonymous")
        for column in cols_to_avg:
            if column_needs_synonym_mask(column):
                merged.loc[synonymous_mask, column] = float("nan")

    residue_level_cols = merge_cols + ["ss_domains"] + cols_to_avg
    if cols_to_avg:
        residue_level = merged[residue_level_cols].groupby(
            merge_cols + ["ss_domains"],
            as_index=False,
        ).agg({column: "mean" for column in cols_to_avg})
    else:
        residue_level = merged[merge_cols + ["ss_domains"]].drop_duplicates()

    agg_dict = {column: "mean" for column in cols_to_avg}
    if cols_to_avg:
        by_domain = residue_level.groupby(["chain", "ss_domains"], as_index=False).agg(agg_dict)
    else:
        by_domain = residue_level[["chain", "ss_domains"]].drop_duplicates()
    by_domain = by_domain.rename(columns={column: f"ss_domain_{column}" for column in cols_to_avg})

    lengths = ss_domain_lengths(residue_level)
    by_domain = by_domain.merge(lengths, on=["chain", "ss_domains"], how="left")
    log2_df = ss_domain_log2_aa_group_ratios(residue_level)
    by_domain = by_domain.merge(log2_df, on=["chain", "ss_domains"], how="left")

    # Keep unmodeled rows in the returned scaffold (label only; aggregate cols stay NaN)
    rt_subset = rt_subset.loc[rt_subset["ss_domains"].notna()].copy()
    out = rt_subset.merge(by_domain, on=["chain", "ss_domains"], how="left")
    # ss_domains already lives on the features scaffold; avoid merge suffixes
    return out.drop(columns=["ss_domains"])
