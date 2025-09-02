from __future__ import annotations

from typing import Iterable, List, Tuple, Optional

from .enums import MappingType, InteractionMode
from .models import MappingRow


Issue = Tuple[str, str]  # (severity, message)


def validate_rows(rows: Iterable[MappingRow]) -> List[Issue]:
    issues: List[Issue] = []

    for i, r in enumerate(rows):
        ctx = f"[row {i} ctrl={r.traktor_control_id} note={r.midi_note}]"

        # NOTE numbers must be 0..127 if present
        if (r.midi_event == "NOTE") and (r.midi_number is not None):
            if not (0 <= r.midi_number <= 127):
                issues.append(("error", f"{ctx} NOTE number out of range: {r.midi_number}"))

        # LED tail on IN mappings is unusual but possible; warn only if fields look half-garbage
        if (r.mapping_type == MappingType.IN) if isinstance(r.mapping_type, MappingType) else (r.mapping_type == 0):
            if any(v is not None for v in (r.led_min_controller, r.led_max_controller)) and r.led_min_midi is None:
                issues.append(("warn", f"{ctx} LED floats present on IN mapping without MIDI min/max"))

        # set_value_to is only meaningful in DIRECT
        if (r.set_value_to is not None) and (r.interaction_mode not in (InteractionMode.DIRECT, 3)):
            issues.append(("info", f"{ctx} set_value_to set but mode is not DIRECT"))

        # Deck scope should be 0..3 or -1 (device target)
        if r.deck_scope is not None:
            try:
                v = int(r.deck_scope)
                if v not in (-1, 0, 1, 2, 3):
                    issues.append(("warn", f"{ctx} unusual deck_scope: {v}"))
            except Exception:
                pass

    return issues
