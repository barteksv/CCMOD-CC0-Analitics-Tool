import json
from pathlib import Path

from analyzer.calibration import (
    get_memory_stats,
    get_topic_keywords,
    load_calibration_memory,
)


def test_load_calibration_memory_includes_bundled_defaults(tmp_path: Path):
    default_path = tmp_path / "default_calibration_memory.json"
    default_path.write_text(
        json.dumps(
            {
                "version": 3,
                "ccmod": {"default phrase": {"topics": "staging"}},
                "cc0": {},
                "global_rows": {"ccmod": {"4": {"complexity": "high"}}, "cc0": {}},
                "custom_topics": {"posterior_crossbite": ["posterior crossbite"]},
            }
        ),
        encoding="utf-8",
    )

    memory = load_calibration_memory(
        path=tmp_path / "missing_local.json", default_path=default_path
    )

    assert memory["ccmod"]["default phrase"]["topics"] == "staging"
    assert memory["global_rows"]["ccmod"]["4"]["complexity"] == "high"
    assert get_memory_stats(memory)["custom_topics"] == 1
    assert "posterior crossbite" in get_topic_keywords(memory)["posterior_crossbite"]


def test_local_calibration_overrides_bundled_defaults(tmp_path: Path):
    default_path = tmp_path / "default_calibration_memory.json"
    local_path = tmp_path / "calibration_memory.json"
    default_path.write_text(
        json.dumps(
            {
                "ccmod": {"same phrase": {"complexity": "low"}},
                "custom_topics": {"topic": ["old"]},
            }
        ),
        encoding="utf-8",
    )
    local_path.write_text(
        json.dumps(
            {
                "ccmod": {"same phrase": {"complexity": "high"}},
                "custom_topics": {"topic": ["new"]},
            }
        ),
        encoding="utf-8",
    )

    memory = load_calibration_memory(path=local_path, default_path=default_path)

    assert memory["ccmod"]["same phrase"]["complexity"] == "high"
    assert memory["custom_topics"]["topic"] == ["new"]
