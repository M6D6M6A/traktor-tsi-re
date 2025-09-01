# tests/test_dump_sample_to_examples.py
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import IntEnum
from pathlib import Path

import pytest

from traktor_tsi.parser import TsiParser
from traktor_tsi.xml import extract_mapping_blob


def _coerce_enums(obj):
    """Convert IntEnum (and nested structures) to plain int for stable JSON."""
    if isinstance(obj, IntEnum):
        return int(obj)
    if is_dataclass(obj):
        return {k: _coerce_enums(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _coerce_enums(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce_enums(v) for v in obj]
    return obj


def test_dump_sample_json_next_to_tsi():
    """
    If examples/sample.tsi exists, parse and save JSON as examples/sample.json
    (in-place, overwriting if it already exists). Skips cleanly if no sample.
    """
    repo_root = Path(__file__).resolve().parents[1]
    examples_dir = repo_root / "examples"
    sample_tsi = examples_dir / "sample.tsi"

    if not sample_tsi.exists():
        pytest.skip("examples/sample.tsi not present; add a small exported TSI to run this test.")

    # Extract blob + parse mappings
    blob = extract_mapping_blob(str(sample_tsi))
    rows = TsiParser(cast_enums=True).parse(blob)

    # Serialize -> examples/sample.json (next to sample.tsi)
    data = _coerce_enums([asdict(r) for r in rows])
    out_path = sample_tsi.with_suffix(".json")
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Basic sanity checks
    assert out_path.exists()
    parsed = json.loads(out_path.read_text(encoding="utf-8"))
    assert isinstance(parsed, list)
    if parsed:
        r0 = parsed[0]
        for key in ("traktor_control_id", "mapping_type", "midi_binding_id"):
            assert key in r0
