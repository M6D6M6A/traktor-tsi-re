from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from .beio import BER, read_frame_header
from .enums import (
    ControllerType,
    InteractionMode,
    MappingResolution,
    MappingTargetDeck,
    MappingType,
    MidiEncoderMode,
)
from .frames import FrameWalker
from .midi import parse_binding_name
from .models import MappingRow


def _to_s32(u: Optional[int]) -> Optional[int]:
    """Interpret a u32 as signed 32-bit (Traktor often uses 0xFFFFFFFF as -1)."""
    if u is None:
        return None
    return u - 0x100000000 if u > 0x7FFFFFFF else u


class TsiParser:
    """
    High-level parser for Traktor TSI controller-mapping binary blobs.

    - Recurses through frames to find DEVI anywhere
    - Handles CMAS/DCBM order in DDCB (two-pass)
    - Parses DDDC (MIDI definitions) to attach encoder_mode/velocity/control_id
    - Conditionally parses CMAD tails (LED/Resolution for OUT mappings only)
    - Sanitizes denorm floats and non-meaningful set_value_to values
    - Preserves raw ints for enum fields as *_raw, and resolution DWORD
    - Captures raw UTF-16BE bytes (hex) for device_name, DCBM binding, CMAD comment
    """

    def __init__(self, cast_enums: bool = True) -> None:
        self._cast_enums = cast_enums

    # ---------- Public API ----------

    def parse(self, blob: bytes) -> List[MappingRow]:
        rows: List[MappingRow] = []
        walker = FrameWalker()
        for node in walker.walk(blob):
            if node.id4 == "DEVI":
                rows.extend(self._parse_device(blob, node.start + 8, node.end))
        return rows

    # ---------- Internal: devices ----------

    def _parse_device(self, data: bytes, start: int, end: int) -> List[MappingRow]:
        r = BER(data, start, end)

        # Device name (UTF-16 **BE**, prefixed char count) + capture raw bytes
        name_len = r.u32()
        device_name_raw = r.bytes(name_len * 2)
        device_name = device_name_raw.decode("utf-16-be", errors="ignore")
        device_name_raw_hex = device_name_raw.hex()

        rows: List[MappingRow] = []
        while r.tell() < r.end:
            fid, cstart, cend = read_frame_header(r)
            if fid == "DDAT":
                rows.extend(
                    self._parse_device_data(
                        data, cstart, cend, device_name, device_name_raw_hex
                    )
                )
            r.seek(cend)

        return rows

    def _parse_device_data(
        self, data: bytes, start: int, end: int, device_name: str, device_name_raw_hex: str
    ) -> List[MappingRow]:
        r = BER(data, start, end)
        device_target = 0  # default

        # name -> (velocity, encoder_mode, control_id)
        midi_defs: Dict[str, Tuple[Optional[float], Optional[int], Optional[int]]] = {}

        rows: List[MappingRow] = []
        while r.tell() < r.end:
            fid, cstart, cend = read_frame_header(r)

            if fid == "DDIF":  # DeviceTargetInfo
                rr = BER(data, cstart, cend)
                device_target = rr.u32()

            elif fid == "DDDC":  # MIDI definitions (In/Out)
                midi_defs.update(self._parse_midi_definitions(data, cstart, cend))

            elif fid == "DDCB":  # Mappings container
                rows.extend(
                    self._parse_mappings_container(
                        data, cstart, cend,
                        device_name, device_name_raw_hex,
                        device_target, midi_defs
                    )
                )

            r.seek(cend)

        return rows

    # ---------- MIDI definitions (DDDC → DDCI/DDCO with DCDT entries) ----------

    def _parse_midi_definitions(
        self, data: bytes, start: int, end: int
    ) -> Dict[str, Tuple[Optional[float], Optional[int], Optional[int]]]:
        """
        Returns name -> (velocity, encoder_mode, control_id).
        Structure:
          DDDC {
            DDCI { count; repeat count: DCDT ... }
            DDCO { count; repeat count: DCDT ... }
          }
        """
        out: Dict[str, Tuple[Optional[float], Optional[int], Optional[int]]] = {}
        r = BER(data, start, end)

        def _scan_list(list_start: int, list_end: int) -> None:
            rr = BER(data, list_start, list_end)
            count = rr.u32()
            for _ in range(count):
                fid2, dstart, dend = read_frame_header(rr)
                if fid2 != "DCDT":  # MidiDefinition
                    rr.seek(dend)
                    continue
                r2 = BER(data, dstart, dend)
                nlen = r2.u32()
                raw = r2.bytes(nlen * 2)
                name = raw.decode("utf-16-be", errors="ignore")
                _unk1 = r2.u32()
                _unk2 = r2.u32()
                velocity = r2.f32()
                encoder_mode = r2.u32()  # MidiEncoderMode (int)
                control_id = r2.u32()
                out[name] = (velocity, encoder_mode, control_id)
                rr.seek(dend)

        while r.tell() < r.end:
            fid, cstart, cend = read_frame_header(r)
            if fid in ("DDCI", "DDCO"):
                _scan_list(cstart, cend)
            r.seek(cend)

        return out

    # ---------- Mappings container (two-pass over children) ----------

    def _parse_mappings_container(
        self,
        data: bytes,
        start: int,
        end: int,
        device_name: str,
        device_name_raw_hex: str,
        device_target: int,
        midi_defs: Dict[str, Tuple[Optional[float], Optional[int], Optional[int]]],
    ) -> List[MappingRow]:
        # First pass: collect child slices
        child_slices = []
        r = BER(data, start, end)
        while r.tell() < r.end:
            fid, cstart, cend = read_frame_header(r)
            child_slices.append((fid, cstart, cend))
            r.seek(cend)

        # Second pass A: aggregate MIDI bindings (with raw bytes) from all DCBM lists
        midi_bindings: Dict[int, str] = {}
        midi_bindings_raw_hex: Dict[int, str] = {}
        for fid, cstart, cend in child_slices:
            if fid != "DCBM":
                continue
            rr = BER(data, cstart, cend)
            count = rr.u32()
            for _ in range(count):
                fid2, bstart, bend = read_frame_header(rr)
                if fid2 != "DCBM":
                    rr.seek(bend)
                    continue
                r2 = BER(data, bstart, bend)
                binding_id = r2.u32()
                nlen = r2.u32()
                raw = r2.bytes(nlen * 2)
                name = raw.decode("utf-16-be", errors="ignore")
                midi_bindings[binding_id] = name
                midi_bindings_raw_hex[binding_id] = raw.hex()
                rr.seek(bend)

        # Second pass B: parse all CMAS lists (mappings)
        rows: List[MappingRow] = []
        for fid, cstart, cend in child_slices:
            if fid == "CMAS":
                rows.extend(
                    self._read_mappings_list(
                        data, cstart, cend,
                        device_name, device_name_raw_hex,
                        device_target, midi_bindings, midi_bindings_raw_hex, midi_defs
                    )
                )
        return rows

    def _read_mappings_list(
        self,
        data: bytes,
        start: int,
        end: int,
        device_name: str,
        device_name_raw_hex: str,
        device_target: int,
        midi_bindings: Dict[int, str],
        midi_bindings_raw_hex: Dict[int, str],
        midi_defs: Dict[str, Tuple[Optional[float], Optional[int], Optional[int]]],
    ) -> List[MappingRow]:
        r = BER(data, start, end)
        count = r.u32()

        out: List[MappingRow] = []
        for _ in range(count):
            fid, mstart, mend = read_frame_header(r)
            if fid == "CMAI":
                out.append(
                    self._read_mapping(
                        data, mstart, mend,
                        device_name, device_name_raw_hex,
                        device_target, midi_bindings, midi_bindings_raw_hex, midi_defs
                    )
                )
            r.seek(mend)
        return out

    # ---------- One mapping (CMAI/CMAD) ----------

    def _read_mapping(
        self,
        data: bytes,
        start: int,
        end: int,
        device_name: str,
        device_name_raw_hex: str,
        device_target: int,
        midi_bindings: Dict[int, str],
        midi_bindings_raw_hex: Dict[int, str],
        midi_defs: Dict[str, Tuple[Optional[float], Optional[int], Optional[int]]],
    ) -> MappingRow:
        r = BER(data, start, end)

        midi_binding_id = r.u32()
        mapping_type_val = r.u32()  # 0 In, 1 Out
        traktor_control_id = r.u32()

        # CMAD (settings)
        fid, sstart, send = read_frame_header(r)
        if fid != "CMAD":
            return self._build_row_minimal(
                device_name, device_name_raw_hex, device_target,
                mapping_type_val, traktor_control_id,
                midi_binding_id, midi_bindings.get(midi_binding_id),
                midi_bindings_raw_hex.get(midi_binding_id),
                midi_defs
            )

        sr = BER(data, sstart, send)

        def _u32() -> Optional[int]:
            return sr.u32() if sr.tell() + 4 <= sr.end else None

        def _f32() -> Optional[float]:
            return sr.f32() if sr.tell() + 4 <= sr.end else None

        def _wstr_raw() -> Tuple[str, Optional[str]]:
            """
            Read a length-prefixed UTF-16BE string and return (text, raw_hex).
            Safe if truncated.
            """
            if sr.tell() + 4 > sr.end:
                return "", None
            n = sr.u32()
            bytelen = n * 2
            if sr.tell() + bytelen > sr.end:
                bytelen = max(0, sr.end - sr.tell())
            raw = sr.bytes(bytelen)
            return raw.decode("utf-16-be", errors="ignore"), (raw.hex() if bytelen else None)

        def _clean_f(v: Optional[float]) -> Optional[float]:
            if v is None:
                return None
            if math.isnan(v) or abs(v) < 1e-20:
                return None
            return v

        # ---- CMAD fixed head ----
        _unknown1 = _u32()
        controller_type_val = _u32()
        interaction_mode_val = _u32()
        deck_scope_u32 = _u32()
        deck_scope_val = _to_s32(deck_scope_u32)  # treat 0xFFFFFFFF as -1

        auto_repeat = _u32()
        invert = _u32()
        soft_takeover = _u32()
        rotary_sensitivity = _f32()
        rotary_acceleration = _f32()
        _unknown10 = _u32()
        _unknown11 = _u32()
        set_value_to = _f32()
        comment, comment_raw_hex = _wstr_raw()
        if comment == "":
            comment = None

        mod1_id = _u32()
        _unk15 = _u32()
        mod1_val = _u32()
        mod2_id = _u32()
        _unk18 = _u32()
        mod2_val = _u32()
        _unk20 = _u32()

        # Raw copies for diagnostics / output
        mapping_type_raw = mapping_type_val
        controller_type_raw = controller_type_val
        interaction_mode_raw = interaction_mode_val
        deck_scope_raw = deck_scope_u32
        resolution_dword = None  # set below if we read it

        # ---- CMAD conditional tail (LED/Resolution) ----
        led_min_ctrl = led_max_ctrl = None
        led_min_midi = led_max_midi = None
        led_invert = led_blend = None
        resolution_raw_val = None

        if mapping_type_val == int(MappingType.OUT):
            tail_len = send - sr.tell()
            if tail_len >= 40:
                tail = BER(data, sr.tell(), send)
                t_led_min_ctrl = _clean_f(tail.f32())
                _ = tail.u32()  # unknown22
                t_led_max_ctrl = _clean_f(tail.f32())
                t_led_min_midi = tail.u32()
                t_led_max_midi = tail.u32()
                t_led_invert = tail.u32()
                t_led_blend = tail.u32()
                _ = tail.u32()  # unknown29
                t_res_dword = tail.u32()
                _ = tail.u32()  # unknown30

                # accept only if we consumed the whole frame AND MIDI ranges are sane
                if tail.tell() == tail.end and 0 <= t_led_min_midi <= 127 and 0 <= t_led_max_midi <= 127:
                    sr.seek(send)  # commit
                    led_min_ctrl = t_led_min_ctrl
                    led_max_ctrl = t_led_max_ctrl
                    led_min_midi = t_led_min_midi
                    led_max_midi = t_led_max_midi
                    led_invert = t_led_invert
                    led_blend = t_led_blend
                    resolution_raw_val = t_res_dword
                    resolution_dword = t_res_dword

        # set_value_to: only meaningful in DIRECT mode
        if interaction_mode_val != int(InteractionMode.DIRECT) if interaction_mode_val is not None else True:
            set_value_to = None
        else:
            set_value_to = _clean_f(set_value_to)

        # Cast to enums when requested (IntEnum is still an int)
        def _cast(enum_cls, value: Optional[int]):
            if not self._cast_enums or value is None:
                return value
            try:
                return enum_cls(value)
            except ValueError:
                return None  # treat invalid as missing

        def _cast_res(dw: Optional[int]) -> Optional[MappingResolution]:
            if dw is None:
                return None
            try:
                return MappingResolution(dw)
            except ValueError:
                return None

        mapping_type = _cast(MappingType, mapping_type_val)
        controller_type = _cast(ControllerType, controller_type_val)
        interaction_mode = _cast(InteractionMode, interaction_mode_val)
        deck_scope = _cast(MappingTargetDeck, deck_scope_val)
        resolution_enum = _cast_res(resolution_raw_val) if self._cast_enums else resolution_raw_val

        # Enrich from binding name and DDDC (+ raw hex)
        binding_name = midi_bindings.get(midi_binding_id)
        binding_raw_hex = midi_bindings_raw_hex.get(midi_binding_id)
        ch, event, number, note_name = parse_binding_name(binding_name)

        # fallback: compute MIDI number from note name if parser didn't produce one
        if number is None and note_name:
            number = self._note_to_number_fallback(note_name)

        vel, enc_mode_raw, ctrl_id = (None, None, None)
        if binding_name and binding_name in midi_defs:
            vel, enc_mode_raw, ctrl_id = midi_defs[binding_name]

        # normalize NI sentinel control id
        if ctrl_id == 0xFFFFFFFF:
            ctrl_id = -1

        midi_encoder_mode = None
        if enc_mode_raw is not None:
            try:
                midi_encoder_mode = MidiEncoderMode(enc_mode_raw)
            except ValueError:
                midi_encoder_mode = None

        return MappingRow(
            device_name=device_name,
            device_target=device_target,
            device_name_raw_hex=device_name_raw_hex,
            mapping_type=mapping_type,
            traktor_control_id=traktor_control_id,
            midi_binding_id=midi_binding_id,
            midi_note=binding_name,
            midi_note_raw_hex=binding_raw_hex,
            midi_channel=ch,
            midi_event=event,
            midi_number=number,
            midi_note_name=note_name,
            midi_encoder_mode=midi_encoder_mode,
            midi_default_velocity=_clean_f(vel),
            midi_control_id=ctrl_id,
            controller_type=controller_type,
            interaction_mode=interaction_mode,
            deck_scope=deck_scope,
            auto_repeat=auto_repeat,
            invert=invert,
            soft_takeover=soft_takeover,
            rotary_sensitivity=rotary_sensitivity,
            rotary_acceleration=rotary_acceleration,
            set_value_to=set_value_to,
            mod1_id=mod1_id,
            mod1_val=mod1_val,
            mod2_id=mod2_id,
            mod2_val=mod2_val,
            led_min_controller=led_min_ctrl,
            led_max_controller=led_max_ctrl,
            led_min_midi=led_min_midi,
            led_max_midi=led_max_midi,
            led_invert=led_invert,
            led_blend=led_blend,
            resolution_raw=resolution_enum,
            comment=comment,
            comment_raw_hex=comment_raw_hex,
            # raw ints preserved:
            mapping_type_raw=mapping_type_raw,
            controller_type_raw=controller_type_raw,
            interaction_mode_raw=interaction_mode_raw,
            deck_scope_raw=deck_scope_raw,
            resolution_dword=resolution_dword,
        )

    # ---------- Helpers ----------

    def _build_row_minimal(
        self,
        device_name: str,
        device_name_raw_hex: str,
        device_target: int,
        mapping_type_val: int,
        traktor_control_id: int,
        midi_binding_id: int,
        midi_note: Optional[str],
        midi_note_raw_hex: Optional[str],
        midi_defs: Dict[str, Tuple[Optional[float], Optional[int], Optional[int]]],
    ) -> MappingRow:
        # Parse binding + defs even for minimal rows
        ch, event, number, note_name = parse_binding_name(midi_note)
        if number is None and note_name:
            number = self._note_to_number_fallback(note_name)

        vel = enc = cid = None
        if midi_note and midi_note in midi_defs:
            vel, enc, cid = midi_defs[midi_note]
        if cid == 0xFFFFFFFF:
            cid = -1

        midi_encoder_mode = None
        if enc is not None:
            try:
                midi_encoder_mode = MidiEncoderMode(enc)
            except ValueError:
                midi_encoder_mode = None

        try:
            mapping_type = MappingType(mapping_type_val) if self._cast_enums else mapping_type_val
        except ValueError:
            mapping_type = None

        return MappingRow(
            device_name=device_name,
            device_target=device_target,
            device_name_raw_hex=device_name_raw_hex,
            mapping_type=mapping_type,
            traktor_control_id=traktor_control_id,
            midi_binding_id=midi_binding_id,
            midi_note=midi_note,
            midi_note_raw_hex=midi_note_raw_hex,
            midi_channel=ch,
            midi_event=event,
            midi_number=number,
            midi_note_name=note_name,
            midi_encoder_mode=midi_encoder_mode,
            midi_default_velocity=vel,
            midi_control_id=cid,
            # raw enum int we do know here:
            mapping_type_raw=mapping_type_val,
        )

    @staticmethod
    def _note_to_number_fallback(name: str) -> Optional[int]:
        """
        Convert 'C#3' style note names to MIDI number with C-1 = 0.
        Only used if midi.parse_binding_name couldn't provide a number.
        """
        base = {"C":0,"C#":1,"Db":1,"D":2,"D#":3,"Eb":3,"E":4,"F":5,"F#":6,"Gb":6,"G":7,"G#":8,"Ab":8,"A":9,"A#":10,"Bb":10,"B":11}
        name = name.strip()
        for k in sorted(base.keys(), key=len, reverse=True):
            if name.startswith(k):
                try:
                    octave = int(name[len(k):])
                except ValueError:
                    return None
                return 12 * (octave + 1) + base[k]
        return None
