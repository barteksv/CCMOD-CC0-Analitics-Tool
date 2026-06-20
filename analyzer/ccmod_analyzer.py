"""
Analysis logic for CCMod doctor comments.

This module implements the end‑to‑end processing pipeline for CCMod
comments. It cleans raw comment text, removes boilerplate phrases,
classifies clinical topics, detects requests for new treatment plans,
calculates comment lengths, assesses complexity, and aggregates
statistics by case type and CCMod number. The results can then be
exported to Excel or summarised for display in the Streamlit app.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .config import DEFAULT_EXCLUSION_PHRASES
from .text_cleaning import (
    normalize_whitespace,
    remove_views,
    remove_phrases,
    count_sentences,
)
from .classifiers import (
    classify_topics,
    detect_new_plan,
    determine_ccmod_complexity,
)

# Regular expressions needed for phrase audit.
import re


@dataclass
class CCModAnalysisResult:
    """Container for the outputs of a CCMod analysis."""

    metrics: Dict[str, any]
    avg_by_part_and_ccmod: pd.DataFrame
    avg_by_part: pd.DataFrame
    avg_by_ccmod: pd.DataFrame
    topic_counts: pd.DataFrame
    complexity_counts: pd.DataFrame
    focus_counts: pd.DataFrame
    top_formulations: pd.DataFrame
    new_plan_counts: pd.DataFrame
    removed_phrases_audit: pd.DataFrame
    row_level: pd.DataFrame


def classify_focus(topics: List[str], new_plan: bool) -> str:
    """
    Determine the focus type for a comment based on topics and new plan flag.

    The categories are mutually exclusive and evaluated in a specific order.

    Args:
        topics: List of topic keys.
        new_plan: True if a new treatment plan request was detected.

    Returns:
        A string representing the focus category.
    """
    if new_plan:
        return "New treatment plan request"
    if not topics:
        return "No clear treatment keyword"
    # Only attachments
    if topics == ["attachments"]:
        return "Only attachments"
    # Attachments + other
    if "attachments" in topics:
        return "Attachments + other topics"
    # Only IPR
    if topics == ["ipr"]:
        return "Only IPR / separation / spacing"
    # IPR + other
    if "ipr" in topics:
        return "IPR / separation + other topics"
    # Only movements
    if topics == ["movements"]:
        return "Only tooth movements / alignment"
    if "movements" in topics:
        return "Movements + other topics"
    # Only staging
    if topics == ["staging"]:
        return "Only staging / aligner count"
    # Only occlusion
    if topics == ["occlusion"]:
        return "Occlusion / bite / contacts"
    # Multi‑topic catch‑all
    return "Multi-topic comment"


def analyse_ccmod_dataframe(
    df: pd.DataFrame,
    comment_col: str,
    part_col: Optional[str],
    ccmod_col: Optional[str],
    exclusion_phrases: Optional[List[str]] = None,
    return_row_level: bool = True,
) -> CCModAnalysisResult:
    """
    Analyse a DataFrame containing CCMod comments.

    Args:
        df: The input DataFrame.
        comment_col: Column name containing the raw comment text.
        part_col: Column name for part category (may be None).
        ccmod_col: Column name for CCMod number (may be None).
        exclusion_phrases: Additional phrases to exclude from comments.
        return_row_level: Whether to return the full row‑level classification.

    Returns:
        A CCModAnalysisResult with aggregated statistics and tables.
    """
    # Combine default and user‑provided exclusion phrases
    phrases = list(DEFAULT_EXCLUSION_PHRASES)
    if exclusion_phrases:
        phrases.extend(exclusion_phrases)

    # Prepare containers
    removed_audit = []  # list of (phrase, count)
    row_records = []

    # Precompute phrase removal counts for audit
    phrase_counter = Counter()

    # Iterate over each comment
    for idx, row in df.iterrows():
        original = str(row.get(comment_col, "") or "")
        # Remove view markers
        temp = remove_views(original)
        # Remove phrases
        temp2, removed_count = remove_phrases(temp, phrases)
        # Track removal counts per phrase
        # Actually remove_phrases returns total removed occurrences across
        # all phrases; update phrase_counter accordingly
        # We'll recalc later for audit
        # Normalise whitespace
        cleaned = normalize_whitespace(temp2)
        cleaned_lower = cleaned.lower()
        # Classify topics
        topics = classify_topics(cleaned_lower)
        # New plan detection
        new_plan = detect_new_plan(cleaned_lower)
        # Clause count
        clauses = count_sentences(cleaned)
        # Complexity
        complexity = determine_ccmod_complexity(len(cleaned), len(topics), clauses)
        # Focus type
        focus = classify_focus(topics, new_plan)
        # Record row‑level data
        row_records.append(
            {
                "original_comment": original,
                "cleaned_comment": cleaned,
                "original_length": len(original),
                "cleaned_length": len(cleaned),
                "part_category": row.get(part_col) if part_col else None,
                "ccmod_number": row.get(ccmod_col) if ccmod_col else None,
                "topics": ", ".join(topics) if topics else "",
                "topics_list": topics,
                "new_plan_request": new_plan,
                "complexity": complexity,
                "focus_type": focus,
                "clauses": clauses,
            }
        )
    # Create DataFrame
    row_df = pd.DataFrame(row_records)

    # Audit removed phrases counts: we count across cleaned comments how many times each phrase appears in original. Because we didn't count per phrase while cleaning, we now scan original comments for phrase occurrences.
    for phrase in phrases:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        total_occurrences = row_df["original_comment"].str.count(pattern).sum()
        phrase_counter[phrase] = total_occurrences

    # Compute metrics
    total_rows = len(row_df)
    non_empty_rows = (row_df["cleaned_length"] > 0).sum()
    avg_original_length = row_df["original_length"].mean() if total_rows else 0
    avg_cleaned_length = row_df["cleaned_length"].mean() if total_rows else 0
    median_cleaned = row_df["cleaned_length"].median() if total_rows else 0
    p90_cleaned = row_df["cleaned_length"].quantile(0.9) if total_rows else 0

    # Compute averages by part and ccmod
    def _compute_group_avg(df: pd.DataFrame, group_cols: List[str], label_cols: List[str]) -> pd.DataFrame:
        if not group_cols:
            return pd.DataFrame()
        grp = df.groupby(group_cols)["cleaned_length"].mean().reset_index()
        grp.rename(columns={"cleaned_length": "avg_cleaned_length"}, inplace=True)
        return grp

    avg_by_part_and_ccmod = pd.DataFrame()
    avg_by_part = pd.DataFrame()
    avg_by_ccmod = pd.DataFrame()
    if part_col and ccmod_col:
        avg_by_part_and_ccmod = row_df.groupby(["part_category", "ccmod_number"]) ["cleaned_length"].mean().reset_index().rename(columns={"cleaned_length": "avg_cleaned_length"})
    if part_col:
        avg_by_part = row_df.groupby(["part_category"]) ["cleaned_length"].mean().reset_index().rename(columns={"cleaned_length": "avg_cleaned_length"})
    if ccmod_col:
        avg_by_ccmod = row_df.groupby(["ccmod_number"]) ["cleaned_length"].mean().reset_index().rename(columns={"cleaned_length": "avg_cleaned_length"})

    # Topic counts
    all_topics_flat = [t for topics in row_df["topics_list"] for t in topics]
    topic_counts_series = pd.Series(all_topics_flat).value_counts().reset_index()
    topic_counts_series.columns = ["topic", "count"]
    topic_counts = topic_counts_series.copy()

    # Complexity counts
    complexity_counts = row_df["complexity"].value_counts().reset_index()
    complexity_counts.columns = ["complexity", "count"]

    # Focus counts
    focus_counts = row_df["focus_type"].value_counts().reset_index()
    focus_counts.columns = ["focus_type", "count"]

    # Top formulations: count identical cleaned comments (non-empty)
    top_forms_series = row_df[row_df["cleaned_comment"].str.strip().astype(bool)]["cleaned_comment"].value_counts().head(20).reset_index()
    top_forms_series.columns = ["comment", "count"]

    # New plan counts
    new_plan_counts = row_df["new_plan_request"].value_counts().reset_index()
    new_plan_counts.columns = ["new_plan", "count"]

    # Removed phrases audit DataFrame
    removed_audit_df = pd.DataFrame.from_dict(phrase_counter, orient="index", columns=["removed_count"]).reset_index()
    removed_audit_df.columns = ["phrase", "removed_count"]
    removed_audit_df.sort_values(by="removed_count", ascending=False, inplace=True)

    # Prepare metrics summary dictionary
    metrics = {
        "total_rows": int(total_rows),
        "rows_with_comment": int(total_rows),  # for ccmod, all rows considered as having a comment
        "rows_after_cleaning": int(non_empty_rows),
        "avg_original_length": float(avg_original_length),
        "avg_cleaned_length": float(avg_cleaned_length),
        "median_cleaned": float(median_cleaned),
        "p90_cleaned": float(p90_cleaned),
    }

    return CCModAnalysisResult(
        metrics=metrics,
        avg_by_part_and_ccmod=avg_by_part_and_ccmod,
        avg_by_part=avg_by_part,
        avg_by_ccmod=avg_by_ccmod,
        topic_counts=topic_counts,
        complexity_counts=complexity_counts,
        focus_counts=focus_counts,
        top_formulations=top_forms_series,
        new_plan_counts=new_plan_counts,
        removed_phrases_audit=removed_audit_df,
        row_level=row_df if return_row_level else row_df.head(1000),
    )