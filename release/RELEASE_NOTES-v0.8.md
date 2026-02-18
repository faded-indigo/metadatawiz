# HSP Metadata Wizard v0.8

Release date: 2026-02-18
Tag: `v0.8`

## Highlights

- Selection and preview model hardened:
  - Only checked rows are actionable for writes.
  - Clicked row is preview-only when nothing is checked.
  - Panel refreshes immediately on checked-row/current-row changes.
- Metadata panel is now the single edit surface:
  - Table cells are read-only (no inline edit path).
  - Per-field actions clarified:
    - Title: `Update`, `Clear`, `Copy filename -> Title`
    - Author/Subject/Keywords: `Update`, `Add`, `Clear`
- Multi-select behavior improved:
  - Mixed values show empty input with placeholder `(Multiple values)`.
  - Multi-select status indicator shown in panel.
- Action safety hardening:
  - Update/Add ignore empty input silently.
  - Dirty-field gating for Update/Add.
  - Multi-file confirmations are keyed per action+field.
  - Protected/corrupted checked files block writes explicitly.
- Post-write consistency:
  - Row refresh now targets journaled write paths to avoid sort/selection drift corruption.

## Notes

- Subject disambiguation behavior remains in place (`PDF:Subject` preferred over `XMP-dc:Subject`).
- ExifTool remains the only read/write backend.
- Keyword normalization and canonical delimiter rules are unchanged.
