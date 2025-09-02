from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .enums import (
    ControllerType,
    InteractionMode,
    MappingResolution,
    MappingTargetDeck,
    MappingType,
    MidiEncoderMode,
)


@dataclass
class MappingRow:
    """
    High-level mapping row extracted from the TSI binary frames.

    Notes
    -----
    - Enum-typed fields use IntEnum subclasses (still behave like ints).
    - *_raw fields preserve original integers/bytes for diagnostics.
    - For NOTE bindings we include both a computed MIDI number (C-1 = 0)
      and the human-friendly note name when applicable.
    """

    # --- REQUIRED (non-default) fields MUST come first ---
    device_name: str
    device_target: int
    traktor_control_id: int
    midi_binding_id: int

    # --- Optional / defaulted fields below ---

    # Device name raw bytes (UTF-16BE) as hex for debugging
    device_name_raw_hex: Optional[str] = None

    # CMAI header (mapping direction) — may be unknown
    mapping_type: Optional[MappingType] = None

    # MIDI binding name (from DCBM) + raw bytes
    midi_note: Optional[str] = None
    midi_note_raw_hex: Optional[str] = None

    # Parsed from binding string (if available)
    midi_channel: Optional[int] = None                  # 1..16
    midi_event: Optional[str] = None                    # "NOTE" | "CC"
    midi_number: Optional[int] = None                   # 0..127 for NOTE/CC
    midi_note_name: Optional[str] = None                # e.g. "C#3" (for NOTE)

    # Enriched from DDDC (MIDI definitions), if available
    midi_encoder_mode: Optional[MidiEncoderMode] = None
    midi_default_velocity: Optional[float] = None
    midi_control_id: Optional[int] = None               # NI control id or -1/None

    # CMAD settings
    controller_type: Optional[ControllerType] = None    # 0=Button,1=Fader/Knob,2=Encoder,65535=LED
    interaction_mode: Optional[InteractionMode] = None  # 1..8 (Toggle..Output)
    deck_scope: Optional[MappingTargetDeck] = None      # includes -1 (device target)
    auto_repeat: Optional[int] = None
    invert: Optional[int] = None
    soft_takeover: Optional[int] = None

    rotary_sensitivity: Optional[float] = None
    rotary_acceleration: Optional[float] = None
    set_value_to: Optional[float] = None                # only meaningful in DIRECT mode

    mod1_id: Optional[int] = None
    mod1_val: Optional[int] = None
    mod2_id: Optional[int] = None
    mod2_val: Optional[int] = None

    # LED/meter ranges (outputs)
    led_min_controller: Optional[float] = None
    led_max_controller: Optional[float] = None
    led_min_midi: Optional[int] = None
    led_max_midi: Optional[int] = None
    led_invert: Optional[int] = None
    led_blend: Optional[int] = None

    # DWORD that maps to specific float semantics; kept as enum for fidelity
    resolution_raw: Optional[MappingResolution] = None

    # Free-form comment + raw bytes (UTF-16BE hex)
    comment: Optional[str] = None
    comment_raw_hex: Optional[str] = None

    # Raw integer fallbacks for unknown enum values / diagnostics
    mapping_type_raw: Optional[int] = None
    controller_type_raw: Optional[int] = None
    interaction_mode_raw: Optional[int] = None
    deck_scope_raw: Optional[int] = None
    resolution_dword: Optional[int] = None              # raw DWORD for resolution
