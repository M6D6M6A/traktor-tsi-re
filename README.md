# traktor-tsi-re

## Idea based on
https://github.com/ivanz/TraktorMappingFileFormat

Reverse-engineer and parse **Traktor Pro** TSI controller mappings (TP2/TP3/TP4) in Python.

- Pure Python, typed, PEP8, no runtime deps
- Parses `.tsi` → extracts `DeviceIO.Config.Controller` (Base64) → decodes **binary frames**
- Walks `DEVI → DDAT → DDCB(CMAS/DCBM)` and returns **mapping rows**
- CLI: `tsi-tool dump my.tsi --csv out.csv --json out.json`

## Install (editable)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
