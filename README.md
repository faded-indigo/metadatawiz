# HSP Metadata Wizard

Batch edit PDF metadata (Title, Author, Subject, Keywords) safely on Windows.

Current app version: `0.8` (`core/version.py`).

## Scope And Platform

- Windows-only target (Windows 10/11).
- Metadata-only workflow for PDF files.
- Uses bundled ExifTool as the only read/write backend.

## What The App Does

- Scans a source folder recursively for PDF files.
- Displays table columns in this order:
  `✓`, `Filename`, `Title`, `Keywords`, `Author`, `Subject`.
- Applies batched metadata updates through worker threads.
- Supports undo for the last batch.
- Skips password-protected PDFs and reports file-level errors.

## What The App Does Not Do

- Does not edit PDF content.
- Does not perform file renaming as a metadata side-effect.
- Does not provide cloud sync or remote services.
- Does not process non-PDF files.

## v0.8 Interaction Model

- Only checked rows are actionable batch selection.
- Clicked row is preview-only when nothing is checked.
- Metadata panel is the only edit surface; table cells are read-only.
- Switching checked rows or clicked row refreshes panel values immediately.
- Multi-select panel values:
  - Same value across all checked files: show value.
  - Mixed values: show empty input with placeholder `(Multiple values)`.

## Field Semantics

- `Title`
  - `Update`: replace Title on all checked files.
  - `Clear`: clear Title (confirmation required).
  - `Copy filename -> Title`: set Title to each file stem.
- `Author`, `Subject`, `Keywords`
  - `Update`: replace field on all checked files.
  - `Add`: append/merge into existing field values.
  - `Clear`: clear field (confirmation required).

## Rules And Safety

- `Update` and `Add` ignore empty input silently.
- Per-field `Update`/`Add` buttons are gated by dirty edits from user input.
- Multi-file confirmations are tracked per field and action (`Update`, `Add`, `Clear`) with "Don't ask again" settings.
- If checked files include protected/corrupted PDFs, actions are disabled until those files are unchecked.
- Keywords use canonical delimiter `", "` and existing normalization rules (dedupe, natural sort, `shib-*` ordering).

## Subject Tag Disambiguation

Read path resolves Subject explicitly:
- Prefer `PDF:Subject`
- Fallback to `XMP-dc:Subject`

This avoids showing XMP-only Subject values when the PDF Subject differs.

## Install And Run (Dev)

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m ui.main
```

## Basic Usage

1. Choose a source folder containing PDFs.
2. Check the rows you want to modify.
3. Edit fields in the Metadata panel.
4. Use field buttons (`Update`, `Add`, `Clear`) to write changes.
5. Use `Undo last` to roll back the most recent batch.

## Developer Setup

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests\test_rules.py -q
```

## Build Windows EXE

```powershell
.\.venv\Scripts\pyinstaller.exe --noconfirm HSPMetadataWizard.spec
```

Expected build output:
- `dist\HSPMetadataWizard.exe`

For release upload, rename/copy to:
- `HSPMetadataWizard-vX.Y-windows-x64.exe`

## ExifTool Requirement

- ExifTool is required for metadata operations.
- This repository ships bundled ExifTool runtime files under `tools/`.
- Metadata writes in the app are always executed via ExifTool.

## GitHub Releases

- Source code is tracked in this repository.
- Compiled binaries should be uploaded as GitHub Release assets.
- Release metadata files are kept in `release/`:
  - `release\RELEASE_NOTES-vX.Y.md`
  - `release\PROVENANCE-vX.Y.json`
  - `release\SHA256SUMS.txt`

## Release Workflow (Versioned Builds)

1. Bump `core/version.py`.
2. Build via `HSPMetadataWizard.spec`.
3. Produce artifact: `HSPMetadataWizard-vX.Y-windows-x64.exe`.
4. Compute SHA256 and update `release/SHA256SUMS.txt`.
5. Add/update:
   - `release/RELEASE_NOTES-vX.Y.md`
   - `release/PROVENANCE-vX.Y.json`
6. Commit changes.
7. Create annotated tag `vX.Y`.
8. Push branch and tag.
9. Create GitHub Release from tag and upload binary asset(s).

## Repository Layout

```text
core/        business rules and metadata IO
infra/       packaging/runtime helpers
services/    operation factories
ui/          PyQt UI
workers/     threaded scan/write workers
tests/       tests
resources/   icon/help assets
tools/       bundled ExifTool runtime
release/     release metadata and checksums
```

## Third-Party Components

- ExifTool runtime is bundled in `tools/`.
- Third-party licensing notices from that bundle are in `tools/exiftool_files/LICENSE`.
- Consolidated third-party notice summary: `THIRD_PARTY_NOTICES.md`.

## License

PolyForm Noncommercial 1.0.0. See `LICENSE`.

Copyright © Kai ilchmann.
Free for non-commercial use. Commercial use requires written permission.
