"""
Classification functions for comments and instructions.

This module provides functions to assign clinical topic labels to
cleaned text, detect requests for new treatment plans, determine
complexity levels and identify instruction sections. The logic is
based on simple keyword matching using the configuration defined in
analyzer.config.
"""

from typing import Dict, List, Optional

from .config import TOPIC_KEYWORDS, NEW_PLAN_KEYWORDS, CCMOD_COMPLEXITY_THRESHOLDS, CC0_COMPLEXITY_THRESHOLDS
from .text_cleaning import count_sentences, count_lines


def classify_topics(text: str, topic_keywords: Optional[Dict[str, List[str]]] = None) -> List[str]:
    """
    Assign one or more topic labels to a cleaned text based on
    keyword matching.

    Args:
        text: The cleaned text to classify (lower‑casing is applied).
        topic_keywords: Optional Treatment Area Footprint category-to-keywords mapping.

    Returns:
        A list of topic keys (as defined in config.TOPIC_KEYWORDS).
    """
    if not text:
        return []
    text_lower = text.lower()
    topics = []
    keyword_map = topic_keywords if topic_keywords is not None else TOPIC_KEYWORDS
    for topic, keywords in keyword_map.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                topics.append(topic)
                break
    return topics


def detect_new_plan(text: str) -> bool:
    """
    Determine whether the text includes a request for a new treatment plan.

    Args:
        text: The cleaned comment text.

    Returns:
        True if a new plan request is detected, False otherwise.
    """
    if not text:
        return False
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in NEW_PLAN_KEYWORDS)


def determine_ccmod_complexity(length: int, num_topics: int, num_clauses: int) -> str:
    """
    Compute complexity category for CCMod comments.

    Args:
        length: Number of characters in the cleaned comment.
        num_topics: Number of topic labels assigned.
        num_clauses: Number of sentences/clauses detected.

    Returns:
        A complexity category: 'Empty', 'Low', 'Medium' or 'High'.
    """
    if length == 0:
        return "Empty"
    # Low complexity
    low = CCMOD_COMPLEXITY_THRESHOLDS.get("low", {})
    if length <= low.get("max_length", float("inf")) and num_topics <= low.get("max_topics", float("inf")) and num_clauses <= low.get("max_clauses", float("inf")):
        return "Low"
    medium = CCMOD_COMPLEXITY_THRESHOLDS.get("medium", {})
    if length <= medium.get("max_length", float("inf")) and num_topics <= medium.get("max_topics", float("inf")) and num_clauses <= medium.get("max_clauses", float("inf")):
        return "Medium"
    return "High"


def determine_cc0_complexity(length: int, num_topics: int, num_sections: int, num_lines: int) -> str:
    """
    Compute complexity category for CC0 initial instructions.

    Args:
        length: Number of characters in the cleaned instruction.
        num_topics: Number of topic labels assigned.
        num_sections: Number of distinct instruction sections identified.
        num_lines: Number of lines in the cleaned instruction.

    Returns:
        A complexity category: 'Empty', 'Low', 'Medium' or 'High'.
    """
    if length == 0:
        return "Empty"
    low = CC0_COMPLEXITY_THRESHOLDS.get("low", {})
    if length <= low.get("max_length", float("inf")) and num_topics <= low.get("max_topics", float("inf")) and num_sections <= low.get("max_sections", float("inf")) and num_lines <= low.get("max_lines", float("inf")):
        return "Low"
    medium = CC0_COMPLEXITY_THRESHOLDS.get("medium", {})
    if length <= medium.get("max_length", float("inf")) and num_topics <= medium.get("max_topics", float("inf")) and num_sections <= medium.get("max_sections", float("inf")) and num_lines <= medium.get("max_lines", float("inf")):
        return "Medium"
    return "High"


def detect_instruction_sections(original_text: str) -> List[str]:
    """
    Identify which sections of a CC0 instruction are present based on
    bracketed labels. Sections include 'Preferences', 'Upper arch',
    'Lower arch' and 'General form instructions'.

    Args:
        original_text: The full instruction text including labels.

    Returns:
        A list of section names detected.
    """
    sections = []
    text_lower = original_text.lower() if original_text else ""
    if "[preference" in text_lower:
        sections.append("Preferences")
    if "upperarch" in text_lower:
        sections.append("Upper arch")
    if "lowerarch" in text_lower:
        sections.append("Lower arch")
    # If none of the above markers but there is some content, treat as general
    if not sections and text_lower.strip():
        sections.append("General form instructions")
    return sections