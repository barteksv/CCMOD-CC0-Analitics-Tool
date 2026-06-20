"""
Streamlit application for analysing Invisalign CCMod comments and CC0 instructions.

This app allows users to upload Excel files containing doctor comments
or instructions, select analysis settings, define custom exclusion
phrases and run analyses. Results are summarised in Polish, exported
to styled Excel workbooks and made available for download individually
or as a ZIP archive. Multiple files can be processed and compared.
"""

import io
import os
import zipfile
from datetime import datetime
from typing import List, Dict

import pandas as pd
import streamlit as st

from analyzer.io_utils import load_excel, detect_ccmod_columns, detect_cc0_instruction_column, detect_analysis_mode
from analyzer.ccmod_analyzer import analyse_ccmod_dataframe
from analyzer.cc0_analyzer import analyse_cc0_dataframe
from analyzer.comparison import summarise_results
from analyzer.excel_export import export_ccmod_to_excel, export_cc0_to_excel
from analyzer.summary_generator import generate_ccmod_summary, generate_cc0_summary, generate_comparison_summary


def parse_custom_phrases(text: str) -> List[str]:
    """Split a multi‑line string into a list of phrases, ignoring empty lines."""
    if not text:
        return []
    return [line.strip() for line in text.split("\n") if line.strip()]


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
        "Dołącz pełen eksport wierszy (może spowolnić analizę przy bardzo dużych plikach)", value=False
    )

    if st.button("Uruchom analizę"):
        results = []
        file_names = []
        downloads: Dict[str, bytes] = {}
        summaries: Dict[str, str] = {}
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
                )
                results.append(res)
                # Generate Excel file in memory
                buffer = io.BytesIO()
                export_ccmod_to_excel(res, buffer)
                downloads[file_name] = buffer.getvalue()
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
                )
                results.append(res)
                buffer = io.BytesIO()
                export_cc0_to_excel(res, buffer)
                downloads[file_name] = buffer.getvalue()
                summaries[file_name] = generate_cc0_summary(file_name, res)
            else:
                st.error(f"Nieobsługiwany tryb analizy dla pliku {file_name}.")
                continue
        if not results:
            st.warning("Brak wyników analizy do wyświetlenia.")
            return
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
            comp_df = summarise_results(results, file_names)
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


if __name__ == "__main__":
    main()