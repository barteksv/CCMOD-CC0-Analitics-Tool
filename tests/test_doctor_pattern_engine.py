import io
import pandas as pd
from services.doctor_pattern_export import build_doctor_pattern_excel, build_missing_upfront_evidence_excel
from services.doctor_pattern_engine import (
    analyze_doctor_patterns, clean_text, extract_values, normalize_order_id,
    normalize_part_category, parse_ccmod_number, split_cc0_sections, classify_categories
)

def test_order_id_normalization():
    assert normalize_order_id(' 00123 ') == '00123'
    assert normalize_order_id('123.0') == '123'
    assert normalize_order_id('nan') is None

def test_ccmod_number_parsing():
    assert parse_ccmod_number('CCMod 2') == 2
    assert parse_ccmod_number('Modification 4') == 4
    assert parse_ccmod_number('abc') is None

def test_boilerplate_removal_keeps_clinical_text():
    txt='This is ClinCheck Live Update case please 14 aligners'
    cleaned,audit=clean_text(txt)
    assert 'live update' not in cleaned.lower()
    assert '14 aligners' in cleaned.lower()
    assert audit

def test_structured_cc0_section_extraction():
    s='Case note [PreferenceInstrucions:] Always align [FormInstructionsUpperArch:] expand upper [FormInstructionsLowerArch:] align lower'
    out=split_cc0_sections(s)
    assert 'Always align' in out['cc0_preference_instruction']
    assert 'expand upper' in out['cc0_upper_arch_instruction']
    assert 'align lower' in out['cc0_case_specific_instruction']

def test_value_extractions():
    vals=extract_values('add 10 passive aligners and please 14 aligners, switch to Lite, stage 12, IPR 0.4')
    assert vals['requested_passive_aligner_count'] == [10]
    assert vals['requested_aligner_count'] == [14]
    assert vals['requested_package'] == ['lite']
    assert vals['requested_stage'] == [12]
    assert vals['requested_ipr_value'] == [0.4]

def test_primary_secondary_normalization():
    assert normalize_part_category('PRIMARY Case') == 'Primary'
    assert normalize_part_category('secondary') == 'Secondary'

def test_multilingual_classification():
    assert 'Aligner quantity / active aligners' in classify_categories('14 aligneurs')
    assert 'Aligner quantity / active aligners' in classify_categories('20 alineadores')
    assert 'New treatment plan' in classify_categories('nuevo plan')

def _sample_result():
    cc0=pd.DataFrame({'SO':['1001','1002','1003'], 'Instruction':['Improve alignment','[PreferenceInstructions:] use attachments','No changes']})
    ccmod=pd.DataFrame({'order_number':['1001','1001','1001','1002','9999','1001','1001'], 'CCMod number':['CCMod 1','CCMod 2','CCMod 3','1','bad','1','2'], 'COMMENT':['please 14 aligners thanks','14 aligners please','Please 20 aligners','remove attachments','IPR 0.4','add IPR','remove IPR'], 'part_category':['Primary','Primary','Primary','Secondary','Primary','Primary','Primary']})
    return analyze_doctor_patterns(cc0, ccmod, {'order':'SO','instruction':'Instruction'}, {'order':'order_number','ccmod_number':'CCMod number','comment':'COMMENT','part_category':'part_category'}, duplicate_policy='keep_all_rows')

def test_repeated_late_changed_and_unmatched_order_handling():
    res=_sample_result(); seq=res['order_sequences']
    align=seq[(seq.order_number=='1001') & (seq.category=='Aligner quantity / active aligners')].iloc[0]
    assert align.first_ccmod_iteration == 1
    assert align.missing_upfront is True or align.missing_upfront == True
    assert align.repeated_request is True or align.repeated_request == True
    assert align.changed_decision is True or align.changed_decision == True
    assert '1003' in set(res['order_summary'].loc[~res['order_summary'].has_ccmod_in_uploaded_file,'cc0_order_key'])
    assert '9999' in set(res['unmatched_orders']['ccmod_order_key'].dropna())

def test_exact_repeated_request_detection():
    res=_sample_result()
    rep=res['repeated_requests']
    assert 'Aligner quantity / active aligners' in set(rep['category'])

def test_late_emerging_request_detection():
    cc0=pd.DataFrame({'SO':['1'], 'Instruction':['alignment']})
    ccmod=pd.DataFrame({'order_number':['1'], 'CCMod number':['2'], 'COMMENT':['add attachments'], 'part_category':['Primary']})
    res=analyze_doctor_patterns(cc0, ccmod, {'order':'SO','instruction':'Instruction'}, {'order':'order_number','ccmod_number':'CCMod number','comment':'COMMENT','part_category':'part_category'})
    assert res['late_requests']['late_emerging'].iloc[0] == True

def test_add_remove_attachment_and_ipr_detection():
    res=_sample_result(); ch=res['changed_decisions']
    assert any(ch['category'].str.contains('IPR', na=False))
    cc0=pd.DataFrame({'SO':['1'], 'Instruction':['']})
    cm=pd.DataFrame({'order_number':['1','1'], 'CCMod number':[1,2], 'COMMENT':['add attachments','remove attachments']})
    res2=analyze_doctor_patterns(cc0, cm, {'order':'SO','instruction':'Instruction'}, {'order':'order_number','ccmod_number':'CCMod number','comment':'COMMENT'})
    assert any(res2['changed_decisions']['category'].str.contains('Attachments', na=False))

def test_exclude_preferences_removes_marker_and_following_text():
    s='[FormInstructionsUpperArch:] - [FormInstructionsLowerArch:] lower anterior IPR [PreferenceInstrucions:] global attachments preference'
    out=split_cc0_sections(s, exclude_preferences=True)
    assert 'global attachments preference' not in out['cc0_full_instruction']
    assert out['cc0_preference_instruction'] == ''
    assert 'lower anterior IPR' in out['cc0_case_specific_instruction']


def test_pattern_analysis_can_exclude_cc0_preferences():
    cc0=pd.DataFrame({'SO':['1'], 'Instruction':['[FormInstructionsLowerArch:] align lower [PreferenceInstrucions:] use attachments']})
    ccmod=pd.DataFrame({'order_number':['1'], 'CCMod number':[1], 'COMMENT':['remove attachments']})
    res=analyze_doctor_patterns(cc0, ccmod, {'order':'SO','instruction':'Instruction'}, {'order':'order_number','ccmod_number':'CCMod number','comment':'COMMENT'}, exclude_preferences=True)
    row=res['cc0_cleaned'].iloc[0]
    assert row['cc0_preference_instruction'] == ''
    assert 'attachments' not in row['cc0_full_instruction'].lower()

def test_doctor_pattern_prefers_already_cleaned_ccmod_comments():
    cc0 = pd.DataFrame({'SO': ['1'], 'Instruction': ['']})
    ccmod = pd.DataFrame({
        'order_number': ['1'],
        'CCMod number': [1],
        'COMMENT': ['remove attachments'],
        'COMMENT cleaned': ['14 aligners'],
    })
    res = analyze_doctor_patterns(
        cc0,
        ccmod,
        {'order': 'SO', 'instruction': 'Instruction'},
        {'order': 'order_number', 'ccmod_number': 'CCMod number', 'comment': 'COMMENT'},
    )
    row = res['ccmod_cleaned'].iloc[0]
    assert row['original_text'] == '14 aligners'
    assert row['analysis_text'] == '14 aligners'
    assert 'Aligner quantity / active aligners' in row['categories']
    assert 'Attachments' not in row['categories']


def test_calibrated_bite_ramps_do_not_imply_occlusion():
    cats = classify_categories('please give biteramps on 13,23')
    assert 'Bite ramps' in cats
    assert 'Occlusion / bite / contacts' not in cats


def test_active_aligner_quantity_does_not_imply_tooth_movement():
    cats = classify_categories('use max 25 active aligners')
    assert 'Aligner quantity / active aligners' in cats
    assert 'Tooth movement / alignment' not in cats


def test_ipr_timing_phrases_imply_staging():
    cats = classify_categories('IPR upper front as late as possible')
    assert 'IPR / stripping / spacing' in cats
    assert 'Staging / sequencing' in cats

    cats = classify_categories('place bite ramps on 13,23 - Do IPR after alignment')
    assert 'Bite ramps' in cats
    assert 'IPR / stripping / spacing' in cats
    assert 'Staging / sequencing' in cats
    assert 'Occlusion / bite / contacts' not in cats


def test_procline_first_and_intrude_retract_imply_sequencing_and_torque():
    cats = classify_categories('please procline first upper and lower incisors, intrude and retract')
    assert 'Rotation / torque / intrusion / extrusion' in cats
    assert 'Staging / sequencing' in cats


def test_deep_bite_correction_timing_does_not_imply_occlusion():
    cats = classify_categories('please procline first, intrude and retact during the deep bite correction to keep the inclination ideal')
    assert 'Rotation / torque / intrusion / extrusion' in cats
    assert 'Staging / sequencing' in cats
    assert 'Occlusion / bite / contacts' not in cats


def test_movement_during_distalization_and_after_proclination_imply_staging():
    cats = classify_categories('please procline buccal crowntip upper and lower during distalization. Intrude lower incisors after proclination')
    assert 'Distalization / mesialization' in cats
    assert 'Rotation / torque / intrusion / extrusion' in cats
    assert 'Staging / sequencing' in cats

def test_missing_upfront_evidence_contains_auditable_cc0_and_ccmod_text():
    cc0 = pd.DataFrame({
        'SO': ['1', '2', '3'],
        'Instruction': [
            '[FormInstructionsUpperArch:] align teeth',
            '[FormInstructionsUpperArch:] align teeth [PreferenceInstructions:] use attachments',
            '[FormInstructionsUpperArch:] add attachments',
        ],
    })
    ccmod = pd.DataFrame({
        'order_number': ['1', '2', '3'],
        'CCMod number': [1, 1, 1],
        'COMMENT': ['add attachments', 'add attachments', 'add attachments'],
    })

    res = analyze_doctor_patterns(
        cc0,
        ccmod,
        {'order': 'SO', 'instruction': 'Instruction'},
        {'order': 'order_number', 'ccmod_number': 'CCMod number', 'comment': 'COMMENT'},
        duplicate_policy='keep_all_rows',
    )

    evidence = res['missing_upfront_evidence']
    assert set(evidence['order_number']) == {'1', '2'}
    assert set(evidence['missing_upfront_status']) == {'missing_from_cc0', 'preference_only_not_upfront'}
    order_1 = evidence[evidence['order_number'] == '1'].iloc[0]
    assert order_1['category'] == 'Attachments / retention'
    assert order_1['cc0_case_specific_instruction'] == 'align teeth'
    assert order_1['ccmod_exact_comment'] == 'add attachments'
    assert order_1['present_in_cc0_case_specific'] is False or order_1['present_in_cc0_case_specific'] == False
    order_2 = evidence[evidence['order_number'] == '2'].iloc[0]
    assert order_2['present_in_cc0_preference_only'] is True or order_2['present_in_cc0_preference_only'] == True


def test_missing_upfront_evidence_excel_export_is_xlsx_workbook():
    evidence = pd.DataFrame({
        'order_number': ['1'],
        'category': ['Attachments / retention'],
        'cc0_case_specific_instruction': ['align teeth'],
        'ccmod_exact_comment': ['add attachments'],
    })

    workbook = build_missing_upfront_evidence_excel(evidence)
    exported = pd.read_excel(io.BytesIO(workbook), sheet_name='Missing_Upfront_Evidence', engine='openpyxl')

    assert exported.loc[0, 'order_number'] == 1
    assert exported.loc[0, 'category'] == 'Attachments / retention'
    assert exported.loc[0, 'ccmod_exact_comment'] == 'add attachments'


def test_excel_exports_handle_columns_containing_only_null_values():
    null_data = pd.DataFrame({'empty_value': [None, pd.NA], 'comment': [None, pd.NA]})

    full_workbook = build_doctor_pattern_excel({'findings': null_data})
    evidence_workbook = build_missing_upfront_evidence_excel(null_data)

    full_export = pd.read_excel(io.BytesIO(full_workbook), sheet_name='Executive_Summary', engine='openpyxl')
    evidence_export = pd.read_excel(
        io.BytesIO(evidence_workbook), sheet_name='Missing_Upfront_Evidence', engine='openpyxl'
    )
    assert list(full_export.columns) == ['empty_value', 'comment']
    assert list(evidence_export.columns) == ['empty_value', 'comment']
