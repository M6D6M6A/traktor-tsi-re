from __future__ import annotations

from enum import IntEnum


class DeviceTarget(IntEnum):
    """Device target (top-level device scope)."""
    FOCUS = 0
    DECK_A = 1
    DECK_B = 2
    DECK_C = 3
    DECK_D = 4


class MidiEncoderMode(IntEnum):
    """Encoder delta coding as stored in MidiDefinition."""
    _3Fh_41h = 0
    _7Fh_01h = 1


class MappingTargetDeck(IntEnum):
    """
    Per-mapping deck scope (a.k.a. 'Deck' field inside CMAD).
    Matches 010 template values, including -1.
    """
    DEVICE_TARGET_DECK = -1
    A_OR_FX1_OR_REMIX1_SLOT1_OR_GLOBAL = 0
    B_OR_FX2_OR_REMIX1_SLOT2 = 1
    C_OR_FX3_OR_REMIX1_SLOT3 = 2
    D_OR_FX4_OR_REMIX1_SLOT4 = 3
    REMIX2_SLOT1 = 4
    REMIX2_SLOT2 = 5
    REMIX2_SLOT3 = 6
    REMIX2_SLOT4 = 7
    REMIX3_SLOT1 = 8
    REMIX3_SLOT2 = 9
    REMIX3_SLOT3 = 10
    REMIX3_SLOT4 = 11
    REMIX4_SLOT1 = 12
    REMIX4_SLOT2 = 13
    REMIX4_SLOT3 = 14
    REMIX4_SLOT4 = 15


class InteractionMode(IntEnum):
    """Mapping interaction mode (CMAD)."""
    TOGGLE = 1
    HOLD = 2
    DIRECT = 3
    RELATIVE = 4
    INCREMENT = 5
    DECREMENT = 6
    RESET = 7
    OUTPUT = 8


class ControllerType(IntEnum):
    """Controller type inferred for mapping (CMAD)."""
    BUTTON = 0
    FADER_OR_KNOB = 1
    ENCODER = 2
    LED = 65535


class MappingResolution(IntEnum):
    """
    Resolution field in CMAD; stored as DWORD (big-endian) that corresponds
    to specific float values. We keep the raw DWORD constants for fidelity.
    """
    FINE = 0x3C800000
    MIN = 0x3D800000
    DEFAULT = 0x3D800000
    COARSE = 0x3E000000
    SWITCH = 0x3F000000


class MappingType(IntEnum):
    IN = 0
    OUT = 1


# Backwards-compatible aliases (if you referenced these names elsewhere):
MappingControllerType = ControllerType
MappingInteractionMode = InteractionMode
