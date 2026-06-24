import pandas as pd
from analyzer.cc0_analyzer import analyse_cc0_dataframe

def test_cc0_analyzer_excludes_preference_instruction_tail():
    df=pd.DataFrame({'Instruction':['[FormInstructionsUpperArch:] -\n[FormInstructionsLowerArch:] - lower anterior IPR max 0,2mm\n[PreferenceInstrucions:] Please review preferences attachments']})
    res=analyse_cc0_dataframe(df, 'Instruction', exclude_preferences=True)
    cleaned=res.row_level['cleaned_instruction'].iloc[0]
    assert 'Please review preferences' not in cleaned
    assert 'attachments' not in cleaned
    assert 'lower anterior IPR max 0,2mm' in cleaned
