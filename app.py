"""
Streamlit application for analysing Invisalign CCMod comments and CC0 instructions.

This app allows users to upload Excel files containing doctor comments
or instructions, select analysis settings, define custom exclusion
phrases and run analyses. Results are summarised in Polish, exported
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
    st.subheader(f"Kalibracja klasyfikacji: {file_name}")
    st.caption(
        "Popraw kategorie tematów, focus, złożoność lub flagę new plan na poziomie pojedynczych wierszy. "
        "Po zmianie tabel agregaty i eksport są przeliczane na podstawie Twoich korekt."
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
            "topics": st.column_config.TextColumn("Treatment categories (comma-separated)", help=f"Dostępne: {', '.join(topic_options)}"),
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
        "topics": st.column_config.TextColumn("Treatment categories (comma-separated)", help=f"Dostępne: {', '.join(topic_options)}"),
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

def main():
    st.set_page_config(page_title="Analiza komentarzy i instrukcji ClinCheck", layout="wide")
    st.title("Analiza komentarzy i instrukcji ClinCheck")
    st.write(
        "Wgraj jeden lub kilka plików Excel z komentarzami (CCMod) lub instrukcjami inicjalnymi (CC0) i uzyskaj kompleksową analizę."
    )

    uploaded_files = st.file_uploader(
        "Wybierz pliki Excel (.xlsx)", accept_multiple_files=True, type=["xlsx"]
    )
    if not uploaded_files:
        st.info("Nie wgrano plików.")
        return

    calibration_memory = load_calibration_memory()
    memory_stats = get_memory_stats(calibration_memory)
    st.info(
        f"Pamięć kalibracji: {memory_stats['ccmod']} reguł tekstowych CCMod, "
        f"{memory_stats['cc0']} reguł tekstowych CC0, "
        f"{memory_stats['ccmod_global_rows']} globalnych reguł wierszy CCMod i "
        f"{memory_stats['cc0_global_rows']} globalnych reguł wierszy CC0 i "
        f"{memory_stats['custom_topics']} własnych kategorii Treatment Area Footprint. "
        "Po zapisaniu korekty Treatment Area Footprint / kategorii leczenia ta sama pozycja wiersza "
        "oraz identyczne oczyszczone sformułowanie będą kalibrowane w kolejnych analizach niezależnie od nazwy pliku."
    )


    with st.expander("Własne kategorie Treatment Area Footprint", expanded=False):
        st.caption(
            "Dodaj nową kategorię oraz słowa/frazy, po których aplikacja ma ją rozpoznawać "
            "w CCMod i CC0. Frazy będą stosowane do wszystkich kolejnych analiz niezależnie od nazwy pliku."
        )
        custom_topic_name = st.text_input(
            "Nazwa nowej kategorii",
            key="custom_topic_name",
            placeholder="np. posterior_crossbite",
        )
        custom_topic_keywords = st.text_area(
            "Słowa lub frazy rozpoznające kategorię (jedna na linię)",
            key="custom_topic_keywords",
            height=100,
            placeholder="np. crossbite\nzgryz krzyżowy",
        )
        if st.button("Zapisz kategorię Treatment Area Footprint", key="save_custom_topic"):
            memory = load_calibration_memory()
            added_keywords = remember_custom_topic(memory, custom_topic_name, parse_custom_phrases(custom_topic_keywords))
            if added_keywords:
                save_calibration_memory(memory)
                calibration_memory = memory
                st.success(
                    f"Zapisano kategorię '{custom_topic_name.strip()}' z {added_keywords} nowymi frazami. "
                    "Będzie rozpoznawana w kolejnych analizach."
                )
            else:
                st.warning("Podaj nazwę kategorii i co najmniej jedną nową frazę rozpoznającą.")

    topic_keywords = get_topic_keywords(calibration_memory)

    # Analysis mode selection
    analysis_mode = st.selectbox(
        "Wybierz tryb analizy",
        ("Auto", "CCMod", "CC0"),
        index=0,
        help="W trybie Auto aplikacja spróbuje automatycznie rozpoznać strukturę pliku."
    )
    # Language selection (not used in classification but kept for future)
    language = st.selectbox(
        "Wybierz język komentarzy/instrukcji",
        ("Auto", "French", "Spanish", "English", "Mixed"),
        index=0,
        help="Analiza słów kluczowych jest niezależna od języka, ale możesz tutaj zaznaczyć dominujący język."
    )
    # Custom exclusion phrases
    st.write("Możesz dodać własne frazy do wykluczenia (jedna fraza na linię):")
    custom_phrases_input = st.text_area("Frazy do wykluczenia", value="", height=150)
    custom_phrases = parse_custom_phrases(custom_phrases_input)
    # Row-level option
    include_full_rows = st.checkbox(
        "Dołącz pełen eksport wierszy i kalibrację wszystkich rekordów (może spowolnić analizę przy bardzo dużych plikach)", value=True
    )

    if st.button("Uruchom analizę"):
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
                    st.error(f"Nie można rozpoznać formatu pliku {file_name}. Upewnij się, że zawiera oczekiwane kolumny.")
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
                    st.error(f"Plik {file_name} nie zawiera wymaganych kolumn komentarzy (np. 'COMMENT' lub 'H') i numeru CCMod (np. 'CCMod number' lub 'G').")
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
                    st.success(f"Zastosowano {applied_rules} zapamiętanych kalibracji dla {file_name}.")
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
                    st.error(f"Plik {file_name} nie zawiera kolumny z instrukcjami (np. 'Instruction' lub 'E').")
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
                    st.success(f"Zastosowano {applied_rules} zapamiętanych kalibracji dla {file_name}.")
                results.append(res)
                processed_file_names.append(file_name)
                downloads[file_name] = build_excel_download(res, mode)
                result_modes[file_name] = mode
                summaries[file_name] = generate_cc0_summary(file_name, res)
            else:
                st.error(f"Nieobsługiwany tryb analizy dla pliku {file_name}.")
                continue
        if not results:
            st.warning("Brak wyników analizy do wyświetlenia.")
            return
        st.session_state["analysis_results"] = dict(zip(processed_file_names, results))
        st.session_state["analysis_modes"] = result_modes
        # Display summaries and download links per file
        st.header("Podsumowania plików")
        for fn in file_names:
            if fn in summaries:
                st.subheader(fn)
                st.markdown(summaries[fn])
                # Provide download button
                file_key = fn + "_download"
                st.download_button(
                    label=f"Pobierz wynik analiz dla {fn}",
                    data=downloads[fn],
                    file_name=f"analysis_{fn}",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=file_key,
                )
        # If multiple files, generate comparison summary and summary file
        if len(results) > 1:
            comp_df = summarise_results(results, processed_file_names)
            comp_summary = generate_comparison_summary(comp_df)
            st.header("Porównanie wielu plików")
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
                label="Pobierz wszystkie wyniki jako ZIP",
                data=zip_buffer.getvalue(),
                file_name="analiza_wyniki.zip",
                mime="application/zip",
            )


    if "analysis_results" in st.session_state and st.session_state["analysis_results"]:
        st.header("Kalibracja po analizie")
        st.write(
            "Po wygenerowaniu analizy możesz ręcznie skorygować przypisanie tematów leczenia, focusu i złożoności. "
            "To pomaga rozstrzygnąć przypadki graniczne, np. czy dana fraza powinna wejść w staging czy w tooth movements."
        )
        calibrated_results: Dict[str, Any] = {}
        calibrated_downloads: Dict[str, bytes] = {}
        for fn, result in st.session_state["analysis_results"].items():
            mode = st.session_state["analysis_modes"].get(fn)
            with st.expander(f"Skalibruj {fn}", expanded=False):
                calibrated = render_calibration_panel(fn, result, mode, topic_keywords)
                updates = collect_memory_updates(result.row_level, calibrated.row_level, mode)
                global_row_updates = collect_global_row_updates(result.row_level, calibrated.row_level, mode)
                update_count = max(len(updates), len(global_row_updates))
                if update_count:
                    st.warning(
                        f"Wykryto {update_count} nowych zmian kalibracyjnych. "
                        "Kliknij przycisk poniżej, aby zapamiętać je permanentnie dla identycznych tekstów "
                        "i globalnie dla tych samych pozycji wierszy we wszystkich nowych analizach."
                    )
                if st.button(
                    "Zapisz tę kalibrację jako naukę na przyszłość",
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
                        f"Zapamiętano {saved_count} reguł. Będą użyte w kolejnych analizach "
                        "identycznych sformułowań oraz globalnie dla tych samych pozycji wierszy, "
                        "niezależnie od nazwy pliku."
                    )
                calibrated_results[fn] = calibrated
                calibrated_downloads[fn] = build_excel_download(calibrated, mode)
                if mode == "ccmod":
                    st.markdown(generate_ccmod_summary(fn, calibrated))
                elif mode == "cc0":
                    st.markdown(generate_cc0_summary(fn, calibrated))
                st.download_button(
                    label=f"Pobierz skalibrowany wynik dla {fn}",
                    data=calibrated_downloads[fn],
                    file_name=f"calibrated_analysis_{fn}",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"calibrated_download_{fn}",
                )
        if len(calibrated_results) > 1:
            st.subheader("Porównanie po kalibracji")
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
                label="Pobierz wszystkie skalibrowane wyniki jako ZIP",
                data=zip_buffer.getvalue(),
                file_name="skalibrowane_wyniki.zip",
                mime="application/zip",
                key="calibrated_zip_download",
            )


if __name__ == "__main__":
    main()
