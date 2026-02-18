# ui/constants.py
"""
User-facing strings and messages for HSP Metadata Wizard.
Centralized for easy maintenance and consistency.
"""

from enum import IntEnum
from core.version import APP_NAME, __version__ as APP_VERSION


# ===== Window and Dialog Titles =====
MAIN_WINDOW_TITLE = f"{APP_NAME} {APP_VERSION}"
TOOLBAR_HELP = "Help"
MENU_HELP = "Help"
MENU_HELP_CONTENTS = "Help"
MENU_ABOUT = "About"

DIALOG_ERROR = "Error"
DIALOG_ERRORS = "Errors"
DIALOG_INFORMATION = "Information"
DIALOG_WRITE_ERROR = "Write Error"
DIALOG_UNDO_ERROR = "Undo Error"
DIALOG_ABOUT = "About"

# ===== Title Card =====
TITLECARD_PROCEED = "Proceed"
TITLECARD_AUTHOR = "Author: kai ilchmann"
TITLECARD_VERSION = f"Version: v{APP_VERSION}"
TITLECARD_HELP = "Help"
TITLECARD_LICENSE = "License"

# ===== Group Box Titles =====
GROUP_SOURCE = "Source Folder"
GROUP_LEGEND = "Legend & Counts"
GROUP_METADATA = "Metadata Edit Panel (applies to Checked rows)"
GROUP_ACTIONS = "Actions"
GROUP_PROGRESS = "Progress"

# ===== Button Labels =====
BTN_BROWSE = "Browse"
BTN_RESCAN = "Rescan"
BTN_SELECT_ALL = "Select All"
BTN_SELECT_NONE = "Select None"
BTN_INVERT = "Invert"

BTN_UPDATE = "Update"
BTN_ADD = "Add"
BTN_CLEAR = "Clear"
BTN_COPY_FILENAME = "Copy filename → Title (All)"
BTN_OPEN_FOLDER_PANEL = "Open folder"

BTN_SORT_KEYWORDS = "Sort keywords alphabetically, shib-tags last"
BTN_ADD_SHIB = "Add shib-[foldername] tag to Keywords"
BTN_ADD_SHIB_1234 = "Add shib-1234 tag to Keywords"
BTN_OPEN_FOLDER = "Open pdf source folder"

BTN_UNDO = "Undo last"

BTN_CANCEL = "Cancel"
BTN_COPY = "Copy"
BTN_CLOSE = "Close"

BTN_SHOW_INFO = "Show information"
BTN_SHOW_ERRORS = "Show errors"

# ===== Labels and Status Messages =====
LABEL_LEGEND = "Legend:"
LABEL_COUNTS = "Counts:"
LABEL_TOTAL = "Total: {}"
LABEL_SELECTED = "Selected: {}"
LABEL_WARNINGS = "Warnings: {}"
LABEL_PROTECTED = "Protected: {}"

LABEL_BATCH_PROGRESS = "Batch progress:"
LABEL_FILE_PROGRESS = "File progress:"

LABEL_TITLE = "Title:"
LABEL_AUTHOR = "Author:"
LABEL_SUBJECT = "Subject:"
LABEL_KEYWORDS = "Keywords:"
LABEL_KEYWORD_TOOLS = "Keyword tools:"

STATUS_SCANNING = "Scanning {}/{} ({}%)"
STATUS_LOADING_FOLDER = "Loading folder: {}"
STATUS_NO_PDFS = "No PDF files found in the selected folder."
STATUS_LOADED = "Loaded {} PDF files."
STATUS_LOADED_WITH_ISSUES = " {} protected files will be skipped."
STATUS_LOADED_WITH_WARNINGS = " {} files have naming warnings."

STATUS_WRITE_START = "Starting write..."
STATUS_WRITE_COMPLETE = "Applied. Success: {}, Skipped: {}, Failures: {}."
STATUS_WRITE_CANCELLED = "Write cancelled."
STATUS_WRITE_FILE = "Writing {}/{}: {}"

STATUS_UNDO_START = "Starting undo..."
STATUS_UNDO_COMPLETE = "Undo complete. Restored: {}, Failures: {}."
STATUS_UNDO_CANCELLED = "Undo cancelled."
STATUS_UNDO_FILE = "Undo {}/{}: {}"

STATUS_OPERATION_CANCELLED = "Operation cancelled."
STATUS_PREVIEW_ONLY = "Preview only. Check at least one file to modify."
STATUS_NO_PREVIEW = "No preview file selected. Click a row to preview."
STATUS_PREVIEW_LOCKED = "Preview file cannot be modified (protected or failed to load)."
STATUS_SELECTION_BLOCKED = "One or more checked files cannot be modified. Uncheck protected/corrupted files to proceed."
STATUS_MULTI_SELECTED = "(!) {} files selected"

# ===== Confirmations and Warnings =====
CONFIRM_TITLE_SET = "Set Title to '{}' for {} file(s)?"
CONFIRM_COPY_FILENAME = "Copy filename → Title for {} file(s)?"
CONFIRM_ADD_FIELD = "Add to {} for {} file(s)? This will add to the existing values, it does not overwrite - if you want to overwrite you need to clear the field."
CONFIRM_CLEAR_FIELD = "Clear {} for {} file(s)? This can be undone with Undo Last (button below)."
CONFIRM_HEADER = "Confirm"
CONFIRM_ADD_SHIB = "Add shib tag '{}' to Keywords for {} file(s)?"
CONFIRM_ADD_SHIB_1234 = "Add shib-1234 tag to Keywords for {} file(s)?"

WARN_SUBFOLDER = "Some files are in subfolders:\n\n{}\n\nProceed with caution."
WARN_SUBFOLDER_SIMPLE = "Some files are in subfolders, proceed with caution."
WARN_INVALID_FOLDER = "The folder does not exist:\n{}"

MSG_NO_SELECTION = "Please select files to apply changes."
MSG_NO_CHANGES = "Enter at least one metadata value to apply."
MSG_NO_TEXT = "Enter a {} value first."
MSG_NO_UNDO = "There is no previous batch to undo."
MSG_UNDO_EMPTY = "Batch was empty."
MSG_EXIT_WHILE_BUSY = "An operation is still running. Cancel it and exit?"
MSG_RENAME_HINT = "To rename files, open the folder in Explorer."
MSG_MULTIPLE_VALUES = "(Multiple values)"

# ===== Tooltips =====
TIP_BROWSE = "Select a folder containing PDF files"
TIP_RESCAN = "Rescan the current folder for changes"
TIP_OPEN_FOLDER = "Open the current source folder in Explorer"
TIP_FOLDER_INPUT = "Paste a folder path and press Enter to load"
TIP_SELECT_ALL = "Select all files in the table"
TIP_SELECT_NONE = "Deselect all files"
TIP_INVERT = "Invert the current selection"

TIP_TITLE_UPDATE = "Replace Title on all checked files with this value. On multi-file selection, all checked files are updated."
TIP_TITLE_CLEAR = "Clear Title on all checked files (asks for confirmation)"
TIP_COPY_FILENAME = "Set each checked file's Title to its own filename (without .pdf)"

TIP_AUTHOR_UPDATE = "Replace Author on all checked files with this value. On multi-file selection, all checked files are updated."
TIP_AUTHOR_ADD = "Append Author on all checked files (token merge, case-insensitive de-dup). On multi-file selection, all checked files are updated."
TIP_AUTHOR_CLEAR = "Clear Author on all checked files"

TIP_SUBJECT_UPDATE = "Replace Subject on all checked files with this value. On multi-file selection, all checked files are updated."
TIP_SUBJECT_ADD = "Append Subject on all checked files (token merge, case-insensitive de-dup). On multi-file selection, all checked files are updated."
TIP_SUBJECT_CLEAR = "Clear Subject on all checked files"

TIP_KEYWORDS_UPDATE = "Replace Keywords on all checked files with canonicalized keyword text. On multi-file selection, all checked files are updated."
TIP_KEYWORDS_ADD = "Append Keywords on all checked files (canonicalized: de-duplicate + sort; shib-tags last). On multi-file selection, all checked files are updated."
TIP_KEYWORDS_CLEAR = "Clear Keywords on all checked files"

TIP_SORT_KEYWORDS = "De-duplicate (case-insensitive), sort; shib-tags last."
TIP_ADD_SHIB = "Add 'shib-[foldername]' tag to Keywords for checked files (asks for confirmation)"
TIP_ADD_SHIB_1234 = "Add 'shib-1234' tag to Keywords for checked files (asks for confirmation)"


TIP_UNDO = "Undo the last batch of changes"
TIP_CANCEL = "Stop the current operation after the current file"

TIP_ERRORS_COPY = "Copy all errors to clipboard"

# ===== UI Text Elements =====
TEXT_FILENAME_WARNING = "⚠"
TEXT_PROTECTED = "🔒"
TEXT_PLACEHOLDER = "Paste folder path and press Enter, or use Browse..."
TEXT_HINT = "(Paste path + Enter loads)"
TEXT_NOTE = "Note: Keywords are de-duplicated (case-insensitive), sorted (with the shib-tags last)."

# ===== Table Headers =====
HEADER_CHECK = "✓"
HEADER_FILENAME = "Filename"
HEADER_TITLE = "Title"
HEADER_AUTHOR = "Author"
HEADER_KEYWORDS = "Keywords"
HEADER_SUBJECT = "Subject"

# --- Unified column schema ---

class Col(IntEnum):
    CHECK    = 0
    FILENAME = 1
    TITLE    = 2
    KEYWORDS = 3
    AUTHOR   = 4
    SUBJECT  = 5

# Logical order (stable, used by the model)
TABLE_HEADERS = [
    HEADER_CHECK,
    HEADER_FILENAME,
    HEADER_TITLE,
    HEADER_KEYWORDS,
    HEADER_AUTHOR,
    HEADER_SUBJECT,

]

# Metadata fields handled uniformly
METADATA_FIELDS = ("title", "author", "subject", "keywords")

# Map metadata field -> logical column index
COL_INDEX = {
    "filename": Col.FILENAME,   # convenience
    "title":    Col.TITLE,
    "keywords": Col.KEYWORDS,
    "author":   Col.AUTHOR,
    "subject":  Col.SUBJECT,
}

# ===== Error Messages =====
ERROR_FILE_NOT_FOUND = "File not found"
ERROR_PROTECTED_SKIP = "Password protected (skipped)"
ERROR_PROTECTED_CORRUPTED = "Protected/Corrupted"

# ===== Help Text =====
HELP_TEXT = """HSP Metadata Wizard v1

1. Select a folder containing PDFs
2. Select files to modify
3. Enter new metadata values or use Add/Clear/Copy buttons
4. Apply changes (Undo available)

🔒 = password protected (skipped) | ⚠ = filename warning"""
