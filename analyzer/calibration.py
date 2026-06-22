"""Helpers for recalibrating and remembering row-level analysis results.

The Streamlit app lets users manually correct row-level labels after an
analysis has been generated. These helpers rebuild the aggregate tables from
corrected rows and can persist exact-text calibration overrides so future
analyses reuse previously reviewed classifications.
"""

from dataclasses import replace
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from .cc0_analyzer import CC0AnalysisResult
from .ccmod_analyzer import CCModAnalysisResult
from .config import TOPIC_KEYWORDS

CALIBRATION_MEMORY_PATH = Path("data/calibration_memory.json")
MEMORY_VERSION = 3


def split_labels(value: object) -> List[str]:
    """Convert a comma-separated editor value into a clean list of labels."""
    if value is None or pd.isna(value):
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def normalize_memory_text(value: object) -> str:
    """Normalize text used as a stable key for exact calibration memory matches."""
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).lower().split())


def load_calibration_memory(path: Path = CALIBRATION_MEMORY_PATH) -> Dict[str, Any]:
    """Load persisted calibration overrides from disk."""
    if not path.exists():
        return {"version": MEMORY_VERSION, "ccmod": {}, "cc0": {}, "global_rows": {"ccmod": {}, "cc0": {}}, "custom_topics": {}}
    with path.open("r", encoding="utf-8") as handle:
        memory = json.load(handle)
    memory.setdefault("version", MEMORY_VERSION)
    memory.setdefault("ccmod", {})
    memory.setdefault("cc0", {})
    global_rows = memory.setdefault("global_rows", {})
    global_rows.setdefault("ccmod", {})
    global_rows.setdefault("cc0", {})
    memory.setdefault("custom_topics", {})
    return memory


def save_calibration_memory(memory: Dict[str, Any], path: Path = CALIBRATION_MEMORY_PATH) -> None:
    """Persist calibration overrides to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(memory, handle, ensure_ascii=False, indent=2, sort_keys=True)


def get_memory_stats(memory: Dict[str, Any]) -> Dict[str, int]:
    """Return simple counts of learned overrides by analysis mode."""
    return {
        "ccmod": len(memory.get("ccmod", {})),
        "cc0": len(memory.get("cc0", {})),
        "ccmod_global_rows": len(memory.get("global_rows", {}).get("ccmod", {})),
        "cc0_global_rows": len(memory.get("global_rows", {}).get("cc0", {})),
        "custom_topics": len(memory.get("custom_topics", {})),
    }


def get_topic_keywords(memory: Dict[str, Any] | None = None) -> Dict[str, List[str]]:
    """Return built-in and user-learned Treatment Area Footprint keyword rules."""
    topic_keywords = {topic: list(keywords) for topic, keywords in TOPIC_KEYWORDS.items()}
    custom_topics = (memory or {}).get("custom_topics", {})
    for topic, keywords in custom_topics.items():
        cleaned_topic = str(topic).strip()
        if not cleaned_topic:
            continue
        topic_keywords.setdefault(cleaned_topic, [])
        for keyword in keywords or []:
            cleaned_keyword = str(keyword).strip()
            if cleaned_keyword and cleaned_keyword not in topic_keywords[cleaned_topic]:
                topic_keywords[cleaned_topic].append(cleaned_keyword)
    return topic_keywords


def remember_custom_topic(memory: Dict[str, Any], topic: str, keywords: List[str]) -> int:
    """Persist a custom Treatment Area Footprint category and its recognition keywords."""
    cleaned_topic = str(topic).strip()
    cleaned_keywords = []
    for keyword in keywords:
        cleaned_keyword = str(keyword).strip()
        if cleaned_keyword and cleaned_keyword not in cleaned_keywords:
            cleaned_keywords.append(cleaned_keyword)
    if not cleaned_topic or not cleaned_keywords:
        return 0

    memory.setdefault("version", MEMORY_VERSION)
    custom_topics = memory.setdefault("custom_topics", {})
    existing_keywords = custom_topics.setdefault(cleaned_topic, [])
    added = 0
    for keyword in cleaned_keywords:
        if keyword not in existing_keywords:
            existing_keywords.append(keyword)
            added += 1
    return added


def _value_counts(df: pd.DataFrame, column: str, name: str) -> pd.DataFrame:
    counts = df[column].value_counts(dropna=False).reset_index()
    counts.columns = [name, "count"]
    return counts


def _topic_counts(row_df: pd.DataFrame) -> pd.DataFrame:
    topics_flat = [topic for topics in row_df["topics_list"] for topic in topics]
    topic_counts = pd.Series(topics_flat).value_counts().reset_index()
    topic_counts.columns = ["topic", "count"]
    return topic_counts


def recalibrate_ccmod_result(result: CCModAnalysisResult, edited_rows: pd.DataFrame) -> CCModAnalysisResult:
    """Return a CCMod result whose aggregates are rebuilt from edited rows."""
    row_df = edited_rows.copy()
    if "topics" in row_df.columns:
        row_df["topics_list"] = row_df["topics"].apply(split_labels)
    elif "topics_list" not in row_df.columns:
        row_df["topics_list"] = [[] for _ in range(len(row_df))]

    topic_counts = _topic_counts(row_df)
    focus_counts = _value_counts(row_df, "focus_type", "focus_type") if "focus_type" in row_df.columns else result.focus_counts
    complexity_counts = _value_counts(row_df, "complexity", "complexity") if "complexity" in row_df.columns else result.complexity_counts
    new_plan_counts = _value_counts(row_df, "new_plan_request", "new_plan") if "new_plan_request" in row_df.columns else result.new_plan_counts

    return replace(
        result,
        topic_counts=topic_counts,
        focus_counts=focus_counts,
        complexity_counts=complexity_counts,
        new_plan_counts=new_plan_counts,
        row_level=row_df,
    )


def recalibrate_cc0_result(result: CC0AnalysisResult, edited_rows: pd.DataFrame) -> CC0AnalysisResult:
    """Return a CC0 result whose aggregates are rebuilt from edited rows."""
    row_df = edited_rows.copy()
    if "topics" in row_df.columns:
        row_df["topics_list"] = row_df["topics"].apply(split_labels)
    elif "topics_list" not in row_df.columns:
        row_df["topics_list"] = [[] for _ in range(len(row_df))]
    if "sections" in row_df.columns:
        row_df["sections_list"] = row_df["sections"].apply(split_labels)
    elif "sections_list" not in row_df.columns:
        row_df["sections_list"] = [[] for _ in range(len(row_df))]

    topic_counts = _topic_counts(row_df)

    sections_flat = [section for sections in row_df["sections_list"] for section in sections]
    sections_count = pd.Series(sections_flat).value_counts().reset_index()
    sections_count.columns = ["section", "count"]

    complexity_counts = _value_counts(row_df, "complexity", "complexity") if "complexity" in row_df.columns else result.complexity_counts

    return replace(
        result,
        sections_count=sections_count,
        topic_counts=topic_counts,
        complexity_counts=complexity_counts,
        row_level=row_df,
    )


def _memory_text_column(mode: str) -> str:
    return "cleaned_comment" if mode == "ccmod" else "cleaned_instruction"


def _learned_columns(mode: str) -> List[str]:
    if mode == "ccmod":
        return ["topics", "focus_type", "complexity", "new_plan_request"]
    return ["sections", "topics", "complexity"]


def apply_calibration_memory(result: Any, mode: str, memory: Dict[str, Any]) -> Tuple[Any, int]:
    """Apply remembered exact-text overrides to a result and rebuild aggregates."""
    if mode not in {"ccmod", "cc0"}:
        return result, 0

    row_df = result.row_level.copy()
    text_col = _memory_text_column(mode)
    if text_col not in row_df.columns:
        return result, 0

    mode_memory = memory.get(mode, {})
    global_row_memory = memory.get("global_rows", {}).get(mode, {})
    applied_keys = set()
    for idx, row in row_df.iterrows():
        key = normalize_memory_text(row.get(text_col))
        overrides = []
        exact_override = mode_memory.get(key)
        row_override = global_row_memory.get(str(idx))
        if exact_override:
            overrides.append(exact_override)
            applied_keys.add(("exact", key))
        if row_override:
            overrides.append(row_override)
            applied_keys.add(("row", str(idx)))
        for override in overrides:
            for column in _learned_columns(mode):
                if column in row_df.columns and column in override:
                    row_df.at[idx, column] = override[column]

    applied = len(applied_keys)

    if mode == "ccmod":
        return recalibrate_ccmod_result(result, row_df), applied
    return recalibrate_cc0_result(result, row_df), applied


def collect_memory_updates(original_rows: pd.DataFrame, edited_rows: pd.DataFrame, mode: str) -> Dict[str, Dict[str, Any]]:
    """Collect changed calibration fields as exact-text memory updates."""
    text_col = _memory_text_column(mode)
    learned_columns = [col for col in _learned_columns(mode) if col in edited_rows.columns]
    if text_col not in original_rows.columns or text_col not in edited_rows.columns:
        return {}

    updates: Dict[str, Dict[str, Any]] = {}
    for idx in edited_rows.index:
        if idx not in original_rows.index:
            continue
        key = normalize_memory_text(edited_rows.at[idx, text_col])
        if not key:
            continue
        changed = False
        payload: Dict[str, Any] = {}
        for column in learned_columns:
            edited_value = edited_rows.at[idx, column]
            original_value = original_rows.at[idx, column] if column in original_rows.columns else None
            payload[column] = _json_safe_value(edited_value)
            if _json_safe_value(edited_value) != _json_safe_value(original_value):
                changed = True
        if changed:
            updates[key] = payload
    return updates


def collect_global_row_updates(original_rows: pd.DataFrame, edited_rows: pd.DataFrame, mode: str) -> Dict[str, Dict[str, Any]]:
    """Collect changed row-position overrides that apply to every future file in a mode."""
    learned_columns = [col for col in _learned_columns(mode) if col in edited_rows.columns]
    updates: Dict[str, Dict[str, Any]] = {}
    for idx in edited_rows.index:
        if idx not in original_rows.index:
            continue
        changed = False
        payload: Dict[str, Any] = {}
        for column in learned_columns:
            edited_value = edited_rows.at[idx, column]
            original_value = original_rows.at[idx, column] if column in original_rows.columns else None
            payload[column] = _json_safe_value(edited_value)
            if _json_safe_value(edited_value) != _json_safe_value(original_value):
                changed = True
        if changed:
            updates[str(idx)] = payload
    return updates


def remember_calibration_updates(
    memory: Dict[str, Any],
    mode: str,
    updates: Dict[str, Dict[str, Any]],
    global_row_updates: Dict[str, Dict[str, Any]] | None = None,
) -> int:
    """Merge calibration updates into memory and return the number of saved rules."""
    if mode not in {"ccmod", "cc0"}:
        return 0
    memory.setdefault("version", MEMORY_VERSION)
    if updates:
        mode_memory = memory.setdefault(mode, {})
        mode_memory.update(updates)
    if global_row_updates:
        global_rows = memory.setdefault("global_rows", {}).setdefault(mode, {})
        global_rows.update(global_row_updates)
    return max(len(updates), len(global_row_updates or {}))


def _json_safe_value(value: object) -> Any:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value
