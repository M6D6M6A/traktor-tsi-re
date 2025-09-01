# Traktor TSI format notes

- Controller mappings are stored as a binary blob (big-endian) embedded in the TSI XML.
- Strings are UTF-16LE with a 32-bit char count prefix.
- Frames are nested; unknown frames should be skipped by size to remain robust.
- TP4: data structure remained compatible for controller mappings; extra fields may appear at tail of `CMAD` (guard with safe reads).
