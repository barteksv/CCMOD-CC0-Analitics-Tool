"""
I/O utilities for loading and inspecting Excel files.

This module provides helper functions for reading Excel workbooks
into pandas data frames and for detecting which columns contain
clinical comments, case type information and CCMod numbers. It
supports auto-detection based on column names as well as
falling back to Excel column letters if necessary.
"""

from typing import Optional, Tuple

import pandas as pd


def load_excel(file_path: str) -> pd.DataFrame:
    """
    Load an Excel file into a pandas DataFrame.

    The first sheet of the workbook is read. The caller is
    responsible for cleaning up NaN values.

    Args:
        file_path: Path to the Excel file.

    Returns:
        A pandas DataFrame containing the contents of the first sheet.
    """
    # Use engine='openpyxl' explicitly to avoid warnings.
    return pd.read_excel(file_path, sheet_name=0, engine="openpyxl")


def detect_ccmod_columns(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Detect the relevant columns for CCMod comment analysis.

    This function looks for candidate column names in a priority order.
    If a matching column is found (case-insensitive), it returns
    the actual column name from the DataFrame.

    The detection logic is:
      * Comment column candidates: 'COMMENT', 'Comment', 'comment', 'H'
      * Case type (part category) candidates: 'part_category', 'Case Type', 'case_type', 'C'
      * CCMod number candidates: 'CCMod number', 'CCMod', 'ccmod_number', 'G'

    Args:
        df: The DataFrame to inspect.

    Returns:
        A tuple of (comment_column, part_category_column, ccmod_number_column).
        If a column is not found, the corresponding entry will be None.
    """
    col_names = [c for c in df.columns]
    # Lower-case to allow case-insensitive comparison
    lower_names = {c.lower(): c for c in col_names}

    # Candidate priority lists
    comment_candidates = ["comment", "h"]
    part_candidates = ["part_category", "case type", "case_type", "c"]
    ccmod_candidates = ["ccmod number", "ccmod", "ccmod_number", "g"]

    comment_col = None
    for cand in comment_candidates:
        if cand.lower() in lower_names:
            comment_col = lower_names[cand.lower()]
            break

    part_col = None
    for cand in part_candidates:
        if cand.lower() in lower_names:
            part_col = lower_names[cand.lower()]
            break

    ccmod_col = None
    for cand in ccmod_candidates:
        if cand.lower() in lower_names:
            ccmod_col = lower_names[cand.lower()]
            break

    return comment_col, part_col, ccmod_col


def detect_cc0_instruction_column(df: pd.DataFrame) -> Optional[str]:
    """
    Detect the instruction column for CC0 initial instruction files.

    Candidate column names, in order of priority:
        'Instruction', 'instruction', 'Instructions', 'E'

    Args:
        df: The DataFrame to inspect.

    Returns:
        The name of the instruction column, or None if not found.
    """
    col_names = [c for c in df.columns]
    lower_names = {c.lower(): c for c in col_names}
    candidates = ["instruction", "instructions", "e"]
    for cand in candidates:
        if cand.lower() in lower_names:
            return lower_names[cand.lower()]
    return None


def detect_analysis_mode(df: pd.DataFrame) -> str:
    """
    Determine the likely analysis mode (ccmod or cc0) for a DataFrame.

    This heuristically checks for the presence of expected columns. If
    comment and CCMod columns are present, returns 'ccmod'. If only
    instruction column is present, returns 'cc0'. Otherwise returns
    'unknown'.

    Args:
        df: The DataFrame to analyze.

    Returns:
        A string 'ccmod', 'cc0' or 'unknown'.
    """
    comment_col, part_col, ccmod_col = detect_ccmod_columns(df)
    instr_col = detect_cc0_instruction_column(df)
    has_comment = comment_col is not None
    has_ccmod = ccmod_col is not None
    has_instr = instr_col is not None
    if has_comment and has_ccmod:
        return "ccmod"
    if has_instr and not has_comment:
        return "cc0"
    return "unknown"