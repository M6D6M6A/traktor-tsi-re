from __future__ import annotations

import struct


class BER:
    """Big-endian reader with UTF-16LE (length-prefixed) helper."""

    def __init__(self, data: bytes, off: int = 0, end: int | None = None) -> None:
        self.data = data
        self.off = off
        self.end = len(data) if end is None else end

    def tell(self) -> int:
        return self.off

    def seek(self, off: int) -> None:
        self.off = off

    def remain(self) -> int:
        return self.end - self.off

    def u8(self) -> int:
        v = self.data[self.off]
        self.off += 1
        return v

    def u32(self) -> int:
        v = struct.unpack_from(">I", self.data, self.off)[0]
        self.off += 4
        return v

    def f32(self) -> float:
        v = struct.unpack_from(">f", self.data, self.off)[0]
        self.off += 4
        return v

    def bytes(self, n: int) -> bytes:
        b = self.data[self.off : self.off + n]
        self.off += n
        return b

    def wstr_prefixed(self) -> str:
        """Reads: u32 length (UTF-16 code units), then UTF-16BE bytes (2*len)."""
        n = self.u32()
        raw = self.bytes(n * 2)
        # The TSI controller blob is big-endian overall; wchar_t is UTF-16BE here.
        return raw.decode("utf-16-be", errors="ignore")


def read_frame_header(r: BER) -> tuple[str, int, int]:
    """
    Read a frame header and return (id4, payload_start, payload_end).

    IMPORTANT:
      - The 010 template defines Header.Size as *the number of bytes of content that follow*,
        i.e., **payload length**, NOT including the 8-byte header itself.
    """
    fid = r.bytes(4).decode("ascii", errors="ignore")
    size = r.u32()  # payload length in bytes
    # validate bounds (size can be 0 for empty frames)
    if r.tell() + size > r.end:
        raise ValueError(f"Invalid frame size {size} for {fid!r} (out of bounds)")
    payload_start = r.tell()
    payload_end = payload_start + size
    return fid, payload_start, payload_end
