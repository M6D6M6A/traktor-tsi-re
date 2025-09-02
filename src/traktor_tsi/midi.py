from __future__ import annotations

import re
from typing import Optional, Tuple

# e.g. F4, C#3, G-1 (Traktor often uses negative octaves)
_NOTE_NAME_RE = re.compile(r"^([A-Ga-g])([#b])?(-?\d+)$")

# Semitone map relative to C
_SEMITONE = {
    "C": 0, "C#": 1, "Db": 1,
    "D": 2, "D#": 3, "Eb": 3,
    "E": 4,
    "F": 5, "F#": 6, "Gb": 6,
    "G": 7, "G#": 8, "Ab": 8,
    "A": 9, "A#": 10, "Bb": 10,
    "B": 11,
}

def _note_name_to_number(note_name: str) -> Optional[int]:
    """
    Convert musical note like 'F4', 'C#3', 'G-1' to a MIDI number using C-1 = 0.
    Formula: number = (octave + 1) * 12 + semitone
    """
    m = _NOTE_NAME_RE.match(note_name)
    if not m:
        return None
    letter = m.group(1).upper()
    accidental = m.group(2) or ""
    octave = int(m.group(3))
    key = letter + accidental
    if key not in _SEMITONE:
        return None
    semitone = _SEMITONE[key]
    return (octave + 1) * 12 + semitone  # C-1 -> 0

def parse_binding_name(name: Optional[str]) -> Tuple[Optional[int], Optional[str], Optional[int], Optional[str]]:
    """
    Parses binding strings like:
        "Ch07.CC.064"   -> (7, "CC", 64, None)
        "Ch05.Note.C#3" -> (5, "NOTE", 49, "C#3")  # number computed with C-1 = 0
        "Ch01.Note.0B"  -> (1, "NOTE", 11, None)   # hex/decimal if not a musical name

    Returns: (channel, event, number, note_name)
    """
    if not name or not name.startswith("Ch"):
        return None, None, None, None

    parts = name.split(".")
    if len(parts) < 3:
        return None, None, None, None

    # Channel
    try:
        ch = int(parts[0][2:])
    except ValueError:
        ch = None

    event_raw = parts[1].strip().upper()
    event = "NOTE" if event_raw == "NOTE" else ("CC" if event_raw in ("CC", "CONTROL") else event_raw)

    tail = parts[2].strip()

    if event == "NOTE":
        # Prefer musical note names like F4/C#3/G-1
        num_from_name = _note_name_to_number(tail)
        if num_from_name is not None:
            return ch, "NOTE", num_from_name, tail  # keep both number + name

        # Otherwise parse numeric (dec or hex)
        try:
            return ch, "NOTE", int(tail), None
        except ValueError:
            try:
                return ch, "NOTE", int(tail, 16), None
            except ValueError:
                return ch, "NOTE", None, tail  # last resort

    # CC: parse numeric (dec -> hex fallback)
    try:
        return ch, "CC", int(tail), None
    except ValueError:
        try:
            return ch, "CC", int(tail, 16), None
        except ValueError:
            return ch, "CC", None, tail
