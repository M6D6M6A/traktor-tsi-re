# Architecture

- **XML layer**: extract `DeviceIO.Config.Controller` Base64 from the `.tsi`
- **Binary layer**: big-endian frame reader (`id4` + `u32 size`), UTF-16LE length-prefixed strings
- **Domain layer**: parse known frames
  - `DEVI` device
  - `DDAT` data (`DDIF` target, `DDCB` mappings container)
  - `DDCB` contains `CMAS` (list of `CMAI`) and `DCBM` (MIDI binding table)
  - `CMAI` wraps `CMAD` (mapping settings)
- **Model**: `MappingRow` captures the union of commonly used fields
- **CLI**: `tsi-tool dump/frames/stats`
