# HSP Metadata Wizard v0.9

Release date: 2026-05-22
Tag: `v0.9`

## Highlights

- Removed unused atomic/platform helper modules and an unused title-card dialog.
- Updated fallback Help text to show the current app/version when `help.html` is unavailable.
- Write progress now shows the file being processed before the file completes.
- Metadata write and clear paths now share the same safe copy/edit/fsync/replace helper.
- Loading a new folder clears the undo stack so undo cannot target files from a previous folder.
- Added Help -> Reset "Don't ask again" confirmations so confirmation prompts can be restored.
- Hardened cancellation and shutdown behavior for scan, write, and undo workers.
- Cancelled writes now report partial completion instead of a normal "Applied" result.
- Undo batches remain retryable until an undo completes successfully.
- Keyword sorting now marks the Keywords field dirty so the sorted value can be applied.
- Table sorting is paused while scan results stream in to keep row data stable.
- Folder path entry now requires a directory, not just any existing filesystem path.

## Notes

- ExifTool remains the only read/write backend.
- Release asset: `HSPMetadataWizard-v0.9-windows-x64.exe`
- SHA256: `490A90811557CCAF502FE7DF20C7BEAF74E1412EA58983D17B1127CC22626668`
