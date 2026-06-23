"""Excel export helpers for Doctor Pattern Analysis."""
from __future__ import annotations
import io
from typing import Dict
import pandas as pd
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
