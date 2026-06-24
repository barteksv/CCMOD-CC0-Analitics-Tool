"""Excel export helpers for Doctor Pattern Analysis."""
from __future__ import annotations
import io
from typing import Dict
import pandas as pd

VARIABLE_GLOSSARY = {
    "present_upfront": "The same clinical category was detected in the CC0 case-specific instruction for that order.",
    "preference_only": "The category was detected only in the CC0 preference/general section, not in the case-specific instruction.",
    "missing_upfront": "The category appears first in CCMod 1 and was not detected in the CC0 case-specific instruction.",
    "late_emerging": "The category first appears at CCMod 2 or later.",
    "repeated_later_ccmods": "Count of order/category sequences where the same category appears across multiple CCMod iterations.",
    "changed_decision": "The same category repeats but extracted details, values, or action direction changed between iterations.",
    "repeated_request": "True when a category appears in at least two different CCMod iterations for the same order.",
    "consecutively_repeated": "True when repeated category requests occur in back-to-back CCMod iterations.",
    "persistent_unresolved_request": "A repeated category with the same extracted clinical signature across iterations.",
    "added_detail": "Later comments add a different signature/detail, but the rule engine did not classify it as a changed decision.",
    "first_ccmod_iteration": "Earliest parsed CCMod number where the category appears for an order.",
    "last_ccmod_iteration": "Latest parsed CCMod number where the category appears for an order.",
    "ccmods_with_category": "Number of distinct CCMod iterations containing the category for an order.",
    "cc0_case_categories": "Categories detected from the case-specific parts of the CC0 initial instruction.",
    "cc0_preference_categories": "Categories detected from preference/general CC0 instruction text.",
    "analysis_text": "CCMod comment text after view markers and configured boilerplate exclusions are removed.",
    "normalized_comment": "Lowercase normalized form used to group exact/similar recurring comments.",
    "value_signature": "Extracted values/actions plus normalized wording used to compare whether repeated requests changed over time.",
    "duplicate_clinical_comment": "Duplicate flag based on order, CCMod iteration, and normalized cleaned comment.",
    "exact_source_duplicate": "Duplicate flag based on the original mapped order, CCMod number, and comment columns.",
    "ccmod_number_unparsed": "True when the selected CCMod number cell did not contain a parsable number.",
    "part_category_normalized": "Case type normalized from the mapped part_category column, usually Primary, Secondary, or Unknown.",
    "boilerplate_audit": "Per-row record of default/custom exclusion phrases removed from the comment.",
}

SHEETS = [("Executive_Summary","findings"),("Data_Coverage","coverage"),("Frequent_Requests","frequent_requests"),("Exact_Comments","exact_comments"),("Similar_Comment_Clusters","similar_comment_clusters"),("CC0_vs_CCMod","cc0_vs_ccmod"),("Repeated_Requests","repeated_requests"),("Late_Requests","late_requests"),("Changed_Decisions","changed_decisions"),("Primary_vs_Secondary","primary_vs_secondary"),("Order_Summary","order_summary"),("Order_Sequences","order_sequences"),("CC0_Cleaned","cc0_cleaned"),("CCMod_Cleaned","ccmod_cleaned"),("Unmatched_Orders","unmatched_orders"),("Boilerplate_Audit","boilerplate_audit"),("Rules_Used","rules_used")]

def _safe_df(df):
    if df is None: return pd.DataFrame()
    out=df.copy()
    for c in out.columns:
        out[c]=out[c].map(lambda x: ", ".join(map(str,x)) if isinstance(x,list) else (str(x) if isinstance(x,dict) else x))
    return out

def build_doctor_pattern_excel(result: Dict[str,pd.DataFrame]) -> bytes:
    buf=io.BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        wb=writer.book
        header=wb.add_format({'bold':True,'bg_color':'#1F4E78','font_color':'white','border':1})
        wrap=wb.add_format({'text_wrap':True,'valign':'top'})
        pct=wb.add_format({'num_format':'0.0%'})
        glossary = pd.DataFrame([{"Variable": key, "Meaning": value} for key, value in VARIABLE_GLOSSARY.items()])
        glossary.to_excel(writer, sheet_name="Variable_Glossary", index=False)
        glossary_ws = writer.sheets["Variable_Glossary"]
        glossary_ws.freeze_panes(1, 0)
        glossary_ws.autofilter(0, 0, max(len(glossary), 1), 1)
        glossary_ws.write(0, 0, "Variable", header)
        glossary_ws.write(0, 1, "Meaning", header)
        glossary_ws.set_column(0, 0, 28, wrap)
        glossary_ws.set_column(1, 1, 100, wrap)
        for sheet,key in SHEETS:
            df=_safe_df(result.get(key))
            if df.empty: df=pd.DataFrame({"message":["No rows for this section."]})
            df.to_excel(writer, sheet_name=sheet, index=False)
            ws=writer.sheets[sheet]
            ws.freeze_panes(1,0); ws.autofilter(0,0,max(len(df),1),max(len(df.columns)-1,0))
            for idx,col in enumerate(df.columns):
                ws.write(0,idx,col,header)
                width=min(max(12, min(60, int(df[col].astype(str).str.len().quantile(.9) if len(df) else 12)+2)),60)
                ws.set_column(idx,idx,width, wrap if any(k in col.lower() for k in ['comment','instruction','sequence','text','evidence','issue']) else None)
                if 'pct' in col.lower() or 'percentage' in col.lower() or 'rate' in col.lower(): ws.set_column(idx,idx,14,pct)
    return buf.getvalue()
