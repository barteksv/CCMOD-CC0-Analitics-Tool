"""Streamlit page for Doctor Pattern Analysis."""
from __future__ import annotations
import io
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from config.doctor_pattern_rules import DEFAULT_EXCLUSIONS, DEFAULT_FINDING_WEIGHTS
from services.doctor_pattern_engine import analyze_doctor_patterns, detect_file_role, propose_mapping
from services.doctor_pattern_export import build_doctor_pattern_excel

DISCLAIMER = "This analysis identifies text and sequence patterns within the uploaded CC0 and CCMod files. An order without a matched CCMod is reported only as having no CCMod in the uploaded dataset. It is not automatically classified as accepted or clinically successful. Pattern classification is rule-based and should be reviewed before clinical conclusions are made."

def _read_excel(uploaded):
    return pd.read_excel(io.BytesIO(uploaded.getvalue()), engine='openpyxl')

def _select_col(label, cols, value=None, required=False, key=None):
    opts=[None]+list(cols); idx=opts.index(value) if value in opts else 0
    return st.selectbox(label + (" *" if required else ""), opts, index=idx, format_func=lambda x:"-- not mapped --" if x is None else str(x), key=key)

def render_doctor_pattern_analysis():
    st.header("Doctor Pattern Analysis")
    st.caption("Compare CC0 instructions with later CCMod comments to identify repeated, late-emerging and changed requests.")
    st.info(DISCLAIMER)
    c1,c2=st.columns(2)
    with c1: file_a=st.file_uploader("Upload Excel file A", type=['xlsx'], key='dpa_a')
    with c2: file_b=st.file_uploader("Upload Excel file B", type=['xlsx'], key='dpa_b')
    if not (file_a and file_b): return
    with st.spinner("Reading workbooks and detecting file types..."):
        df_a=_read_excel(file_a); df_b=_read_excel(file_b)
    role_a=detect_file_role(df_a); role_b=detect_file_role(df_b)
    st.subheader("Detected mapping")
    st.write(pd.DataFrame([{"file":file_a.name,"detected_role":role_a,"columns":", ".join(map(str,df_a.columns[:12]))},{"file":file_b.name,"detected_role":role_b,"columns":", ".join(map(str,df_b.columns[:12]))}]))
    default_cc0 = file_a.name if role_a=='CC0' else file_b.name if role_b=='CC0' else file_a.name
    cc0_name=st.radio("Which file is the CC0 instructions file?", [file_a.name,file_b.name], index=[file_a.name,file_b.name].index(default_cc0), horizontal=True)
    cc0_df, ccmod_df=(df_a,df_b) if cc0_name==file_a.name else (df_b,df_a)
    cc0_map=propose_mapping(cc0_df,'CC0'); ccmod_map=propose_mapping(ccmod_df,'CCMod')
    with st.expander("Column mapping and validation", expanded=True):
        l,r=st.columns(2)
        with l:
            st.markdown("**CC0 required fields**")
            cc0_order=_select_col("CC0 order identifier", cc0_df.columns, cc0_map.get('order'), True, 'dpa_cc0_order')
            cc0_instruction=_select_col("CC0 initial instruction", cc0_df.columns, cc0_map.get('instruction'), True, 'dpa_cc0_instr')
        with r:
            st.markdown("**CCMod fields**")
            cm_order=_select_col("CCMod order identifier", ccmod_df.columns, ccmod_map.get('order'), True, 'dpa_cm_order')
            cm_num=_select_col("CCMod number", ccmod_df.columns, ccmod_map.get('ccmod_number'), True, 'dpa_cm_num')
            cm_comment=_select_col("CCMod comment", ccmod_df.columns, ccmod_map.get('comment'), True, 'dpa_cm_comment')
            cm_pid=_select_col("PID", ccmod_df.columns, ccmod_map.get('pid'), False, 'dpa_pid')
            cm_part=_select_col("part_category", ccmod_df.columns, ccmod_map.get('part_category'), False, 'dpa_part')
            cm_time=_select_col("complete_time", ccmod_df.columns, ccmod_map.get('complete_time'), False, 'dpa_time')
            cm_doc=_select_col("DoctorID", ccmod_df.columns, ccmod_map.get('doctor_id'), False, 'dpa_doc')
    with st.expander("Text Cleaning Settings"):
        disabled=st.multiselect("Disable default exclusions", DEFAULT_EXCLUSIONS, default=[])
        custom=st.text_area("Add custom exclusions, one per line", height=100)
        active=[x for x in DEFAULT_EXCLUSIONS if x not in disabled]+[x.strip() for x in custom.splitlines() if x.strip()]
        st.write(pd.DataFrame({"active_exclusion":active}))
    with st.expander("Advanced Settings"):
        duplicate_policy=st.selectbox("Duplicate handling", ["exclude_duplicate_clinical","keep_all_rows","exclude_exact_source_duplicates"], index=0)
        weights={k:st.number_input(k, value=float(v), min_value=0.0, max_value=1.0, step=.05) for k,v in DEFAULT_FINDING_WEIGHTS.items()}
        show_ids=st.checkbox("Show order identifiers in report", value=True)
    errors=[]
    if not cc0_order: errors.append("CC0 order identifier was not detected.")
    if not cc0_instruction: errors.append("The selected CC0 instruction column contains no usable text." if cc0_instruction else "CC0 instruction column was not detected.")
    if not cm_order: errors.append("CCMod order identifier was not detected.")
    if not cm_num: errors.append("CCMod number could not be parsed.")
    if not cm_comment: errors.append("CCMod comment column was not detected.")
    for e in errors: st.error(e)
    if errors: return
    if st.button("Run Pattern Analysis", type='primary'):
        with st.spinner("Running rule-based sequence analysis..."):
            res=analyze_doctor_patterns(cc0_df, ccmod_df, {'order':cc0_order,'instruction':cc0_instruction}, {'order':cm_order,'ccmod_number':cm_num,'comment':cm_comment,'pid':cm_pid,'part_category':cm_part,'complete_time':cm_time,'doctor_id':cm_doc}, active, duplicate_policy, weights)
        st.session_state['doctor_pattern_result']=res
        st.session_state['doctor_pattern_show_ids']=show_ids
    res=st.session_state.get('doctor_pattern_result')
    show_ids=st.session_state.get('doctor_pattern_show_ids', True)
    if not res: return
    def view_df(df):
        out=df.copy()
        if not show_ids:
            order_cols=[c for c in out.columns if 'order' in str(c).lower() or str(c).lower() in {'cc0_order_key','ccmod_order_key'}]
            values=pd.unique(pd.concat([out[c].astype(str) for c in order_cols], ignore_index=True)) if order_cols else []
            mapping={v:f'Order {i+1}' for i,v in enumerate([x for x in values if x and x!='nan'])}
            for c in order_cols:
                out[c]=out[c].astype(str).map(lambda x:mapping.get(x,x))
        return out
    tabs=st.tabs(["Executive Summary","Frequent Requests","CC0 vs CCMod","Iteration Patterns","Primary vs Secondary","Order Explorer","Detailed Data","Export"])
    with tabs[0]:
        st.subheader("Data Coverage")
        cov=res['coverage'].iloc[0].to_dict(); cols=st.columns(4)
        for i,(k,v) in enumerate(cov.items()): cols[i%4].metric(k, f"{v:.1%}" if isinstance(v,float) and 'percentage' in k.lower() or 'rate' in k.lower() else str(v))
        st.subheader("Top Problem Findings")
        for i,row in res['findings'].iterrows():
            st.markdown(f"**Problem {i+1}: {row['problem_title']}**\n\nEvidence:\n- {row['evidence']}\n- Scale: {row['scale']}\n\nMost frequent exact comments:\n{row['exact_recurring_comments']}\n\nExample sequence:\n{row['example_sequence']}\n\nObserved issue:\n{row['observed_issue']}")
        st.subheader("Data Quality"); st.dataframe(view_df(res['data_quality']), use_container_width=True)
        if not res['frequent_requests'].empty: st.plotly_chart(px.bar(res['frequent_requests'].head(15).sort_values('comment_count'), x='comment_count', y='category', orientation='h', title='Most frequent request categories'), use_container_width=True)
    with tabs[1]:
        df=res['frequent_requests']; st.dataframe(view_df(df), use_container_width=True)
        st.subheader("Exact Repeated Comments"); st.dataframe(view_df(res['exact_comments']), use_container_width=True)
        st.subheader("Similar Comment Clusters"); st.dataframe(view_df(res['similar_comment_clusters']), use_container_width=True)
    with tabs[2]:
        gap=res['cc0_vs_ccmod']; st.dataframe(view_df(gap), use_container_width=True)
        if not gap.empty:
            st.plotly_chart(px.bar(gap, x='category', y=['present_upfront','preference_only','missing_upfront','late_emerging'], title='CC0 vs CCMod gap', barmode='stack'), use_container_width=True)
            min_flow=st.slider('Minimum Sankey frequency', 1, 25, 3)
            flows=[]
            for _,row in res['order_summary'].iterrows():
                for src in row.get('cc0_case_categories', []) or []:
                    if src != 'General or unclassified':
                        for dst in set(res['category_rows'].loc[res['category_rows']['ccmod_order_key']==row['cc0_order_key'], 'category'].dropna()):
                            flows.append((src,dst))
            if flows:
                flow_df=pd.DataFrame(flows, columns=['source','target']).value_counts().reset_index(name='value')
                flow_df=flow_df[flow_df['value']>=min_flow]
                if not flow_df.empty:
                    labels=list(pd.unique(pd.concat([flow_df['source'],flow_df['target']])))
                    fig=go.Figure(data=[go.Sankey(node=dict(label=labels), link=dict(source=flow_df['source'].map(labels.index), target=flow_df['target'].map(labels.index), value=flow_df['value']))])
                    fig.update_layout(title='CC0 category to later CCMod category flow')
                    st.plotly_chart(fig, use_container_width=True)
        cats=res['category_rows']
        if not cats.empty:
            heat=cats.dropna(subset=['ccmod_iteration']).pivot_table(index='category', columns='ccmod_iteration', values='ccmod_order_key', aggfunc='count', fill_value=0)
            st.plotly_chart(px.imshow(heat, title='Category by CCMod iteration'), use_container_width=True)
    with tabs[3]:
        st.subheader("Repeated Across Iterations"); st.dataframe(view_df(res['repeated_requests']), use_container_width=True)
        st.subheader("Late-Emerging Requests"); st.dataframe(view_df(res['late_requests']), use_container_width=True)
        st.subheader("Changed Decisions"); st.dataframe(view_df(res['changed_decisions']), use_container_width=True)
        if not res['order_summary'].empty and 'max_ccmod_iteration' in res['order_summary']:
            st.plotly_chart(px.histogram(res['order_summary'], x='max_ccmod_iteration', title='Maximum CCMod number per order'), use_container_width=True)
    with tabs[4]:
        st.dataframe(view_df(res['primary_vs_secondary']), use_container_width=True)
        cats=res['category_rows']
        if not cats.empty:
            comp=cats.groupby(['part_category_normalized','category']).size().reset_index(name='count')
            st.plotly_chart(px.bar(comp, x='category', y='count', color='part_category_normalized', barmode='group', title='Primary vs Secondary category counts'), use_container_width=True)
    with tabs[5]:
        orders=sorted(res['order_summary']['cc0_order_key'].dropna().astype(str).unique().tolist())
        sel=st.selectbox("order_number", orders) if orders else None
        if sel:
            st.write(res['order_summary'][res['order_summary']['cc0_order_key'].astype(str)==sel].T)
            st.dataframe(view_df(res['ccmod_cleaned'][res['ccmod_cleaned']['ccmod_order_key'].astype(str)==sel]), use_container_width=True)
    with tabs[6]:
        for name,key in [("Cleaned CC0",'cc0_cleaned'),("Cleaned CCMod",'ccmod_cleaned'),("Matched order-level",'order_summary'),("Category-level",'category_rows'),("Sequence-level",'order_sequences'),("Changed decisions",'changed_decisions'),("Unmatched records",'unmatched_orders')]:
            with st.expander(name):
                st.dataframe(view_df(res[key]), use_container_width=True)
                st.download_button(f"Download {name} CSV", res[key].to_csv(index=False).encode('utf-8'), file_name=f"{key}.csv", mime='text/csv')
    with tabs[7]:
        st.dataframe(view_df(res['boilerplate_audit']), use_container_width=True)
        xlsx=build_doctor_pattern_excel(res)
        st.download_button("Download Doctor_Pattern_Analysis.xlsx", xlsx, file_name="Doctor_Pattern_Analysis.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
