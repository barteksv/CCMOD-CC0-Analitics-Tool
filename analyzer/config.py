"""
Configuration for the comment and instruction analysis.

This module exposes constants and mappings used throughout the
application. It defines default phrases to exclude when cleaning
comments, language options, topic classification keywords, and
complexity thresholds for CCMod comments and CC0 instructions.

The configuration is separated from the analysis logic so that
defaults can be adjusted in a single place. Users can extend
or override these values via the Streamlit UI by providing
custom exclusion phrases.
"""

from typing import Dict, List

# Default phrases to remove from comments. These include
# boilerplate messages that are not clinically meaningful.
DEFAULT_EXCLUSION_PHRASES: List[str] = [
    # ClinCheck update routing note
    "<<<ATTENTION!!! This is Clincheck Live Update case! If doctor is asking to repost any previous treatment plans, please route this case to Data Control Team>>>",
    # French boilerplate variants
    "Laisser tel quel : des contacts occlusaux inter arcades importants sont présents",
    "Leave as is: Heavy Occlusal Inter-arch contacts are present",
    "Fix for Me: Heavy Occlusal Inter-arch contacts are present",
    # Italian and Spanish variants provided by the user
    "Sistema per me: sono presenti contatti occlusali stretti interarcata",
    "Dejar tal cual: hay contactos interarcada con mucha oclusión",
    "Arreglar por mí: hay contactos interarcada con mucha oclusión",
]

# Tags/markers used in CC0 initial instruction files that should be
# stripped from the instruction text before analysis. These tags
# describe form sections and are not part of the doctor's clinical
# instructions.
INSTRUCTION_LABELS: List[str] = [
    "[FormInstructionsUpperArch:]",
    "[FormInstructionsLowerArch:]",
    "[PreferenceInstrucions:]",
    "[PreferenceInstructions:]",
    "[FormInstructions:]",
    "[FormInstructionsBothArches:]",
]

# Supported language options for the UI. The analysis itself is not
# language‑specific—keywords across languages are defined below.
LANGUAGE_OPTIONS: List[str] = ["Auto", "French", "Spanish", "English", "Mixed"]

# Keyword lists for each clinical topic. These keywords are used
# for simple pattern matching against cleaned comments or
# instructions. They cover common words in French, Spanish and English.
TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "attachments": [
        "attachment", "attachments", "attachement", "attachements", "taquet", "taquets",
        "atach", "ataches", "aditamento", "aditamentos", "compensador", "compensadores",
    ],
    "ipr": [
        "ipr", "stripping", "interproximal", "reduction interproximale",
        "reducción interproximal", "desgaste", "separation", "séparation", "separación",
        "separaciones", "espace", "espaces", "espacio", "espacios", "diastema",
        "diastemas", "gap", "gaps", "spacing", "fermer les espaces", "cerrar espacio",
        "abrir espacio",
    ],
    "movements": [
        "alignement", "alineación", "align", "aligner", "alignez", "alinear", "nivelar",
        "rotation", "rotación", "rotar", "torque", "distal", "distalizar", "distalisation",
        "distalización", "mesial", "mesializar", "intrusion", "intrusión", "intruir",
        "extrusion", "extrusión", "extruir", "expansion", "expansión", "expandir",
        "vestibular", "lingual", "palatin", "palatino", "palatinizar", "protrusion",
        "retrusion", "mover", "movimiento", "movimientos", "correction", "corregir",
        "quadrant", "arcade", "arcada", "racine", "raíz", "raíces", "root",
    ],
    "occlusion": [
        "occlusion", "occlusal", "occlusaux", "oclusal", "oclusión", "oclusales",
        "contacts", "contact", "contactos", "mordida", "bite", "overbite", "overjet",
        "sobremordida", "resalte", "classe", "clase", "class", "molaire", "molar",
        "canine", "canino", "canina", "premature", "prematuro", "open bite", "deep bite",
        "béance", "cerrar mordida", "abrir mordida",
    ],
    "staging": [
        "aligneur", "aligneurs", "alineador", "alineadores", "aligner", "aligners",
        "stage", "stages", "étape", "étapes", "etapa", "etapas", "phase", "phases",
        "passif", "passifs", "passive", "pasivo", "pasivos", "pasiva", "pasivas",
        "sequence", "sequencing", "secuencia", "secuenciar", "primer aligneur",
        "primer alineador", "desde el primer", "fin de traitement", "final de tratamiento",
    ],
    "auxiliaries": [
        "bite ramp", "bite ramps", "rampa", "rampas", "precision cut", "precision cuts",
        "cutout", "cutouts", "recorte", "recortes", "hook", "hooks", "gancho", "ganchos",
        "button", "buttons", "bouton", "boutons", "botón", "botones", "elastic",
        "elastics", "élastique", "élastiques", "elástico", "elásticos", "power ridge",
        "pontic", "pontique", "póntico", "chainette", "chaîne virtuelle", "cadena virtual",
        "barre", "barra", "wing", "wings",
    ],
    "final_setup": [
        "esthetic", "esthétique", "aesthetic", "estética", "estético", "sourire", "sonrisa",
        "smile", "symétrie", "simetría", "symmetry", "ligne médiane", "línea media", "midline",
        "milieu", "final", "finition", "acabado", "detail", "detailing", "incisal",
        "gingival", "plano oclusal", "plan occlusal",
    ],
    "doctor_preference": [
        "preference", "preferences", "préférence", "protocolo", "protocole", "protocol",
        "please", "svp", "s'il vous plaît", "por favor", "merci", "gracias", "according to my protocol",
        "selon mon protocole", "según mi protocolo",
    ],
}

# Keywords that suggest the doctor is requesting a new treatment plan. These
# phrases are used primarily for CCMod comments analysis. They are kept
# separate to avoid diluting other topic counts.
NEW_PLAN_KEYWORDS: List[str] = [
    "nuevo plan", "plan nuevo", "nuevo plan de tratamiento", "nuevo ClinCheck",
    "ClinCheck nuevo", "nuevo setup", "nuevo tratamiento", "rehacer plan",
    "rehacer el plan", "rehacer ClinCheck", "volver a hacer plan", "crear nuevo plan",
    "generar nuevo plan", "necesito nuevo plan", "quiero nuevo plan", "replanificar",
    "replanificación", "new treatment plan", "new plan", "redo plan", "redo ClinCheck",
    "recreate plan", "make new plan", "nuovo piano", "nuovo piano di trattamento",
]

# Complexity thresholds for CCMod comments. Keys define categories and
# inner dicts specify maxima for length, topics and clauses.
CCMOD_COMPLEXITY_THRESHOLDS = {
    "low": {
        "max_length": 80,
        "max_topics": 1,
        "max_clauses": 1,
    },
    "medium": {
        "max_length": 250,
        "max_topics": 2,
        "max_clauses": 2,
    },
    # Anything above the medium thresholds is high complexity.
}

# Complexity thresholds for CC0 instructions. Keys define categories and
# inner dicts specify maxima for length, topics, sections and lines.
CC0_COMPLEXITY_THRESHOLDS = {
    "low": {
        "max_length": 100,
        "max_topics": 1,
        "max_sections": 1,
        "max_lines": 2,
    },
    "medium": {
        "max_length": 300,
        "max_topics": 2,
        "max_sections": 2,
        "max_lines": 5,
    },
    # Anything above the medium thresholds is high complexity.
}