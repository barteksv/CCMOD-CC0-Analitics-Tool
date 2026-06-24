"""
Text cleaning utilities used in CCMod and CC0 analysis.

Functions in this module are responsible for removing boilerplate
phrases, stripping technical form labels, normalising whitespace and
punctuation, and counting clauses or lines for complexity analysis.
"""

import re
from typing import Iterable, List, Tuple


def normalize_whitespace(text: str) -> str:
    """Collapse multiple whitespace characters into a single space and strip."""
    # Replace line breaks and tabs with spaces
    cleaned = re.sub(r"\s+", " ", text)
    return cleaned.strip()


def remove_views(text: str) -> str:
    """
    Remove markers like '{view#0}' that sometimes appear in comments.

    Args:
        text: The original comment text.

    Returns:
        The text with view markers removed.
    """
    return re.sub(r"\{view#\d+\}", "", text, flags=re.IGNORECASE)


def remove_phrases(text: str, phrases: Iterable[str]) -> Tuple[str, int]:
    """
    Remove each phrase from the text in a case-insensitive manner.

    Args:
        text: The original text.
        phrases: An iterable of phrases to remove.

    Returns:
        A tuple of (cleaned_text, total_removed) where total_removed
        indicates how many phrases were removed (not how many characters).
    """
    cleaned = text
    removed_count = 0
    for phrase in phrases:
        # Use regex for case-insensitive replacement. Escape the phrase to
        # avoid interpreting regex metacharacters.
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        # Count occurrences
        occurrences = len(pattern.findall(cleaned))
        if occurrences > 0:
            cleaned = pattern.sub("", cleaned)
            removed_count += occurrences
    return cleaned, removed_count


def remove_instruction_labels(text: str, labels: Iterable[str]) -> Tuple[str, int]:
    """
    Remove instruction labels from CC0 instruction text.

    Args:
        text: The original instruction text.
        labels: An iterable of label strings to remove.

    Returns:
        A tuple of (cleaned_text, total_removed).
    """
    cleaned = text
    removed_count = 0
    for label in labels:
        pattern = re.compile(re.escape(label), re.IGNORECASE)
        occurrences = len(pattern.findall(cleaned))
        if occurrences > 0:
            cleaned = pattern.sub("", cleaned)
            removed_count += occurrences
    return cleaned, removed_count


def exclude_clinical_preferences(text: str) -> str:
    """Return CC0 text before the clinical preference instruction marker.

    The source files may contain a misspelled ``[PreferenceInstrucions:]``
    marker or the corrected ``[PreferenceInstructions:]`` marker. When this
    marker exists, everything from the marker onward is treated as global
    preference boilerplate and omitted from downstream analysis.
    """
    match = re.search(r"\[\s*PreferenceInstruc(?:tions|ions)\s*:\s*\]", str(text), flags=re.IGNORECASE)
    if not match:
        return str(text)
    return str(text)[:match.start()]


def count_sentences(text: str) -> int:
    """
    Roughly count the number of sentences or clauses in a text.
    Splits on punctuation that often ends a sentence or clause.

    Args:
        text: The text to analyse.

    Returns:
        Number of sentences or clauses detected.
    """
    # Define punctuation that may separate sentences/clauses
    separators = r"[\.\!\?;:]"
    # Split and filter out empty parts
    parts = re.split(separators, text)
    non_empty = [p.strip() for p in parts if p.strip()]
    return max(1, len(non_empty)) if non_empty else 0


def count_lines(text: str) -> int:
    """
    Count the number of lines in a text, splitting on newline characters.

    Args:
        text: The text to count lines in.

    Returns:
        Number of non-empty lines.
    """
    lines = text.split("\n")
    non_empty = [l for l in lines if l.strip()]
    return max(1, len(non_empty)) if non_empty else 0