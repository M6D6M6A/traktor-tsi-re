from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from .enums import (
    ControllerType,
    InteractionMode,
    MappingResolution,
    MappingTargetDeck,
    MappingType,
)


IntOrEnum = Union[int, ControllerType, InteractionMode, MappingResolution, MappingTargetDeck, MappingType]


@dataclass
class MappingRow:
    """
    High-level mapping row extracted from the TSI binary frames.

    NOTE:
      - Enum fields are typed as their IntEnum classes.
      - Because IntEnum derives from int, they compare/serialize like ints.
      - For CSV/JSON, the CLI coerces IntEnums to plain ints by default.
    """

    device_name: str
    device_target: int  # remains a plain int (DeviceTarget is top-level scope, not per-mapping)

    # --- CMAI header ---
    mapping_type: Optional[MappingType]                 # 0=In, 1=Out
    traktor_control_id: int
    midi_binding_id: int
    midi_note: Optional[str]

    # --- CMAD settings ---
    controller_type: Optional[ControllerType]           # 0=Button,1=Fader/Knob,2=Encoder,65535=LED
    interaction_mode: Optional[InteractionMode]         # 1..8 (Toggle..Output)
    deck_scope: Optional[MappingTargetDeck]             # includes -1 (DeviceTargetDeck)
    auto_repeat: Optional[int]
    invert: Optional[int]
    soft_takeover: Optional[int]

    rotary_sensitivity: Optional[float]
    rotary_acceleration: Optional[float]
    set_value_to: Optional[float]

    mod1_id: Optional[int]
    mod1_val: Optional[int]
    mod2_id: Optional[int]
    mod2_val: Optional[int]

    # LED/meter ranges (outputs)
    led_min_controller: Optional[float]
    led_max_controller: Optional[float]
    led_min_midi: Optional[int]
    led_max_midi: Optional[int]
    led_invert: Optional[int]
    led_blend: Optional[int]

    # DWORD that maps to specific float semantics; kept as enum for fidelity
    resolution_raw: Optional[MappingResolution]

    comment: Optional[str]
