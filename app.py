"""
Streamlit application for analysing Invisalign CCMod comments and CC0 instructions.

This app allows users to upload Excel files containing doctor comments
or instructions, select analysis settings, define custom exclusion
phrases and run analyses. Results are summarised in English, exported
to styled Excel workbooks and made available for download individually
or as a ZIP archive. Multiple files can be processed and compared.
"""

import io
import zipfile
from typing import List, Dict, Any

import pandas as pd
import streamlit as st

from analyzer.io_utils import detect_ccmod_columns, detect_cc0_instruction_column, detect_analysis_mode
from analyzer.ccmod_analyzer import analyse_ccmod_dataframe
from analyzer.cc0_analyzer import analyse_cc0_dataframe
from analyzer.comparison import summarise_results
from analyzer.excel_export import export_ccmod_to_excel, export_cc0_to_excel
from analyzer.summary_generator import generate_ccmod_summary, generate_cc0_summary, generate_comparison_summary
from pages.doctor_pattern_analysis import render_doctor_pattern_analysis
from analyzer.calibration import (
    apply_calibration_memory,
    collect_memory_updates,
    collect_global_row_updates,
    get_memory_stats,
    get_topic_keywords,
    load_calibration_memory,
    recalibrate_cc0_result,
    recalibrate_ccmod_result,
    remember_calibration_updates,
    remember_custom_topic,
    save_calibration_memory,
)



def render_analysis_page_guide() -> None:
    """Render English documentation for the standard CCMod/CC0 analysis page."""
    with st.expander("How this page works and variable legend", expanded=False):
        st.markdown(
            "This page analyzes one or more Excel files as either **CCMod doctor comments** or **CC0 initial instructions**. "
            "The app detects the file type, cleans boilerplate text, classifies treatment topics, estimates complexity, "
            "creates English summaries, and exports Excel workbooks. After the first run, the calibration area lets users "
            "correct row-level classifications and save those corrections as future learning rules."
        )
        st.markdown("**Workflow**")
        st.markdown(
            "1. Upload `.xlsx` files.  \n"
            "2. Choose Auto, CCMod, or CC0 mode.  \n"
            "3. Optionally add custom exclusion phrases and custom Treatment Area Footprint categories.  \n"
            "4. Run the analysis and download individual or ZIP exports.  \n"
            "5. Use Post-analysis calibration when a row needs a corrected topic, focus, complexity, or new-plan flag."
        )
        legend = {
            "Analysis mode": "Auto lets the app infer CCMod versus CC0 from columns; manual modes force a specific pipeline.",
            "Custom exclusion phrases": "User-provided boilerplate phrases removed before classification; enter one phrase per line.",
            "Treatment Area Footprint categories / topics": "Clinical areas detected from keywords, such as attachments, IPR, movements, staging, occlusion, or custom categories.",
            "original_length": "Character count of the source comment or instruction before cleaning.",
            "cleaned_length": "Character count after view markers, labels, and exclusion phrases are removed.",
            "avg_cleaned_length": "Average cleaned text length for a group, used as a rough workload/detail indicator.",
            "median_cleaned": "Middle cleaned-text length; less sensitive to extreme long comments than the average.",
            "p90_cleaned": "90th percentile cleaned-text length; indicates very detailed or complex upper-tail records.",
            "complexity": "Rule-based label (Empty, Low, Medium, High) based on text length, number of topics, sections, lines, or clauses.",
            "focus_type": "CCMod-only summary of the main request type, such as only attachments, IPR + other topics, staging, or multi-topic comment.",
            "new_plan_request": "CCMod-only flag for comments that ask for a new, previous, reposted, or alternative treatment plan.",
            "clauses": "Approximate sentence/clause count in a cleaned CCMod comment.",
            "sections": "CC0 instruction sections detected from source labels, such as upper arch, lower arch, preference, or other.",
            "num_lines": "Number of instruction lines after label removal, before final whitespace collapse.",
            "Calibration memory": "Saved correction rules applied to identical cleaned phrases and matching row positions in future analyses.",
        }
        st.table(pd.DataFrame([{"Variable": k, "Meaning": v} for k, v in legend.items()]))

def parse_custom_phrases(text: str) -> List[str]:
    """Split a multi‑line string into a list of phrases, ignoring empty lines."""
    if not text:
        return []
    return [line.strip() for line in text.split("\n") if line.strip()]



def build_excel_download(result: Any, mode: str) -> bytes:
    """Create an Excel workbook in memory for a CCMod or CC0 result."""
    buffer = io.BytesIO()
    if mode == "ccmod":
        export_ccmod_to_excel(result, buffer)
    elif mode == "cc0":
        export_cc0_to_excel(result, buffer)
    else:
        raise ValueError(f"Unsupported analysis mode: {mode}")
    return buffer.getvalue()


def render_calibration_panel(file_name: str, result: Any, mode: str, topic_keywords: Dict[str, List[str]]) -> Any:
    """Render editable row-level classifications and return a recalibrated result."""
    st.subheader(f"Classification calibration: {file_name}")
    st.caption(
        "Adjust topic categories, focus, complexity, or the new-plan flag for individual rows. "
        "After you edit the table, aggregates and exports are recalculated from your corrections."
    )

    row_df = result.row_level.copy()
    topic_options = sorted(topic_keywords.keys())
    complexity_options = ["Empty", "Low", "Medium", "High"]

    if mode == "ccmod":
        editable_cols = [
            "original_comment", "cleaned_comment", "topics", "focus_type",
            "complexity", "new_plan_request", "clauses", "part_category", "ccmod_number",
        ]
        disabled_cols = [
            col for col in editable_cols
            if col in row_df.columns and col not in {"topics", "focus_type", "complexity", "new_plan_request"}
        ]
        focus_options = sorted(result.focus_counts["focus_type"].dropna().astype(str).unique().tolist() + [
            "New treatment plan request",
            "No clear treatment keyword",
            "Only attachments",
            "Attachments + other topics",
            "Only IPR / separation / spacing",
            "IPR / separation + other topics",
            "Only tooth movements / alignment",
            "Movements + other topics",
            "Only staging / aligner count",
            "Occlusion / bite / contacts",
            "Multi-topic comment",
        ])
        column_config = {
            "topics": st.column_config.TextColumn("Treatment categories (comma-separated)", help=f"Available: {', '.join(topic_options)}"),
            "focus_type": st.column_config.SelectboxColumn("Focus", options=focus_options),
            "complexity": st.column_config.SelectboxColumn("Complexity", options=complexity_options),
            "new_plan_request": st.column_config.CheckboxColumn("New plan?"),
        }
        edited = st.data_editor(
            row_df[[col for col in editable_cols if col in row_df.columns]],
            key=f"calibration_editor_{file_name}",
            use_container_width=True,
            hide_index=False,
            disabled=disabled_cols,
            column_config=column_config,
        )
        return recalibrate_ccmod_result(result, edited)

    editable_cols = [
        "original_instruction", "cleaned_instruction", "sections", "topics",
        "complexity", "num_lines",
    ]
    disabled_cols = [col for col in editable_cols if col in row_df.columns and col not in {"sections", "topics", "complexity"}]
    column_config = {
        "sections": st.column_config.TextColumn("Sections (comma-separated)"),
        "topics": st.column_config.TextColumn("Treatment categories (comma-separated)", help=f"Available: {', '.join(topic_options)}"),
        "complexity": st.column_config.SelectboxColumn("Complexity", options=complexity_options),
    }
    edited = st.data_editor(
        row_df[[col for col in editable_cols if col in row_df.columns]],
        key=f"calibration_editor_{file_name}",
        use_container_width=True,
        hide_index=False,
        disabled=disabled_cols,
        column_config=column_config,
    )
    return recalibrate_cc0_result(result, edited)

def render_existing_analysis():
    """Render the existing CCMod/CC0 analysis workspace."""
    st.header("Existing CCMod/CC0 Analysis")
    st.write(
        "Upload one or more Excel files with comments (CCMod) or initial instructions (CC0) to generate a comprehensive analysis."
    )
    render_analysis_page_guide()

    uploaded_files = st.file_uploader(
        "Select Excel files (.xlsx)", accept_multiple_files=True, type=["xlsx"]
    )
    if not uploaded_files:
        st.info("No files uploaded.")
        return

    calibration_memory = load_calibration_memory()
    memory_stats = get_memory_stats(calibration_memory)
    st.info(
        f"Calibration memory: {memory_stats['ccmod']} CCMod text rules, "
        f"{memory_stats['cc0']} CC0 text rules, "
        f"{memory_stats['ccmod_global_rows']} CCMod global row rules, "
        f"{memory_stats['cc0_global_rows']} CC0 global row rules, "
        f"{memory_stats['custom_topics']} custom Treatment Area Footprint categories. "
        "After saving a Treatment Area Footprint / treatment category correction, the same row position "
        "and the identical cleaned phrase will be calibrated in future analyses regardless of the file name."
    )


    with st.expander("Custom Treatment Area Footprint categories", expanded=False):
        st.caption(
            "Add a new category and the words/phrases the app should use to recognize it "
            "in CCMod and CC0. Phrases will be applied to all future analyses regardless of file name."
        )
        custom_topic_name = st.text_input(
            "New category name",
            key="custom_topic_name",
            placeholder="e.g. posterior_crossbite",
        )
        custom_topic_keywords = st.text_area(
            "Words or phrases that identify the category (one per line)",
            key="custom_topic_keywords",
            height=100,
            placeholder="e.g. crossbite\nposterior crossbite",
        )
        if st.button("Save Treatment Area Footprint category", key="save_custom_topic"):
            memory = load_calibration_memory()
            added_keywords = remember_custom_topic(memory, custom_topic_name, parse_custom_phrases(custom_topic_keywords))
            if added_keywords:
                save_calibration_memory(memory)
                calibration_memory = memory
                st.success(
                    f"Saved category '{custom_topic_name.strip()}' with {added_keywords} new phrases. "
                    "It will be recognized in future analyses."
                )
            else:
                st.warning("Enter a category name and at least one new recognition phrase.")

    topic_keywords = get_topic_keywords(calibration_memory)

    # Analysis mode selection
    analysis_mode = st.selectbox(
        "Select analysis mode",
        ("Auto", "CCMod", "CC0"),
        index=0,
        help="In Auto mode, the app will try to detect the file structure automatically."
    )
    # Language selection (not used in classification but kept for future)
    language = st.selectbox(
        "Select comment/instruction language",
        ("Auto", "French", "Spanish", "English", "Mixed"),
        index=0,
        help="Keyword analysis is language-independent, but you can select the dominant language here."
    )
    # Custom exclusion phrases
    st.write("You can add custom exclusion phrases (one phrase per line):")
    custom_phrases_input = st.text_area("Exclusion phrases", value="", height=150)
    custom_phrases = parse_custom_phrases(custom_phrases_input)
    # Row-level option
    include_full_rows = st.checkbox(
        "Include full row export and calibration for all records (may slow analysis for very large files)", value=True
    )

    if st.button("Run analysis"):
        results = []
        file_names = []
        processed_file_names = []
        downloads: Dict[str, bytes] = {}
        summaries: Dict[str, str] = {}
        result_modes: Dict[str, str] = {}
        for up_file in uploaded_files:
            file_name = up_file.name
            file_names.append(file_name)
            # Save uploaded file to a temporary location in memory as bytes
            bytes_data = up_file.read()
            # Load into DataFrame
            df = pd.read_excel(io.BytesIO(bytes_data), engine="openpyxl")
            # Determine analysis type
            mode = analysis_mode.lower()
            if mode == "auto":
                mode = detect_analysis_mode(df)
                if mode == "unknown":
                    st.error(f"Cannot detect the file format for {file_name}. Make sure it contains the expected columns.")
                    continue
            elif mode == "ccmod":
                # proceed as ccmod
                pass
            elif mode == "cc0":
                # proceed as cc0
                pass
            # Run analysis based on mode
            if mode == "ccmod":
                comment_col, part_col, ccmod_col = detect_ccmod_columns(df)
                if not comment_col or not ccmod_col:
                    st.error(f"File {file_name} does not contain the required comment columns (for example, 'COMMENT' or 'H') and CCMod number (for example, 'CCMod number' or 'G').")
                    continue
                res = analyse_ccmod_dataframe(
                    df,
                    comment_col=comment_col,
                    part_col=part_col,
                    ccmod_col=ccmod_col,
                    exclusion_phrases=custom_phrases,
                    return_row_level=include_full_rows,
                    topic_keywords=topic_keywords,
                )
                res, applied_rules = apply_calibration_memory(res, mode, calibration_memory)
                if applied_rules:
                    st.success(f"Applied {applied_rules} remembered calibrations for {file_name}.")
                results.append(res)
                processed_file_names.append(file_name)
                # Generate Excel file in memory
                downloads[file_name] = build_excel_download(res, mode)
                result_modes[file_name] = mode
                # Generate summary text
                summaries[file_name] = generate_ccmod_summary(file_name, res)
            elif mode == "cc0":
                instr_col = detect_cc0_instruction_column(df)
                if not instr_col:
                    st.error(f"File {file_name} does not contain an instruction column (for example, 'Instruction' or 'E').")
                    continue
                res = analyse_cc0_dataframe(
                    df,
                    instruction_col=instr_col,
                    exclusion_phrases=custom_phrases,
                    return_row_level=include_full_rows,
                    topic_keywords=topic_keywords,
                )
                res, applied_rules = apply_calibration_memory(res, mode, calibration_memory)
                if applied_rules:
                    st.success(f"Applied {applied_rules} remembered calibrations for {file_name}.")
                results.append(res)
                processed_file_names.append(file_name)
                downloads[file_name] = build_excel_download(res, mode)
                result_modes[file_name] = mode
                summaries[file_name] = generate_cc0_summary(file_name, res)
            else:
                st.error(f"Unsupported analysis mode for file {file_name}.")
                continue
        if not results:
            st.warning("No analysis results to display.")
            return
        st.session_state["analysis_results"] = dict(zip(processed_file_names, results))
        st.session_state["analysis_modes"] = result_modes
        # Display summaries and download links per file
        st.header("File summaries")
        for fn in file_names:
            if fn in summaries:
                st.subheader(fn)
                st.markdown(summaries[fn])
                # Provide download button
                file_key = fn + "_download"
                st.download_button(
                    label=f"Download analysis result for {fn}",
                    data=downloads[fn],
                    file_name=f"analysis_{fn}",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=file_key,
                )
        # If multiple files, generate comparison summary and summary file
        if len(results) > 1:
            comp_df = summarise_results(results, processed_file_names)
            comp_summary = generate_comparison_summary(comp_df)
            st.header("Multi-file comparison")
            st.markdown(comp_summary)
            # Show comparison table
            st.dataframe(comp_df)
        # Create a ZIP archive of all outputs
        if downloads:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                for fn, data in downloads.items():
                    zipf.writestr(f"analysis_{fn}", data)
            st.download_button(
                label="Download all results as ZIP",
                data=zip_buffer.getvalue(),
                file_name="analysis_results.zip",
                mime="application/zip",
            )


    if "analysis_results" in st.session_state and st.session_state["analysis_results"]:
        st.header("Post-analysis calibration")
        st.write(
            "After generating the analysis, you can manually correct treatment topic, focus, and complexity assignments. "
            "This helps resolve borderline cases, such as whether a phrase belongs to staging or tooth movements."
        )
        calibrated_results: Dict[str, Any] = {}
        calibrated_downloads: Dict[str, bytes] = {}
        for fn, result in st.session_state["analysis_results"].items():
            mode = st.session_state["analysis_modes"].get(fn)
            with st.expander(f"Calibrate {fn}", expanded=False):
                calibrated = render_calibration_panel(fn, result, mode, topic_keywords)
                updates = collect_memory_updates(result.row_level, calibrated.row_level, mode)
                global_row_updates = collect_global_row_updates(result.row_level, calibrated.row_level, mode)
                update_count = max(len(updates), len(global_row_updates))
                if update_count:
                    st.warning(
                        f"Detected {update_count} new calibration changes. "
                        "Click the button below to permanently remember them for identical texts "
                        "and globally for the same row positions in all new analyses."
                    )
                if st.button(
                    "Save this calibration as learning for the future",
                    key=f"remember_calibration_{fn}",
                    disabled=not bool(updates or global_row_updates),
                ):
                    memory = load_calibration_memory()
                    saved_count = remember_calibration_updates(memory, mode, updates, global_row_updates)
                    save_calibration_memory(memory)
                    st.session_state["analysis_results"][fn] = calibrated
                    for other_fn, other_result in list(st.session_state["analysis_results"].items()):
                        other_mode = st.session_state["analysis_modes"].get(other_fn)
                        if other_mode == mode and other_fn != fn:
                            reapplied, _ = apply_calibration_memory(other_result, other_mode, memory)
                            st.session_state["analysis_results"][other_fn] = reapplied
                    st.success(
                        f"Remembered {saved_count} rules. They will be used in future analyses "
                        "of identical phrases and globally for the same row positions, "
                        "regardless of file name."
                    )
                calibrated_results[fn] = calibrated
                calibrated_downloads[fn] = build_excel_download(calibrated, mode)
                if mode == "ccmod":
                    st.markdown(generate_ccmod_summary(fn, calibrated))
                elif mode == "cc0":
                    st.markdown(generate_cc0_summary(fn, calibrated))
                st.download_button(
                    label=f"Download calibrated result for {fn}",
                    data=calibrated_downloads[fn],
                    file_name=f"calibrated_analysis_{fn}",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"calibrated_download_{fn}",
                )
        if len(calibrated_results) > 1:
            st.subheader("Comparison after calibration")
            calibrated_file_names = list(calibrated_results.keys())
            comp_df = summarise_results(list(calibrated_results.values()), calibrated_file_names)
            st.markdown(generate_comparison_summary(comp_df))
            st.dataframe(comp_df)
        if calibrated_downloads:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                for fn, data in calibrated_downloads.items():
                    zipf.writestr(f"calibrated_analysis_{fn}", data)
            st.download_button(
                label="Download all calibrated results as ZIP",
                data=zip_buffer.getvalue(),
                file_name="calibrated_results.zip",
                mime="application/zip",
                key="calibrated_zip_download",
            )


def main():
    st.set_page_config(page_title="ClinCheck Comment and Instruction Analysis", layout="wide")
    st.title("ClinCheck Comment and Instruction Analysis")

    analysis_tab, doctor_pattern_tab = st.tabs([
        "Existing CCMod/CC0 Analysis",
        "Doctor Pattern Analysis",
    ])

    with analysis_tab:
        render_existing_analysis()
    with doctor_pattern_tab:
        st.expander("Page overview", expanded=False).markdown(
            "Use this page when you have both initial CC0 instructions and later CCMod comments and want to explain repeated, late-emerging, or changed doctor requests. Detailed English help and legends appear inside each results tab after the analysis runs."
        )
        render_doctor_pattern_analysis()


if __name__ == "__main__":
    main()
