from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, is_dataclass
from enum import IntEnum
from typing import Any, Dict, List

from .parser import TsiParser
from .xml import extract_mapping_blob


def _coerce_enums(obj: Any) -> Any:
    """Convert IntEnum (and nested structures) to plain int for stable CSV/JSON."""
    if isinstance(obj, IntEnum):
        return int(obj)
    if is_dataclass(obj):
        return {k: _coerce_enums(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _coerce_enums(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce_enums(v) for v in obj]
    return obj


def _dump_json(rows, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_coerce_enums(rows), f, indent=2, ensure_ascii=False)


def _dump_csv(rows, path: str) -> None:
    # Coerce to primitives first
    rows_p = [_coerce_enums(r) for r in rows]
    if rows_p:
        fieldnames = list(rows_p[0].keys())
    else:
        fieldnames = [
            "device_name",
            "device_target",
            "mapping_type",
            "traktor_control_id",
            "midi_binding_id",
            "midi_note",
            "controller_type",
            "interaction_mode",
            "deck_scope",
            "auto_repeat",
            "invert",
            "soft_takeover",
            "rotary_sensitivity",
            "rotary_acceleration",
            "set_value_to",
            "mod1_id",
            "mod1_val",
            "mod2_id",
            "mod2_val",
            "led_min_controller",
            "led_max_controller",
            "led_min_midi",
            "led_max_midi",
            "led_invert",
            "led_blend",
            "resolution_raw",
            "comment",
        ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows_p:
            w.writerow(r)


def cmd_dump(args: argparse.Namespace) -> None:
    blob = extract_mapping_blob(args.tsi)
    rows = TsiParser(cast_enums=True).parse(blob)   # enums enabled
    if args.json:
        _dump_json([asdict(r) for r in rows], args.json)
    if args.csv:
        _dump_csv([asdict(r) for r in rows], args.csv)
    if not args.json and not args.csv:
        print(json.dumps(_coerce_enums([asdict(r) for r in rows]), indent=2, ensure_ascii=False))
