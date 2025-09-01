from __future__ import annotations

from typing import Dict, List, Optional

from .beio import BER, read_frame_header
from .enums import (
    ControllerType,
    InteractionMode,
    MappingResolution,
    MappingTargetDeck,
    MappingType,
)
from .frames import FrameWalker
from .models import MappingRow


class TsiParser:
    """
    High-level parser for Traktor TSI controller-mapping binary blobs.

    Walks recursively through frames and extracts all CMAI/CMAD under DEVI/DDAT/DDCB.
    """

    def __init__(self, cast_enums: bool = True) -> None:
        self._cast_enums = cast_enums

    def parse(self, blob: bytes) -> List[MappingRow]:
        rows: List[MappingRow] = []
        walker = FrameWalker()

        # Thanks to recursion, DEVI will be found even when nested under root container.
        for node in walker.walk(blob):
            if node.id4 == "DEVI":
                rows.extend(self._parse_device(blob, node.start + 8, node.end))
        return rows

    # ---- device ----

    def _parse_device(self, data: bytes, start: int, end: int) -> List[MappingRow]:
        r = BER(data, start, end)
        # Device name
        name_len = r.u32()
        device_name = r.bytes(name_len * 2).decode("utf-16-be", errors="ignore")

        rows: List[MappingRow] = []
        while r.tell() < r.end:
            fid, cstart, cend = read_frame_header(r)
            if fid == "DDAT":
                rows.extend(self._parse_device_data(data, cstart, cend, device_name))
            r.seek(cend)
        return rows

    def _parse_device_data(self, data: bytes, start: int, end: int, device_name: str) -> List[MappingRow]:
        r = BER(data, start, end)
        device_target = 0
        rows: List[MappingRow] = []

        while r.tell() < r.end:
            fid, cstart, cend = read_frame_header(r)
            if fid == "DDIF":
                rr = BER(data, cstart, cend)
                device_target = rr.u32()
            elif fid == "DDCB":
                rows.extend(self._parse_mappings_container(data, cstart, cend, device_name, device_target))
            r.seek(cend)
        return rows

    # ---- mappings ----

    def _parse_mappings_container(
        self,
        data: bytes,
        start: int,
        end: int,
        device_name: str,
        device_target: int,
    ) -> List[MappingRow]:
        """
        Parse DDCB robustly: some TSIs place CMAS before DCBM.
        We first collect child ranges, parse all DCBM to build the binding table,
        then parse all CMAS using that table.
        """
        # First pass: collect child slices
        child_slices = []
        r = BER(data, start, end)
        while r.tell() < r.end:
            fid, cstart, cend = read_frame_header(r)
            child_slices.append((fid, cstart, cend))
            r.seek(cend)

        # Second pass A: build midi_bindings from all DCBM
        midi_bindings: Dict[int, str] = {}
        for fid, cstart, cend in child_slices:
            if fid == "DCBM":
                # One "list" DCBM holding count, followed by entry DCBMs (same id).
                rr = BER(data, cstart, cend)
                count = rr.u32()
                for _ in range(count):
                    fid2, bstart, bend = read_frame_header(rr)
                    if fid2 != "DCBM":
                        rr.seek(bend)
                        continue
                    r2 = BER(data, bstart, bend)
                    binding_id = r2.u32()
                    name = r2.wstr_prefixed()
                    midi_bindings[binding_id] = name
                    rr.seek(bend)

        # Second pass B: parse all CMAS with the now-populated table
        rows: List[MappingRow] = []
        for fid, cstart, cend in child_slices:
            if fid == "CMAS":
                rows.extend(
                    self._read_mappings_list(
                        data, cstart, cend, device_name, device_target, midi_bindings
                    )
                )

        return rows


    def _read_midi_bindings(self, data: bytes, start: int, end: int) -> Dict[int, str]:
        r = BER(data, start, end)
        count = r.u32()
        out: Dict[int, str] = {}
        for _ in range(count):
            fid, bstart, bend = read_frame_header(r)
            if fid != "DCBM":
                r.seek(bend)
                continue
            rr = BER(data, bstart, bend)
            bid = rr.u32()
            note = rr.wstr_prefixed()
            out[bid] = note
            r.seek(bend)
        return out

    def _read_mappings_list(
        self,
        data: bytes,
        start: int,
        end: int,
        device_name: str,
        device_target: int,
        midi_bindings: Dict[int, str],
    ) -> List[MappingRow]:
        r = BER(data, start, end)
        count = r.u32()
        out: List[MappingRow] = []
        for _ in range(count):
            fid, mstart, mend = read_frame_header(r)
            if fid == "CMAI":
                out.append(self._read_mapping(data, mstart, mend, device_name, device_target, midi_bindings))
            r.seek(mend)
        return out

    def _read_mapping(
        self,
        data: bytes,
        start: int,
        end: int,
        device_name: str,
        device_target: int,
        midi_bindings: Dict[int, str],
    ) -> MappingRow:
        r = BER(data, start, end)
        midi_binding_id = r.u32()
        mapping_type = r.u32()
        traktor_control_id = r.u32()

        fid, sstart, send = read_frame_header(r)  # CMAD
        sr = BER(data, sstart, send)

        def _u32() -> Optional[int]:
            return sr.u32() if sr.tell() + 4 <= sr.end else None

        def _f32() -> Optional[float]:
            return sr.f32() if sr.tell() + 4 <= sr.end else None

        def _wstr() -> str:
            try:
                return sr.wstr_prefixed()
            except Exception:
                return ""

        _unknown1 = _u32()
        controller_type = _u32()
        interaction_mode = _u32()
        deck_scope = _u32()
        auto_repeat = _u32()
        invert = _u32()
        soft_takeover = _u32()
        rotary_sensitivity = _f32()
        rotary_acceleration = _f32()
        _unknown10 = _u32()
        _unknown11 = _u32()
        set_value_to = _f32()
        comment = _wstr() or None
        mod1_id = _u32()
        _unk15 = _u32()
        mod1_val = _u32()
        mod2_id = _u32()
        _unk18 = _u32()
        mod2_val = _u32()
        _unk20 = _u32()
        led_min_ctrl = _f32()
        _unk22 = _u32()
        led_max_ctrl = _f32()
        led_min_midi = _u32()
        led_max_midi = _u32()
        led_invert = _u32()
        led_blend = _u32()
        _unk29 = _u32()
        resolution_raw = _u32()
        _unk30 = _u32()

        def _cast(enum_cls, value: Optional[int]):
            if value is None:
                return None
            try:
                return enum_cls(value)
            except ValueError:
                return value  # keep raw if unknown

        mapping_type_c = _cast(MappingType, mapping_type)
        controller_type_c = _cast(ControllerType, controller_type)
        interaction_mode_c = _cast(InteractionMode, interaction_mode)
        deck_scope_c = _cast(MappingTargetDeck, deck_scope)
        resolution_c = _cast(MappingResolution, resolution_raw)

        return MappingRow(
            device_name=device_name,
            device_target=device_target,
            mapping_type=mapping_type_c,
            traktor_control_id=traktor_control_id,
            midi_binding_id=midi_binding_id,
            midi_note=midi_bindings.get(midi_binding_id),
            controller_type=controller_type_c,
            interaction_mode=interaction_mode_c,
            deck_scope=deck_scope_c,
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
            resolution_raw=resolution_c,
            comment=comment,
        )
