"""
Summary text generation for analysis results.

Generates a human‑readable Polish summary based on the metrics and
tables produced by the analysis modules. The summary aims to
reproduce the style of the earlier analyses in this conversation.
"""

from typing import List, Union

import pandas as pd

from .ccmod_analyzer import CCModAnalysisResult
from .cc0_analyzer import CC0AnalysisResult


def _format_top_topics(topic_df: pd.DataFrame, total_rows: int, num_items: int = 3) -> List[str]:
    """
    Format the top topics with counts and percentages.

    Args:
        topic_df: DataFrame with columns [topic, count].
        total_rows: Total number of rows for percentage calculation.
        num_items: Number of top topics to include.

    Returns:
        A list of formatted strings.
    """
    if topic_df.empty or total_rows == 0:
        return []
    lines = []
    for _, row in topic_df.head(num_items).iterrows():
        count = int(row['count'])
        pct = (count / total_rows) * 100 if total_rows else 0
        lines.append(f"- {row['topic']}: {count}, {pct:.1f}%")
    return lines


def generate_ccmod_summary(filename: str, result: CCModAnalysisResult) -> str:
    """
    Create a summary for a CCMod analysis result in Polish.

    Args:
        filename: Name of the analysed file.
        result: The CCModAnalysisResult object.

    Returns:
        A multi‑line string containing the summary.
    """
    lines = []
    lines.append(f"Gotowe, przygotowałem analizę dla pliku {filename}.")
    lines.append("")
    # Section 1: Data scope
    lines.append("1. Zakres danych")
    lines.append(f"- Liczba wierszy: {result.metrics['total_rows']}")
    lines.append(f"- Wiersze po czyszczeniu: {result.metrics['rows_after_cleaning']}")
    lines.append(f"- Średnia długość przed czyszczeniem: {result.metrics['avg_original_length']:.1f} znaków")
    lines.append(f"- Średnia długość po czyszczeniu: {result.metrics['avg_cleaned_length']:.1f} znaków")
    lines.append(f"- Mediana: {result.metrics['median_cleaned']:.1f} znaków")
    lines.append(f"- P90: {result.metrics['p90_cleaned']:.1f} znaków")
    lines.append("")
    # Section 2: Top topics
    lines.append("2. Najczęstsze obszary komentarzy")
    top_topics_lines = _format_top_topics(result.topic_counts, result.metrics['rows_after_cleaning'], num_items=3)
    if top_topics_lines:
        lines.extend(top_topics_lines)
    else:
        lines.append("- Brak wykrytych tematów")
    lines.append("")
    # Section 3: Kompleksowość
    lines.append("3. Kompleksowość")
    for _, row in result.complexity_counts.iterrows():
        lines.append(f"- {row['complexity']}: {int(row['count'])}")
    lines.append("")
    # Additional: Nowy plan leczenia
    new_plan_df = result.new_plan_counts
    new_plan_count = 0
    if not new_plan_df.empty:
        val_true = new_plan_df[new_plan_df['new_plan'] == True]['count']
        new_plan_count = int(val_true.values[0]) if not val_true.empty else 0
    lines.append("4. Dodatkowe informacje")
    lines.append(f"- Liczba próśb o nowy plan leczenia: {new_plan_count}")
    return "\n".join(lines)


def generate_cc0_summary(filename: str, result: CC0AnalysisResult) -> str:
    """
    Create a summary for a CC0 analysis result in Polish.

    Args:
        filename: Name of the analysed file.
        result: The CC0AnalysisResult object.

    Returns:
        A multi‑line summary string.
    """
    lines = []
    lines.append(f"Gotowe, przygotowałem analizę dla pliku {filename}.")
    lines.append("")
    lines.append("1. Zakres danych")
    lines.append(f"- Liczba wierszy: {result.metrics['total_rows']}")
    lines.append(f"- Wiersze po czyszczeniu: {result.metrics['rows_after_cleaning']}")
    lines.append(f"- Średnia długość przed czyszczeniem: {result.metrics['avg_original_length']:.1f} znaków")
    lines.append(f"- Średnia długość po czyszczeniu: {result.metrics['avg_cleaned_length']:.1f} znaków")
    lines.append(f"- Mediana: {result.metrics['median_cleaned']:.1f} znaków")
    lines.append(f"- P90: {result.metrics['p90_cleaned']:.1f} znaków")
    lines.append("")
    lines.append("2. Najczęstsze obszary instrukcji")
    top_topics_lines = _format_top_topics(result.topic_counts, result.metrics['rows_after_cleaning'], num_items=3)
    if top_topics_lines:
        lines.extend(top_topics_lines)
    else:
        lines.append("- Brak wykrytych tematów")
    lines.append("")
    lines.append("3. Kompleksowość")
    for _, row in result.complexity_counts.iterrows():
        lines.append(f"- {row['complexity']}: {int(row['count'])}")
    lines.append("")
    lines.append("4. Najczęstsze sekcje instrukcji")
    for _, row in result.sections_count.head(3).iterrows():
        count = int(row['count'])
        pct = (count / result.metrics['rows_after_cleaning']) * 100 if result.metrics['rows_after_cleaning'] else 0
        lines.append(f"- {row['section']}: {count}, {pct:.1f}%")
    return "\n".join(lines)


def generate_comparison_summary(df: pd.DataFrame) -> str:
    """
    Generate a comparison summary across multiple files.

    Args:
        df: Comparison DataFrame produced by comparison.summarise_results.

    Returns:
        A Polish textual summary.
    """
    if df.empty or len(df) < 2:
        return ""
    lines = []
    # Identify the file with longest comments/instructions
    sorted_df = df.sort_values(by="avg_cleaned_length", ascending=False)
    top = sorted_df.iloc[0]
    bottom = sorted_df.iloc[-1]
    lines.append("Porównanie plików:")
    lines.append(f"- Plik {top['file_name']} ma dłuższe komentarze/instrukcje (średnia {top['avg_cleaned_length']:.1f} znaków) niż plik {bottom['file_name']} (średnia {bottom['avg_cleaned_length']:.1f} znaków).")
    # Identify topic differences (top topic names) by comparing first rows maybe.
    lines.append("- Najczęstszy obszar komentarzy/instrukcji w pliku o najdłuższych tekstach to " + top['top_topics'].split(',')[0] if top['top_topics'] else "")
    return "\n".join(lines)