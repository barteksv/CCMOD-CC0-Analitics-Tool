# Streamlit Application for CCMod and CC0 Analysis

This project provides a Streamlit web application that analyses Invisalign doctor comments (CCMod) and initial treatment instructions (CC0) from Excel files. It mirrors the analytical logic developed in our conversation, including cleaning, topic classification, complexity assessment and report generation.

## Features

- **Flexible Uploads**: Upload one or multiple Excel files with CCMod comments or CC0 instructions.
- **Auto or Manual Mode**: Let the app automatically detect the file type or specify CCMod/CC0 analysis mode explicitly.
- **Language Selection**: Choose the dominant language of your data (analysis itself is multilingual).
- **Custom Exclusion Phrases**: Add your own phrases to remove from comments or instructions during cleaning.
- **Row‑Level Control**: Opt to include the full row‑level classification in your output or just a sample to save time.
- **Detailed Metrics**: Calculate average comment lengths, topic distributions, complexity breakdowns, and detect requests for new treatment plans.
- **Excel Exports**: Generate polished Excel workbooks with multiple tabs summarising your data. Tabs include summary, averages by categories, topic counts, complexity, top formulations and more.
- **Comparison Across Files**: If you upload more than one file, the app will compare them and highlight key differences in length and topics.
- **Polish Summaries**: Each analysis produces a human‑readable summary in Polish.

## Installation

1. Clone this repository or download the zip file.
2. Create a virtual environment (optional but recommended):

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Running the App

From the project directory, run:

```bash
streamlit run app.py
```

Then open your browser to the local URL shown in the console (typically `http://localhost:8501`). Upload your Excel files and configure the analysis options via the sidebar.

## Usage

1. **Upload Files**: Drag and drop one or more `.xlsx` files containing CCMod or CC0 data. Each file should have the appropriate columns:
   - **CCMod**: Comment column (`COMMENT`/`Comment`/`H`), case type column (`part_category`/`Case Type`/`C`), and CCMod number column (`CCMod number`/`G`).
   - **CC0**: Instruction column (`Instruction`/`E`).

2. **Choose Analysis Mode**:
   - **Auto**: The app inspects your data and picks CCMod or CC0 mode automatically.
   - **CCMod**: Forces comment analysis.
   - **CC0**: Forces instruction analysis.

3. **Set Language**: Select the dominant language (optional). This does not change keyword classification but may be useful for future enhancements.

4. **Add Exclusion Phrases**: If there are boilerplate phrases unique to your data, enter them one per line. These will be removed from comments or instructions before analysis.

5. **Run Analysis**: Click the **Uruchom analizę** button. Results will appear below for each file, along with download buttons for the Excel outputs.

6. **Download Results**: You can download each file’s analysis separately or all results at once as a ZIP archive.

## Known Limitations

- **Keyword-Based Classification**: Topics are determined via simple keyword matching. This provides a strong operational overview but is not a substitute for detailed clinical review.
- **Languages**: The keyword lists cover English, French and Spanish terms. Comments in other languages may not be fully recognised.
- **Performance**: Including the full row‑level output on very large files may slow down the export. Use the sample option for a quicker overview.
- **Excel Formatting**: Column widths and wrapping are set to reasonable defaults but may require manual adjustments for exceptionally long text.

## License

This project is provided for educational purposes and internal operational analysis. Adapt as needed for your workflows.