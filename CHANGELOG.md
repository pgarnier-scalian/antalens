# Changelog

All notable changes to AntaLens will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- **Catalog system** — YAML-driven domain semantics (`Catalog`, `ComponentPattern`, `OutputMetadata`, `ColorPalette`, `StackTemplateConfig`)
- **GEMS-aware data layer** — `SimulationTable` and `Views` stubs for GEMS raw/curated outputs
- **Reactive scenario parameter** — `Lens.scenario` replaces deprecated `Lens.mc`
- **Domain-agnostic themes** — `DARK` and `LIGHT` `PlotlyTheme` instances, no domain-specific themes
- **Template-based stacked charts** — `StackTemplate` system for consistent category coloring
- **Plot accessor pattern** — `ds.plot.timeseries()`, `ds.plot.bar()`, `ds.plot.stack()` fluent API

### Changed

- **Public API surface** — Cleaned up to match spec §3.1, `import antalens as al`
- **Schema system** — Added `kind` discriminator (`wide`, `long_gems`, `xarray`)
- **Lens deprecation** — `mc` parameter deprecated in favor of `scenario`
- **Theme system** — Removed ANTARES-specific themes (`ECO2MIX`, `BASE`)
- **Legacy adapter** — Renamed `AntaresLegacyStudy` to `LegacyStudy`, `load_antares()` to `load_legacy()`

### Removed

- **Domain vocabulary from core** — No ANTARES, eco2mix, or other domain terms in `antalens/` package
- **Placeholder modules** — Removed `aliases.py`, `antares.py`, `antares_io.py`

---

## [0.1.0] - 2026-XX-XX

### Added

- Initial public API surface
- Data loaders (`load_parquet`, `load_csv`, `from_dataframe`)
- Plot builders (`TimeSeriesPlot`, `BarPlot`, `ProductionStack`)
- Dashboard composition with `Dashboard` class
- Chart-to-chart linking with `link()` function
- Reactive state management with `Lens`
