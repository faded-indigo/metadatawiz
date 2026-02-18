# HSP Metadata Wizard

Batch edit PDF metadata (Title, Author, Subject, Keywords) safely on Windows.

This repository is prepared to contain source code only.
Compiled binaries are distributed as GitHub Release assets.

Current app version: `0.7` (`core/version.py`).

## What The App Does

- Scans a source folder recursively for PDF files.
- Displays editable metadata columns in this order:
  `✓`, `Filename`, `Title`, `Keywords`, `Author`, `Subject`.
- Applies batched metadata updates in a worker thread.
- Supports undo for the last batch.
- Skips password-protected PDFs and reports file-level errors.

## Metadata Behavior

- `Title`:
  - `Add` acts as replace.
  - `Clear` removes the field.
  - `Copy filename -> Title` sets Title to file stem.
- `Author` and `Subject`:
  - `Add` appends with token merge on `, ; |` and case-insensitive de-dup.
  - `Clear` removes the field.
- `Keywords`:
  - `Add` canonicalizes via rules engine (NFKC normalize, comma split/trim, de-dup, natural sort).
  - `shib-*` tags sort after non-shib tags.
  - `shib-1234` is always last if present.
  - `Sort keywords` normalizes input text only; click `Add` to write.
  - Dedicated buttons add `shib-[foldername]` or `shib-1234`.

## Subject Tag Disambiguation

Read path uses namespaced ExifTool tags and resolves Subject explicitly:
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

## Developer Setup

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests\test_rules.py -q
```

## Build Windows EXE

```powershell
.\.venv\Scripts\pyinstaller.exe --noconfirm HSPMetadataWizard.spec
```

Expected output:
- `dist\HSPMetadataWizard.exe`

Repository release metadata convention:
- `release\RELEASE_NOTES-vX.Y.md`
- `release\PROVENANCE-vX.Y.json`
- `release\SHA256SUMS.txt`

## Downloading The App From GitHub

Download binaries from the repository's Releases page.
The `main` branch does not track `.exe` files.

## Release Workflow (Versioned Builds)

1. Bump `core/version.py`.
2. Build via `HSPMetadataWizard.spec`.
3. Compute SHA256 and update `release/SHA256SUMS.txt`.
4. Update:
   - `release/RELEASE_NOTES-vX.Y.md`
   - `release/PROVENANCE-vX.Y.json`
5. Commit source/release-metadata changes.
6. Create annotated tag `vX.Y`.
7. Push branch and tag.
8. Create GitHub Release from tag and upload binary asset(s).

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
release/     release notes + provenance + checksums (no committed binaries)
```

## Third-Party Components

- ExifTool runtime is bundled in `tools/`.
- Third-party licensing notices from that bundle are included in `tools/exiftool_files/LICENSE`.

## License

MIT License. See `LICENSE`.
