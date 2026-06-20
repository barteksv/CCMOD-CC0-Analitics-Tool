"""
Excel export utilities for analysis results.

This module defines functions to write analysis tables to Excel
workbooks with consistent styling. Separate functions are provided
for CCMod and CC0 output formats. All workbooks use xlsxwriter as
the engine so that rich formatting can be applied. The caller
should supply a filename for each workbook.
"""

from typing import Optional

import pandas as pd

from .ccmod_analyzer import CCModAnalysisResult
from .cc0_analyzer import CC0AnalysisResult


def _apply_sheet_formatting(writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame, wrap_cols: Optional[list] = None) -> None:
    """
    Apply common formatting to a worksheet.

    Args:
        writer: The ExcelWriter object.
        sheet_name: Name of the worksheet.
        df: DataFrame written to the sheet.
        wrap_cols: List of column indices or names to apply text wrap.
    """
    workbook  = writer.book
    worksheet = writer.sheets[sheet_name]
    # Header format: dark blue fill with white bold font
    header_format = workbook.add_format({
        'bg_color': '#1F4E78',
        'font_color': '#FFFFFF',
        'bold': True,
        'border': 1,
    })
    for col_num, value in enumerate(df.columns.values):
        worksheet.write(0, col_num, value, header_format)
    # Freeze top row
    worksheet.freeze_panes(1, 0)
    # Autofilter
    worksheet.autofilter(0, 0, 0, len(df.columns) - 1)
    # Wrap text for long columns
    if wrap_cols:
        wrap_format = workbook.add_format({'text_wrap': True})
        for col in wrap_cols:
            if isinstance(col, int):
                worksheet.set_column(col, col, 50, wrap_format)
            else:
                idx = df.columns.get_loc(col)
                worksheet.set_column(idx, idx, 50, wrap_format)
    # Default column width
    worksheet.set_column(0, len(df.columns) - 1, 20)


def export_ccmod_to_excel(result: CCModAnalysisResult, filename: str) -> None:
    """
    Export a CCMod analysis result to an Excel workbook.

    Args:
        result: The CCModAnalysisResult to export.
        filename: Path to the output Excel file.
    """
    with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
        # 00 Summary
        summary_data = {
            'Metric': ['Total rows', 'Rows after cleaning', 'Average original length', 'Average cleaned length', 'Median cleaned length', '90th percentile cleaned length'],
            'Value': [
                result.metrics.get('total_rows'),
                result.metrics.get('rows_after_cleaning'),
                round(result.metrics.get('avg_original_length', 0), 2),
                round(result.metrics.get('avg_cleaned_length', 0), 2),
                round(result.metrics.get('median_cleaned', 0), 2),
                round(result.metrics.get('p90_cleaned', 0), 2),
            ],
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='00_Summary', index=False)
        _apply_sheet_formatting(writer, '00_Summary', summary_df)

        # 01 Avg by part and CCMod
        if not result.avg_by_part_and_ccmod.empty:
            result.avg_by_part_and_ccmod.to_excel(writer, sheet_name='01_Avg_by_C_G', index=False)
            _apply_sheet_formatting(writer, '01_Avg_by_C_G', result.avg_by_part_and_ccmod)
        # 02 Avg by part
        if not result.avg_by_part.empty:
            result.avg_by_part.to_excel(writer, sheet_name='02_Avg_by_C', index=False)
            _apply_sheet_formatting(writer, '02_Avg_by_C', result.avg_by_part)
        # 03 Avg by CCMod
        if not result.avg_by_ccmod.empty:
            result.avg_by_ccmod.to_excel(writer, sheet_name='03_Avg_by_G', index=False)
            _apply_sheet_formatting(writer, '03_Avg_by_G', result.avg_by_ccmod)

        # 04 Topic counts
        result.topic_counts.to_excel(writer, sheet_name='04_Topic_counts', index=False)
        _apply_sheet_formatting(writer, '04_Topic_counts', result.topic_counts)

        # 05 Focus counts
        result.focus_counts.to_excel(writer, sheet_name='05_Focus_counts', index=False)
        _apply_sheet_formatting(writer, '05_Focus_counts', result.focus_counts)

        # 06 Complexity counts
        result.complexity_counts.to_excel(writer, sheet_name='06_Complexity', index=False)
        _apply_sheet_formatting(writer, '06_Complexity', result.complexity_counts)

        # 07 Top formulations
        result.top_formulations.to_excel(writer, sheet_name='07_Top_Formulations', index=False)
        _apply_sheet_formatting(writer, '07_Top_Formulations', result.top_formulations, wrap_cols=[0])

        # 08 New plan
        result.new_plan_counts.to_excel(writer, sheet_name='08_New_Plan_Requests', index=False)
        _apply_sheet_formatting(writer, '08_New_Plan_Requests', result.new_plan_counts)

        # 09 Removed phrases audit
        result.removed_phrases_audit.to_excel(writer, sheet_name='09_Removed_Phrases_Audit', index=False)
        _apply_sheet_formatting(writer, '09_Removed_Phrases_Audit', result.removed_phrases_audit, wrap_cols=[0])

        # 10 Row level (may be sample)
        result.row_level.to_excel(writer, sheet_name='10_Row_Level', index=False)
        _apply_sheet_formatting(writer, '10_Row_Level', result.row_level, wrap_cols=[0, 1])


def export_cc0_to_excel(result: CC0AnalysisResult, filename: str) -> None:
    """
    Export a CC0 analysis result to an Excel workbook.

    Args:
        result: The CC0AnalysisResult to export.
        filename: Path to the output Excel file.
    """
    with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
        # Summary sheet
        summary_data = {
            'Metric': ['Total rows', 'Rows after cleaning', 'Average original length', 'Average cleaned length', 'Median cleaned length', '90th percentile cleaned length'],
            'Value': [
                result.metrics.get('total_rows'),
                result.metrics.get('rows_after_cleaning'),
                round(result.metrics.get('avg_original_length', 0), 2),
                round(result.metrics.get('avg_cleaned_length', 0), 2),
                round(result.metrics.get('median_cleaned', 0), 2),
                round(result.metrics.get('p90_cleaned', 0), 2),
            ],
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='00_Overview', index=False)
        _apply_sheet_formatting(writer, '00_Overview', summary_df)

        # Sections count
        result.sections_count.to_excel(writer, sheet_name='01_Sections', index=False)
        _apply_sheet_formatting(writer, '01_Sections', result.sections_count)

        # Topic counts
        result.topic_counts.to_excel(writer, sheet_name='02_Topic_counts', index=False)
        _apply_sheet_formatting(writer, '02_Topic_counts', result.topic_counts)

        # Complexity counts
        result.complexity_counts.to_excel(writer, sheet_name='03_Complexity', index=False)
        _apply_sheet_formatting(writer, '03_Complexity', result.complexity_counts)

        # Top formulations
        result.top_formulations.to_excel(writer, sheet_name='04_Top_Formulations', index=False)
        _apply_sheet_formatting(writer, '04_Top_Formulations', result.top_formulations, wrap_cols=[0])

        # Row level
        result.row_level.to_excel(writer, sheet_name='05_Row_Level', index=False)
        _apply_sheet_formatting(writer, '05_Row_Level', result.row_level, wrap_cols=[0, 1])