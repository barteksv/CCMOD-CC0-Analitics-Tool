"""
Functions for comparing analysis results across multiple files.

This module takes the results of individual CCMod or CC0 analyses
and produces summary tables and comparative metrics useful for
multi‑file reporting. The comparison logic is generic and can
handle both analysis types by introspecting the metrics and
available tables.
"""

from typing import List, Dict, Optional

import pandas as pd

from .ccmod_analyzer import CCModAnalysisResult
from .cc0_analyzer import CC0AnalysisResult


def summarise_results(results: List, file_names: List[str]) -> pd.DataFrame:
    """
    Build a comparison table for multiple analysis results.

    Args:
        results: List of CCModAnalysisResult or CC0AnalysisResult objects.
        file_names: List of original file names corresponding to the results.

    Returns:
        A pandas DataFrame with one row per file summarising key metrics.
    """
    rows = []
    for res, name in zip(results, file_names):
        m = res.metrics
        # Determine type by presence of topic_counts and new_plan_counts
        analysis_type = "CCMod" if hasattr(res, "new_plan_counts") else "CC0"
        # Extract top topics (top 5) if available
        topic_counts = None
        if hasattr(res, "topic_counts"):
            topic_df = res.topic_counts
            # Some results may have 0 topics
            if not topic_df.empty:
                top_topics = ", ".join(
                    f"{row['topic']} ({row['count']})" for _, row in topic_df.head(5).iterrows()
                )
            else:
                top_topics = ""
        else:
            top_topics = ""
        # Complexity distribution summarisation
        complexity_summary = ""
        if hasattr(res, "complexity_counts"):
            compl_df = res.complexity_counts
            if not compl_df.empty:
                complexity_summary = ", ".join(
                    f"{row['complexity']}: {row['count']}" for _, row in compl_df.iterrows()
                )
        # New plan count (only for CCMod)
        new_plan_count = None
        if analysis_type == "CCMod" and hasattr(res, "new_plan_counts"):
            npc_df = res.new_plan_counts
            val_true = npc_df[npc_df["new_plan"] == True]["count"]
            new_plan_count = int(val_true.values[0]) if not val_true.empty else 0
        rows.append(
            {
                "file_name": name,
                "analysis_type": analysis_type,
                "total_rows": m.get("total_rows", 0),
                "rows_after_cleaning": m.get("rows_after_cleaning", 0),
                "avg_cleaned_length": m.get("avg_cleaned_length", 0),
                "median_cleaned": m.get("median_cleaned", 0),
                "p90_cleaned": m.get("p90_cleaned", 0),
                "top_topics": top_topics,
                "complexity_distribution": complexity_summary,
                "new_plan_requests": new_plan_count,
            }
        )
    return pd.DataFrame(rows)