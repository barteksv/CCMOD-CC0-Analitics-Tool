"""Rule-based Doctor Pattern Analysis engine."""
from __future__ import annotations
import re, unicodedata
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Dict, Iterable, List, Optional, Tuple
import numpy as np
import pandas as pd
try:
    from rapidfuzz import fuzz
except Exception:
    fuzz = None
from config.doctor_pattern_rules import ALL_CATEGORIES, CATEGORY_KEYWORDS, DEFAULT_EXCLUSIONS, DEFAULT_FINDING_WEIGHTS

PREFERENCE_MARKER_RE = re.compile(r"\[\s*PreferenceInstruc(?:tions|ions)\s*:\s*\]", re.I)

ALIASES = {
    "order": ["SO","so","Sales Order","SalesOrder","Order Number","order_number","OrderNumber","order number"],
    "instruction": ["Instruction","Instructions","Doctor Instruction","Doctor Instructions","CC0 Instruction","Initial Instruction","Comments","Comment"],
    "ccmod_number": ["CCMod number","CCMod Number","CCMod","Modification Number","Mod Number","Iteration Number"],
    "comment_cleaned": ["COMMENT cleaned"],
    "comment": ["COMMENT cleaned","COMMENT","Comment","Comments","CCMod Comment","Modification Comment"],
    "part_category": ["part_category","Part Category","Case Type","case_type","Order Type"],
    "pid": ["PID","pid"],
    "complete_time": ["complete_time","Complete Time","Date","date","completed_at"],
    "doctor_id": ["DoctorID","Doctor ID","did","DID"],
}

def _key(s: Any) -> str:
    return re.sub(r"[\s_\-]+", "", str(s).strip().lower())

def detect_column(columns: Iterable[str], aliases: Iterable[str]) -> Optional[str]:
    lookup={_key(c): c for c in columns}
    for a in aliases:
        if _key(a) in lookup: return lookup[_key(a)]
    return None

def detect_file_role(df: pd.DataFrame) -> str:
    cols=df.columns
    ccmod_score=sum(bool(detect_column(cols, ALIASES[k])) for k in ["order","ccmod_number","comment"])
    cc0_score=sum(bool(detect_column(cols, ALIASES[k])) for k in ["order","instruction"])
    if ccmod_score>=2 and ccmod_score>=cc0_score: return "CCMod"
    if cc0_score>=2: return "CC0"
    return "Unknown"

def propose_mapping(df: pd.DataFrame, role: str) -> Dict[str, Optional[str]]:
    cols=df.columns
    if role == "CC0":
        return {"order": detect_column(cols, ALIASES["order"]), "instruction": detect_column(cols, ALIASES["instruction"])}
    cleaned=detect_column(cols, ALIASES["comment_cleaned"])
    raw=detect_column(cols, [a for a in ALIASES["comment"] if a != "COMMENT cleaned"])
    comment=cleaned if cleaned and df[cleaned].astype(str).str.strip().replace({"nan":""}).ne("").any() else raw or cleaned
    return {"order": detect_column(cols, ALIASES["order"]), "ccmod_number": detect_column(cols, ALIASES["ccmod_number"]), "comment": comment, "pid": detect_column(cols, ALIASES["pid"]), "part_category": detect_column(cols, ALIASES["part_category"]), "complete_time": detect_column(cols, ALIASES["complete_time"]), "doctor_id": detect_column(cols, ALIASES["doctor_id"])}

def normalize_order_id(v: Any) -> Optional[str]:
    if v is None or (isinstance(v,float) and np.isnan(v)): return None
    s=str(v).replace("\u00a0", " ").strip()
    if s.lower() in {"", "nan", "none", "null", "nat"}: return None
    if re.fullmatch(r"\d+\.0+", s): s=s.split('.')[0]
    return s

def parse_ccmod_number(v: Any) -> Optional[int]:
    if v is None or (isinstance(v,float) and np.isnan(v)): return None
    m=re.search(r"(\d+)", str(v))
    return int(m.group(1)) if m else None

def strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', str(s)) if not unicodedata.combining(c))

def normalize_text_for_matching(s: str) -> str:
    s=strip_accents(str(s).lower())
    s=re.sub(r"\{view#\d+\}", " ", s)
    s=re.sub(r"\b(please|thanks|thank you|merci|por favor|s'il vous plait|svp)\b", " ", s)
    s=re.sub(r"[^a-z0-9./]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def _flex_pattern(phrase: str) -> re.Pattern:
    p=strip_accents(phrase.lower())
    p=re.escape(p)
    p=p.replace(r"\ ", r"\s+").replace(r"\-", r"[\s\-]*").replace(r"\:", r"\s*:\s*")
    return re.compile(p, re.I)

def clean_text(text: Any, exclusions: Iterable[str]=DEFAULT_EXCLUSIONS) -> Tuple[str, Dict[str,int]]:
    if text is None or (isinstance(text,float) and np.isnan(text)): text=""
    original=str(text).replace("\r", "\n").replace("\u00a0", " ")
    cleaned=re.sub(r"\{view#\d+\}", " ", original, flags=re.I)
    audit={}
    accent_clean=strip_accents(cleaned)
    for phrase in exclusions:
        pat=_flex_pattern(phrase)
        cnt=len(pat.findall(accent_clean))
        if cnt:
            accent_clean=pat.sub(" ", accent_clean); audit[phrase]=cnt
    cleaned=re.sub(r"\s+", " ", accent_clean).strip()
    return cleaned, audit

def split_cc0_sections(text: Any, exclude_preferences: bool=False) -> Dict[str,str]:
    full="" if text is None or (isinstance(text,float) and np.isnan(text)) else str(text)
    if exclude_preferences:
        marker = PREFERENCE_MARKER_RE.search(full)
        if marker:
            full = full[:marker.start()]
    labels=list(re.finditer(r"\[([^\]]+):?\]", full))
    out={"cc0_full_instruction": full, "cc0_case_specific_instruction":"", "cc0_preference_instruction":"", "cc0_upper_arch_instruction":"", "cc0_lower_arch_instruction":"", "cc0_other_instruction":""}
    if not labels:
        out["cc0_case_specific_instruction"]=full.strip(); return out
    pre=full[:labels[0].start()].strip(); case=[]
    if pre: case.append(pre)
    for i,m in enumerate(labels):
        name=m.group(1).lower(); start=m.end(); end=labels[i+1].start() if i+1<len(labels) else len(full); val=full[start:end].strip()
        if "preference" in name or "general" in name: out["cc0_preference_instruction"] += (" " + val).strip()
        elif "upper" in name: out["cc0_upper_arch_instruction"] += (" " + val).strip(); case.append(val)
        elif "lower" in name: out["cc0_lower_arch_instruction"] += (" " + val).strip(); case.append(val)
        else: out["cc0_other_instruction"] += (" " + val).strip(); case.append(val)
    out["cc0_case_specific_instruction"]=" ".join(x for x in case if x).strip()
    return out

def normalize_part_category(v: Any) -> str:
    s=str(v or "").strip()
    low=s.lower()
    if "primary" in low: return "Primary"
    if "secondary" in low: return "Secondary"
    return s if s else "Unknown"

COMPILED={cat:[re.compile(p if p.startswith(r"\b") else re.escape(p), re.I) for p in pats] for cat,pats in CATEGORY_KEYWORDS.items()}
def classify_categories(text: Any) -> List[str]:
    t=normalize_text_for_matching(str(text or ""))
    cats=[cat for cat,pats in COMPILED.items() if any(p.search(t) for p in pats)]
    return cats or (["General or unclassified"] if t else [])

def extract_values(text: Any) -> Dict[str, Any]:
    t=normalize_text_for_matching(str(text or "")); vals={}
    vals["requested_passive_aligner_count"]=[int(x) for x in re.findall(r"\b(\d+)\s*passive?s?\s*(?:aligners?|trays?|aligneurs?|alineadores?)", t)]
    vals["requested_aligner_count"]=[int(x) for x in re.findall(r"\b(\d+)\s*(?:active\s*)?(?:aligners?|aligneurs?|alineadores?)", t) if int(x) not in vals["requested_passive_aligner_count"]]
    vals["referenced_ccmod_number"]=[int(x) for x in re.findall(r"\bcc\s*mod?\s*(\d+)|\bcc\s*(\d+)", t) for x in x if x]
    pkg=re.findall(r"\b(lite|moderate|full)\b", t); vals["requested_package"]=pkg
    vals["requested_stage"]=[int(x) for x in re.findall(r"\bstage\s*(\d+)", t)]
    vals["requested_ipr_value"]=[float(x) for x in re.findall(r"\bipr\D{0,10}(\d+(?:\.\d+)?)", t)]
    vals["requested_movement_value"]=[float(x) for x in re.findall(r"\b(?:distalization|distalize|overjet|expand|expansion)\D{0,10}(\d+(?:\.\d+)?)\s*mm", t)]
    vals["referenced_teeth"]=re.findall(r"\b(?:tooth|teeth)\s*([0-9/ ,]+)", t)
    return vals

def detect_actions(text: Any) -> Dict[str,str]:
    t=normalize_text_for_matching(text)
    acts={}
    for key,terms in {"attachment":["attachment","taquet","atache","aditamento"], "ipr":["ipr","stripping"], "expansion":["expand","expansion"], "distalization":["distalize","distalization"], "previous_new_plan":["previous plan","same cc","repost plan","new plan"]}.items():
        if any(term in t for term in terms):
            if re.search(r"\b(remove|delete|no|do not|don't|without|avoid)\b", t): acts[key]="remove/avoid"
            elif re.search(r"\b(keep|do not delete)\b", t): acts[key]="keep"
            elif "new plan" in t: acts[key]="new plan"
            elif any(x in t for x in ["previous plan","same cc","repost plan"]): acts[key]="previous plan"
            else: acts[key]="add/use"
    return acts

def _val_signature(row):
    vals=row.get('extracted_values',{}) or {}; cats=row.get('categories',[])
    pieces=[]
    for k,v in vals.items():
        if v: pieces.append(f"{k}:{v}")
    acts=detect_actions(row.get('analysis_text',''))
    for k,v in acts.items(): pieces.append(f"{k}:{v}")
    return "|".join(pieces) or normalize_text_for_matching(row.get('analysis_text',''))

def analyze_doctor_patterns(cc0_df: pd.DataFrame, ccmod_df: pd.DataFrame, cc0_mapping: Dict[str,str], ccmod_mapping: Dict[str,Optional[str]], exclusions: Optional[List[str]]=None, duplicate_policy: str="exclude_duplicate_clinical", finding_weights: Optional[Dict[str,float]]=None, exclude_preferences: bool=False) -> Dict[str,pd.DataFrame]:
    exclusions=exclusions if exclusions is not None else DEFAULT_EXCLUSIONS; weights=finding_weights or DEFAULT_FINDING_WEIGHTS
    cc0=cc0_df.copy(); ccmod=ccmod_df.copy(); cc0['_source_row']=np.arange(len(cc0))+2; ccmod['_source_row']=np.arange(len(ccmod))+2
    cc0['cc0_order_key']=cc0[cc0_mapping['order']].map(normalize_order_id); cc0['cc0_full_instruction']=cc0[cc0_mapping['instruction']].fillna('').astype(str)
    sections=cc0['cc0_full_instruction'].map(lambda text: split_cc0_sections(text, exclude_preferences=exclude_preferences)).apply(pd.Series); cc0=pd.concat([cc0.drop(columns=['cc0_full_instruction']), sections], axis=1)
    cc0['cc0_case_categories']=cc0['cc0_case_specific_instruction'].map(classify_categories); cc0['cc0_preference_categories']=cc0['cc0_preference_instruction'].map(classify_categories)
    cc0['case_specific_length']=cc0['cc0_case_specific_instruction'].str.len(); cc0['has_case_specific_instruction']=cc0['case_specific_length'].gt(0)
    ccmod['ccmod_order_key']=ccmod[ccmod_mapping['order']].map(normalize_order_id); ccmod['ccmod_iteration']=ccmod[ccmod_mapping['ccmod_number']].map(parse_ccmod_number); ccmod['ccmod_number_unparsed']=ccmod['ccmod_iteration'].isna()
    raw=ccmod[ccmod_mapping['comment']].fillna('').astype(str); cleaned=raw.map(lambda x: clean_text(x, exclusions)); ccmod['original_text']=raw; ccmod['analysis_text']=cleaned.map(lambda x:x[0]); ccmod['boilerplate_audit']=cleaned.map(lambda x:x[1])
    ccmod['normalized_comment']=ccmod['analysis_text'].map(normalize_text_for_matching); ccmod['categories']=ccmod['analysis_text'].map(classify_categories); ccmod['extracted_values']=ccmod['analysis_text'].map(extract_values); ccmod['value_signature']=ccmod.apply(_val_signature, axis=1)
    ccmod['part_category_normalized']=ccmod[ccmod_mapping.get('part_category')].map(normalize_part_category) if ccmod_mapping.get('part_category') else 'Unknown'
    if ccmod_mapping.get('pid'): ccmod['PID']=ccmod[ccmod_mapping['pid']]
    if ccmod_mapping.get('complete_time'): ccmod['complete_time_parsed']=pd.to_datetime(ccmod[ccmod_mapping['complete_time']], errors='coerce')
    dup_cols=['ccmod_order_key','ccmod_iteration','normalized_comment']
    ccmod['duplicate_clinical_comment']=ccmod.duplicated(dup_cols, keep='first')
    ccmod['exact_source_duplicate']=ccmod.duplicated([c for c in [ccmod_mapping.get('order'),ccmod_mapping.get('ccmod_number'),ccmod_mapping.get('comment')] if c], keep='first')
    if duplicate_policy=='exclude_exact_source_duplicates': ccmod_work=ccmod[~ccmod['exact_source_duplicate']].copy()
    elif duplicate_policy=='exclude_duplicate_clinical': ccmod_work=ccmod[~ccmod['duplicate_clinical_comment']].copy()
    else: ccmod_work=ccmod.copy()
    usable=ccmod_work[ccmod_work['analysis_text'].str.len()>0].copy()
    exploded=usable.explode('categories').rename(columns={'categories':'category'})
    matched_keys=set(cc0['cc0_order_key'].dropna()) & set(usable['ccmod_order_key'].dropna())
    order_stats=usable.groupby('ccmod_order_key', dropna=True).agg(ccmod_rows=('ccmod_order_key','size'), unique_ccmod_iterations=('ccmod_iteration','nunique'), min_ccmod_iteration=('ccmod_iteration','min'), max_ccmod_iteration=('ccmod_iteration','max')).reset_index()
    order_stats['reached_ccmod_2_plus']=order_stats['max_ccmod_iteration'].ge(2); order_stats['reached_ccmod_3_plus']=order_stats['max_ccmod_iteration'].ge(3); order_stats['reached_ccmod_4_plus']=order_stats['max_ccmod_iteration'].ge(4); order_stats['has_matched_ccmod']=order_stats['ccmod_order_key'].isin(matched_keys)
    cc0_orders=cc0[['cc0_order_key','cc0_full_instruction','cc0_case_specific_instruction','cc0_preference_instruction','cc0_case_categories','cc0_preference_categories','case_specific_length','has_case_specific_instruction','_source_row']].drop_duplicates('cc0_order_key')
    order_summary=cc0_orders.merge(order_stats, left_on='cc0_order_key', right_on='ccmod_order_key', how='left'); order_summary['has_ccmod_in_uploaded_file']=order_summary['cc0_order_key'].isin(set(usable['ccmod_order_key'].dropna()))
    seq_rows=[]; changes=[]
    for order, grp in usable.dropna(subset=['ccmod_order_key']).sort_values(['ccmod_order_key','ccmod_iteration']).groupby('ccmod_order_key'):
        cc0r=cc0_orders[cc0_orders['cc0_order_key']==order].head(1)
        case_cats=set(cc0r['cc0_case_categories'].iloc[0]) if not cc0r.empty else set(); pref_cats=set(cc0r['cc0_preference_categories'].iloc[0]) if not cc0r.empty else set()
        for cat, cgrp in grp.explode('categories').rename(columns={'categories':'category'}).groupby('category'):
            valid=cgrp.dropna(subset=['ccmod_iteration']).sort_values('ccmod_iteration')
            if valid.empty: continue
            iters=valid['ccmod_iteration'].astype(int).tolist(); sigs=valid['value_signature'].tolist()
            status={"present_upfront": cat in case_cats, "preference_only": cat not in case_cats and cat in pref_cats, "missing_upfront": cat not in case_cats and (min(iters)==1), "late_emerging": min(iters)>=2, "repeated_request": len(set(iters))>=2, "consecutively_repeated": any(b-a==1 for a,b in zip(sorted(set(iters)), sorted(set(iters))[1:])), "persistent_unresolved_request": len(set(iters))>=2 and len(set([s for s in sigs if s]))==1, "changed_decision": False, "added_detail": False}
            uniq=[s for s in dict.fromkeys(sigs) if s]
            status['changed_decision']=len(uniq)>1 and any(k in '|'.join(uniq) for k in ['requested_aligner_count','requested_passive_aligner_count','requested_package','attachment:','ipr:','expansion:','distalization:','previous_new_plan:','requested_stage'])
            status['added_detail']=len(uniq)>1 and not status['changed_decision']
            seq_rows.append({"order_number": order, "category": cat, "first_ccmod_iteration": min(iters), "last_ccmod_iteration": max(iters), "ccmods_with_category": len(set(iters)), "sequence": ' > '.join(map(str,iters)), "exact_comments": '\n'.join(valid['original_text'].astype(str).tolist()), **status})
            if status['changed_decision']:
                prev=None
                for _,r in valid.iterrows():
                    sig=r['value_signature']
                    if prev and sig!=prev['sig']:
                        changes.append({"order_number":order,"part_category":r.get('part_category_normalized','Unknown'),"category":cat,"earlier_ccmod_number":prev['iter'],"earlier_exact_comment":prev['comment'],"later_ccmod_number":r['ccmod_iteration'],"later_exact_comment":r['original_text'],"extracted_earlier_value":prev['sig'],"extracted_later_value":sig,"change_type":f"{cat} changed"})
                    prev={'sig':sig,'iter':r['ccmod_iteration'],'comment':r['original_text']}
    sequence=pd.DataFrame(seq_rows); changed=pd.DataFrame(changes)
    freq=exploded.groupby('category').agg(comment_count=('category','size'), unique_order_count=('ccmod_order_key','nunique'), average_first_ccmod_number=('ccmod_iteration','mean'), median_first_ccmod_number=('ccmod_iteration','median')).reset_index() if not exploded.empty else pd.DataFrame(columns=['category'])
    total_comments=max(len(usable),1); modified_orders=max(usable['ccmod_order_key'].nunique(),1)
    if not freq.empty:
        freq['pct_usable_comments']=freq['comment_count']/total_comments; freq['pct_modified_orders']=freq['unique_order_count']/modified_orders
        for pc in ['Primary','Secondary']:
            sub=exploded[exploded['part_category_normalized']==pc].groupby('category').size().rename(f'{pc}_count')
            freq=freq.merge(sub, on='category', how='left'); freq[f'{pc}_count']=freq[f'{pc}_count'].fillna(0).astype(int); denom=max((usable['part_category_normalized']==pc).sum(),1); freq[f'{pc}_pct']=freq[f'{pc}_count']/denom
        if not sequence.empty:
            rep=sequence[sequence['repeated_request']].groupby('category').size().rename('repeated_order_count'); late=sequence[sequence['late_emerging']].groupby('category').size().rename('late_emerging_order_count')
            freq=freq.merge(rep,on='category',how='left').merge(late,on='category',how='left').fillna({'repeated_order_count':0,'late_emerging_order_count':0})
    exact=usable.groupby('normalized_comment').agg(representative_original_comment=('original_text','first'), total_occurrences=('normalized_comment','size'), unique_orders=('ccmod_order_key','nunique'), category=('categories',lambda x:', '.join(sorted(set(sum([i for i in x if isinstance(i,list)], []))))), extracted_value=('value_signature','first')).reset_index().sort_values('total_occurrences', ascending=False)
    similar=exact.copy(); similar['cluster_id']=range(1,len(similar)+1)
    cc0_vs=sequence.groupby('category').agg(present_upfront=('present_upfront','sum'), preference_only=('preference_only','sum'), missing_upfront=('missing_upfront','sum'), late_emerging=('late_emerging','sum'), repeated_later_ccmods=('repeated_request','sum'), changed_decision=('changed_decision','sum')).reset_index() if not sequence.empty else pd.DataFrame()
    repeated=sequence[sequence.get('repeated_request', pd.Series(dtype=bool))].copy() if not sequence.empty else pd.DataFrame()
    late=sequence[sequence.get('late_emerging', pd.Series(dtype=bool))].copy() if not sequence.empty else pd.DataFrame()
    primary_secondary=exploded.groupby('part_category_normalized').agg(comment_count=('category','size'), unique_orders=('ccmod_order_key','nunique'), avg_comment_length=('analysis_text',lambda s:s.str.len().mean()), median_comment_length=('analysis_text',lambda s:s.str.len().median())).reset_index() if not exploded.empty else pd.DataFrame()
    coverage=pd.DataFrame([{"CC0 rows":len(cc0),"unique CC0 SO":cc0['cc0_order_key'].nunique(),"CCMod rows":len(ccmod),"usable CCMod comments after cleaning":len(usable),"unique modified orders":usable['ccmod_order_key'].nunique(),"matched modified orders":len(matched_keys),"unmatched CCMod orders":len(set(usable['ccmod_order_key'].dropna())-set(cc0['cc0_order_key'].dropna())),"SO without CCMod in uploaded data":len(set(cc0['cc0_order_key'].dropna())-set(usable['ccmod_order_key'].dropna())),"match rate":len(matched_keys)/max(usable['ccmod_order_key'].nunique(),1),"percentage SO with matched CCMod":len(matched_keys)/max(cc0['cc0_order_key'].nunique(),1),"percentage reaching CCMod 2+":order_stats['reached_ccmod_2_plus'].mean() if len(order_stats) else 0,"percentage reaching CCMod 3+":order_stats['reached_ccmod_3_plus'].mean() if len(order_stats) else 0,"maximum observed CCMod number":usable['ccmod_iteration'].max()}])
    quality=pd.DataFrame([{"check":"missing order keys","count":int(cc0['cc0_order_key'].isna().sum()+ccmod['ccmod_order_key'].isna().sum())},{"check":"duplicated CC0 SO","count":int(cc0['cc0_order_key'].duplicated().sum())},{"check":"duplicated CCMod rows","count":int(ccmod['exact_source_duplicate'].sum())},{"check":"unparsed CCMod numbers","count":int(ccmod['ccmod_number_unparsed'].sum())},{"check":"empty comments after cleaning","count":int(ccmod['analysis_text'].str.len().eq(0).sum())},{"check":"unclassified usable comments","count":int(usable['categories'].map(lambda x:x==['General or unclassified']).sum())}])
    boiler=pd.DataFrame([{"exclusion":k,"rows_modified":sum(1 for d in ccmod['boilerplate_audit'] if k in d),"occurrences_removed":sum(d.get(k,0) for d in ccmod['boilerplate_audit'])} for k in exclusions])
    findings=_build_findings(freq, sequence, exact, usable, weights)
    unmatched=pd.concat([cc0[~cc0['cc0_order_key'].isin(set(usable['ccmod_order_key'].dropna()))].assign(unmatched_type='CC0 without CCMod'), ccmod[~ccmod['ccmod_order_key'].isin(set(cc0['cc0_order_key'].dropna()))].assign(unmatched_type='CCMod without CC0')], ignore_index=True, sort=False)
    rules=pd.DataFrame([{"category":c,"keywords":"; ".join(map(str,CATEGORY_KEYWORDS.get(c,[])))} for c in ALL_CATEGORIES])
    return {"coverage":coverage,"frequent_requests":freq.sort_values('comment_count', ascending=False) if not freq.empty else freq,"exact_comments":exact,"similar_comment_clusters":similar,"cc0_vs_ccmod":cc0_vs,"repeated_requests":repeated,"late_requests":late,"changed_decisions":changed,"primary_vs_secondary":primary_secondary,"order_summary":order_summary,"order_sequences":sequence,"cc0_cleaned":cc0,"ccmod_cleaned":ccmod,"unmatched_orders":unmatched,"boilerplate_audit":boiler,"rules_used":rules,"data_quality":quality,"findings":findings,"category_rows":exploded}

def _build_findings(freq, sequence, exact, usable, weights):
    if freq is None or freq.empty: return pd.DataFrame(columns=['problem_title','evidence','scale','exact_recurring_comments','example_sequence','part_category_context','observed_issue','importance_score'])
    f=freq.copy();
    for col in ['unique_order_count','comment_count','repeated_order_count','late_emerging_order_count']:
        if col not in f: f[col]=0
    mx=lambda s: s/max(float(s.max() or 1),1)
    f['importance_score']=weights.get('unique_order_coverage',.3)*mx(f['unique_order_count'])+weights.get('comment_frequency',.2)*mx(f['comment_count'])+weights.get('repeated_request_rate',.2)*mx(f['repeated_order_count'])+weights.get('late_emerging_rate',.15)*mx(f['late_emerging_order_count'])
    rows=[]
    for _,r in f.sort_values('importance_score', ascending=False).head(4).iterrows():
        cat=r['category']; ex=exact[exact['category'].str.contains(re.escape(cat), na=False)].head(3)['representative_original_comment'].astype(str).tolist() if not exact.empty else []
        seq=sequence[sequence['category']==cat].head(1) if sequence is not None and not sequence.empty else pd.DataFrame()
        rows.append({"problem_title":f"{cat} appears repeatedly or prominently in CCMod comments","evidence":f"{int(r.get('comment_count',0))} comments; {int(r.get('unique_order_count',0))} unique orders; {float(r.get('pct_usable_comments',0)):.1%} of usable comments; {int(r.get('repeated_order_count',0))} orders repeated the request.","scale":f"{float(r.get('pct_modified_orders',0)):.1%} of modified orders in uploaded data.","exact_recurring_comments":"\n".join('“'+x+'”' for x in ex),"example_sequence":seq['exact_comments'].iloc[0] if not seq.empty else "No multi-CCMod sequence available.","part_category_context":f"Primary {int(r.get('Primary_count',0))}; Secondary {int(r.get('Secondary_count',0))} comments.","observed_issue":f"The uploaded data show {cat} requests in later CCMod comments, including repeated or late sequence occurrences where present.","importance_score":r['importance_score']})
    return pd.DataFrame(rows)
