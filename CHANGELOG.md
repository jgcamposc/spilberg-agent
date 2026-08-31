# Changelog

## [1.0.1] - 2026-08-31
### Fixed
- Descoberta de `whisper` e `auto-editor` em ambientes isolados fora do checkout local.

### Added
- Cascades Haar faciais empacotadas para manter o reframing disponível mesmo quando a distribuição do OpenCV não expõe seus dados internos.

## [1.0.0] - 2026-08-30
### Added
- CLI framework com suporte a `doctor`, `job submit`, e `job status`.
- Motor FFmpeg local-first integrado.
- Reframer inteligente com heurística de mediana.
- Pydantic models para EditPlan.
