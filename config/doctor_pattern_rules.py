"""Editable rule dictionaries for Doctor Pattern Analysis."""
CATEGORY_KEYWORDS = {
    "Aligner quantity / active aligners": [r"\b\d+\s*(?:active\s*)?(?:aligners?|aligneurs?|alineadores?)\b", "number of aligners", "slow down movements", "first aligners"],
    "Passive aligners": [r"\b\d+\s*passive?s?\s*(?:aligners?|trays?|aligneurs?|alineadores?)\b", "passive aligner", "passive tray", "aligneurs passifs", "alineadores pasivos"],
    "Same / previous plan / repost": ["same treatment", "same traitement", "same cc", "same as cc", "exactly the same", "repost cc", "repost plan", "previous plan", "copy cc", "same as patient"],
    "Tooth movement / alignment": ["align", "alignment", "movement", "mouvement", "movimiento", "round trip", "overcorrection"],
    "Staging / sequencing": ["stage", "staging", "sequence", "sequential", "one by one", "not en masse", "etape", "etapa"],
    "IPR / stripping / spacing": ["ipr", "stripping", "interproximal reduction", "open space", "close space", "diastema", "spacing", "separation", "espacio"],
    "Attachments / retention": ["attachment", "optimized attachment", "retention attachment", "remove attachment", "keep attachment", "do not delete attachment", "taquet", "atache", "aditamento"],
    "Elastics / cutouts / buttons / hooks": ["cutout", "cut out", "button", "hook", "elastic", "precision cut", "power ridge"],
    "Bite ramps": ["bite ramp", "bite ramps", "ramps", "bite plane"],
    "Occlusion / bite / contacts": ["occlusion", "occlusal", "bite", "contacts", "inter-arch", "interarch", "oclusion"],
    "Expansion / arch form": ["expand", "expansion", "arch form", "forme d'arcade", "expansion"],
    "Distalization / mesialization": ["distalize", "distalization", "mesialize", "mesialization", "distaliser", "mesialiser"],
    "Rotation / torque / intrusion / extrusion": ["rotation", "torque", "intrusion", "extrusion", "rotate", "intrude", "extrude"],
    "Surgical workflow / surgical jump": ["surgical jump", "surgery", "surgical treatment", "mandibular advancement", "transversal surgical jump", "chirurgical"],
    "Package / product change": ["switch to lite", "switch to moderate", "switch to full", "full package", "change package", "product change", "package lite", "package moderate", "package full"],
    "New treatment plan": ["new plan", "new treatment plan", "new clincheck", "redo plan", "recreate plan", "make a new plan", "nuevo plan", "nouveau plan"],
    "New scan / scan replacement": ["connect the new scan", "use the new scan", "new scan", "rescan", "nouveau scan", "scan replacement"],
    "Extraction / tooth removal": ["extraction", "extract", "remove tooth", "tooth removal", "exodoncia"],
    "Aesthetics / final outcome": ["aesthetic", "esthetic", "final outcome", "smile", "appearance", "estetica"],
    "Midline / symmetry": ["midline", "symmetry", "symetr", "linea media"],
    "Pontic / missing tooth": ["pontic", "missing tooth", "missing teeth", "tooth missing"],
}
ALL_CATEGORIES = list(CATEGORY_KEYWORDS) + ["General or unclassified"]
DEFAULT_EXCLUSIONS = [
"<<<ATTENTION!!! This is Clincheck Live Update case! If doctor is asking to repost any previous treatment plans, please route this case to Data Control Team>>>",
"This is ClinCheck Live Update case",
"If doctor is asking to repost any previous treatment plans, please route this case to Data Control Team",
"This plan was cloned from the history",
"Laisser tel quel : des contacts occlusaux inter arcades importants sont présents",
"Leave as is: Heavy Occlusal Inter-arch contacts are present",
"Fix for Me: Heavy Occlusal Inter-arch contacts are present",
"Sistema per me: sono presenti contatti occlusali stretti interarcata",
"Dejar tal cual: hay contactos interarcada con mucha oclusión",
"Arreglar por mí: hay contactos interarcada con mucha oclusión",
]
DEFAULT_FINDING_WEIGHTS = {"unique_order_coverage": .30, "comment_frequency": .20, "repeated_request_rate": .20, "late_emerging_rate": .15, "changed_decision_rate": .10, "avg_max_ccmod": .05}
