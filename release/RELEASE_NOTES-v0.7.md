# HSP Metadata Wizard v0.7

Release date: 2026-02-18
Tag: `v0.7`

## Highlights

- Subject metadata read path now disambiguates namespaced tags and prefers `PDF:Subject` over `XMP-dc:Subject`.
- Fixed sorted-table metadata refresh corruption by path-based row updates and safe sort-state handling.
- Repository hardening for GitHub:
  - MIT license alignment across repo and in-app license page.
  - Clean separation strategy: source in repo, binaries in GitHub Release assets.
  - Added release provenance/checksum workflow files.

## Notes

- Runtime metadata behavior and keyword rules are unchanged from the app's documented v0.7 logic.
- Third-party ExifTool runtime remains bundled under `tools/` with upstream notices in `tools/exiftool_files/LICENSE`.
