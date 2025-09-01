from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, List

from .beio import BER, read_frame_header

# Allow 0-9, A-Z, _, a-z
ASCII_OK = set(range(48, 58)) | set(range(65, 91)) | set(range(95, 96)) | set(range(97, 123))


def looks_like_id(b: bytes) -> bool:
    return len(b) == 4 and all(c in ASCII_OK for c in b)


@dataclass
class FrameNode:
    """Generic frame node with a shallow child count (for diagnostics/UI)."""
    id4: str
    start: int  # offset where frame header starts (id)
    end: int    # end offset of payload (exclusive)
    children_count: int


class FrameWalker:
    """
    Recursive frame walker. Yields every frame (pre-order) and also reports a
    shallow child count on each node for quick diagnostics.
    """

    def walk(self, data: bytes, start: int = 0, end: int | None = None) -> Iterator[FrameNode]:
        if end is None:
            end = len(data)
        r = BER(data, start, end)

        while r.tell() + 8 <= end:
            head = data[r.tell(): r.tell() + 4]
            if not looks_like_id(head):
                # resync inside container payloads when we hit non-frame bytes
                r.seek(r.tell() + 1)
                continue

            try:
                fid, pstart, pend = read_frame_header(r)
            except Exception:
                # invalid header; resync
                r.seek(r.tell() + 1)
                continue

            # Count shallow children quickly
            child_count = self._count_children(data, pstart, pend)
            node = FrameNode(id4=fid, start=pstart - 8, end=pend, children_count=child_count)

            # Yield this frame
            yield node

            # Recurse into payload to find nested frames (this was missing before)
            yield from self.walk(data, pstart, pend)

            # Jump to the end of this frame to continue with next sibling
            r.seek(pend)

    def _count_children(self, data: bytes, start: int, end: int) -> int:
        """Quick shallow scan to count immediate children; tolerant of junk."""
        count = 0
        rr = BER(data, start, end)
        while rr.tell() + 8 <= end:
            head = data[rr.tell(): rr.tell() + 4]
            if not looks_like_id(head):
                break
            try:
                _fid, cstart, cend = read_frame_header(rr)
            except Exception:
                break
            count += 1
            rr.seek(cend)
        return count
