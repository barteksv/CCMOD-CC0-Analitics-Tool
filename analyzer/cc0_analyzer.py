"""
Analysis logic for CC0 initial treatment instructions.

This module implements processing for initial treatment instructions
(CC0) similar to the analysis for CCMod but tailored for the
instruction format. It removes form labels, normalises text,
classifies topics, detects sections and calculates complexity.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from .config import DEFAULT_EXCLUSION_PHRASES, INSTRUCTION_LABELS
from .text_cleaning import (
    normalize_whitespace,
    remove_views,
    remove_phrases,
    remove_instruction_labels,
    exclude_clinical_preferences,
    count_sentences,
    count_lines,
)
from .classifiers import (
    classify_topics,
    determine_cc0_complexity,
    detect_instruction_sections,
)


@dataclass
class CC0AnalysisResult:
    """Container for the outputs of a CC0 analysis."""

    metrics: Dict[str, any]
    sections_count: pd.DataFrame
    topic_counts: pd.DataFrame
    complexity_counts: pd.DataFrame
    top_formulations: pd.DataFrame
    row_level: pd.DataFrame


def analyse_cc0_dataframe(
    df: pd.DataFrame,
    instruction_col: str,
    exclusion_phrases: Optional[List[str]] = None,
    return_row_level: bool = True,
    topic_keywords: Optional[Dict[str, List[str]]] = None,
    exclude_preferences: bool = False,
) -> CC0AnalysisResult:
    """
    Analyse a DataFrame containing CC0 initial instructions.

    Args:
        df: The input DataFrame.
        instruction_col: Column name containing the raw instruction text.
        exclusion_phrases: Additional phrases to exclude from the text.
        return_row_level: Whether to return full row‑level classification.
        topic_keywords: Topic-to-keywords mapping used for Treatment Area Footprint classification.
        exclude_preferences: If True, ignore text from the CC0 preference marker onward.

    Returns:
        A CC0AnalysisResult with aggregated statistics and tables.
    """
    phrases = list(DEFAULT_EXCLUSION_PHRASES)
    if exclusion_phrases:
        phrases.extend(exclusion_phrases)

    rows = []
    # Precompute phrase removal counts for audit if needed later

    for idx, row in df.iterrows():
        original = str(row.get(instruction_col, "") or "")
        analysis_source = exclude_clinical_preferences(original) if exclude_preferences else original
        temp = remove_views(analysis_source)
        # Remove specified phrases (rare in CC0 but kept for consistency)
        temp2, _ = remove_phrases(temp, phrases)
        # Remove instruction labels (e.g. [FormInstructionsUpperArch:])
        temp3, _ = remove_instruction_labels(temp2, INSTRUCTION_LABELS)
        cleaned = normalize_whitespace(temp3)
        cleaned_lower = cleaned.lower()
        # Sections detection based on original text (with labels)
        sections = detect_instruction_sections(analysis_source)
        # Topics detection on cleaned text
        topics = classify_topics(cleaned_lower, topic_keywords=topic_keywords)
        # Complexity
        num_lines = count_lines(temp3)  # count lines after removing labels but before collapsing whitespace
        complexity = determine_cc0_complexity(len(cleaned), len(topics), len(sections), num_lines)
        rows.append({
            "original_instruction": original,
            "cleaned_instruction": cleaned,
            "original_length": len(original),
            "cleaned_length": len(cleaned),
            "sections": ", ".join(sections) if sections else "",
            "sections_list": sections,
            "topics": ", ".join(topics) if topics else "",
            "topics_list": topics,
            "num_lines": num_lines,
            "complexity": complexity,
        })

    row_df = pd.DataFrame(rows)
    total_rows = len(row_df)
    non_empty_rows = (row_df["cleaned_length"] > 0).sum()
    avg_original_length = row_df["original_length"].mean() if total_rows else 0
    avg_cleaned_length = row_df["cleaned_length"].mean() if total_rows else 0
    median_cleaned = row_df["cleaned_length"].median() if total_rows else 0
    p90_cleaned = row_df["cleaned_length"].quantile(0.9) if total_rows else 0

    # Sections count
    sections_flat = [s for secs in row_df["sections_list"] for s in secs] if total_rows else []
    sections_count = pd.Series(sections_flat).value_counts().reset_index()
    sections_count.columns = ["section", "count"]

    # Topic counts
    topics_flat = [t for topics in row_df["topics_list"] for t in topics] if total_rows else []
    topic_counts_series = pd.Series(topics_flat).value_counts().reset_index()
    topic_counts_series.columns = ["topic", "count"]

    # Complexity counts
    complexity_counts = row_df["complexity"].value_counts().reset_index()
    complexity_counts.columns = ["complexity", "count"]

    # Top formulations (cleaned instruction text duplicates)
    top_forms_series = row_df[row_df["cleaned_instruction"].str.strip().astype(bool)]["cleaned_instruction"].value_counts().head(20).reset_index()
    top_forms_series.columns = ["instruction", "count"]

    metrics = {
        "total_rows": int(total_rows),
        "rows_with_instruction": int(total_rows),
        "rows_after_cleaning": int(non_empty_rows),
        "avg_original_length": float(avg_original_length),
        "avg_cleaned_length": float(avg_cleaned_length),
        "median_cleaned": float(median_cleaned),
        "p90_cleaned": float(p90_cleaned),
    }

    return CC0AnalysisResult(
        metrics=metrics,
        sections_count=sections_count,
        topic_counts=topic_counts_series,
        complexity_counts=complexity_counts,
        top_formulations=top_forms_series,
        row_level=row_df if return_row_level else row_df.head(1000),
    )