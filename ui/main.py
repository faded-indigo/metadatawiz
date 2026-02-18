# ui/main.py
from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Optional, List, Dict

from PyQt6.QtCore import Qt, QUrl, QSettings   
from PyQt6.QtWidgets import (                  
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QGroupBox, QProgressBar,
    QFileDialog, QMessageBox, QCheckBox
)

from ui.constants import *  # centralised UI strings
from ui.constants import MAIN_WINDOW_TITLE
from ui.table_manager import FileTableManager
from ui.dialogs import InfoDialog, ErrorsDialog, AboutDialog
from core.rules import process_keywords
from core.rules import make_shib_token_from_folder

from PyQt6.QtGui import QIcon, QAction, QKeySequence, QDesktopServices, QCloseEvent
from infra.bundled import resource_path

from services.ops import (
    apply_replace, append_field, clear_field,
    title_from_filename
)

# Module paths (package layout)
sys.path.insert(0, str(Path(__file__).parent.parent))

from workers.loader import LoaderManager
from workers.writer import WriterWorker
from core.undo import UndoManager, UndoWorker
from core.metadata import MetadataHandler


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # State
        self.current_folder: str = ""
        self.pdf_files: List[dict] = []
        self.has_shown_subfolder_warning: bool = False

        # Managers
        self.table_manager = FileTableManager(self)
        self.loader_manager = LoaderManager(self)
        self.undo_manager = UndoManager()

        # Threads
        self.writer_thread: Optional[WriterWorker] = None
        self.undo_thread: Optional[UndoWorker] = None

        # Info/errors buffers
        self.info_messages: List[str] = []
        self.last_failures: List[dict] = []

        # UI
        self.init_ui()
        self.setup_tooltips()
        self.connect_loader_signals()

        # React to selection changes from the table
        self.table_manager.selection_changed.connect(self.update_counts)

        # Settings
        self.settings = QSettings("HSP", "MetadataWizard")


    # -------------------- UI construction --------------------

    def init_ui(self):
        self.setWindowTitle(MAIN_WINDOW_TITLE)
        self.setGeometry(100, 100, 1200, 800)

        cw = QWidget(self)
        self.setCentralWidget(cw)
        main = QVBoxLayout(cw)
        main.setSpacing(8)

        self.create_help_menu()

        # Top row: Source + Legend/Counts
        top_row = QHBoxLayout()
        top_row.addWidget(self.build_source_group(), 2)
        top_row.addWidget(self.build_legend_counts_group(), 1)
        main.addLayout(top_row)

        # File table
        main.addWidget(self.table_manager.table, stretch=1)

        # Metadata edit panel
        self.create_metadata_panel(main)

        # Progress + info/errors buttons
        self.create_progress_area(main)

        self.update_ui_state()

        pass

    def create_help_menu(self):
        help_menu = self.menuBar().addMenu(MENU_HELP)

        help_action = QAction(MENU_HELP_CONTENTS, self)
        help_action.setShortcut(QKeySequence.StandardKey.HelpContents)
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)

        about_action = QAction(MENU_ABOUT, self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def build_source_group(self) -> QGroupBox:
        group = QGroupBox(GROUP_SOURCE)
        v = QVBoxLayout(group)

        row = QHBoxLayout()
        self.folder_input = QLineEdit() # Input for folder path
        self.folder_input.setPlaceholderText(TEXT_PLACEHOLDER) # Placeholder text
        self.folder_input.returnPressed.connect(self.load_folder_from_input) # Load on Enter
        self.folder_input.textChanged.connect(self._on_source_text_changed) # Update button state
        row.addWidget(self.folder_input, 1) 

        self.browse_button = QPushButton(BTN_BROWSE) # Browse button
        self.browse_button.clicked.connect(self.browse_folder)
        row.addWidget(self.browse_button)

        self.rescan_button = QPushButton(BTN_RESCAN) # Rescan button
        self.rescan_button.clicked.connect(self.rescan_folder)
        self.rescan_button.setEnabled(False)
        row.addWidget(self.rescan_button)

        self.open_folder_button = QPushButton(BTN_OPEN_FOLDER) # Open folder button
        self.open_folder_button.setToolTip(TIP_OPEN_FOLDER)
        self.open_folder_button.clicked.connect(self.open_current_folder)
        self.open_folder_button.setEnabled(False)
        row.addWidget(self.open_folder_button)

        v.addLayout(row)

        hint = QLabel(TEXT_HINT)
        hint.setStyleSheet("color: gray; font-size: 10pt;")
        v.addWidget(hint)

        return group

    def build_legend_counts_group(self) -> QGroupBox:
        group = QGroupBox(GROUP_LEGEND)
        v = QVBoxLayout(group)

        # Legend
        legend = QHBoxLayout()
        label_legend = QLabel(LABEL_LEGEND)
        label_legend.setStyleSheet("font-weight: bold;")
        legend.addWidget(label_legend)

        warn = QLabel(f"{TEXT_FILENAME_WARNING} filename warning")
        warn.setStyleSheet("color: orange;")
        legend.addWidget(warn)

        prot = QLabel(f"{TEXT_PROTECTED} protected (skipped)")
        prot.setStyleSheet("color: red;")
        legend.addWidget(prot)
        legend.addStretch()
        v.addLayout(legend)

        # Counts
        counts = QHBoxLayout()
        label_counts = QLabel(LABEL_COUNTS)
        label_counts.setStyleSheet("font-weight: bold;")
        counts.addWidget(label_counts)

        self.total_label = QLabel(LABEL_TOTAL.format(0))
        counts.addWidget(self.total_label)

        self.selected_label = QLabel(LABEL_SELECTED.format(0))
        counts.addWidget(self.selected_label)

        self.warnings_label = QLabel(LABEL_WARNINGS.format(0))
        self.warnings_label.setStyleSheet("color: orange;")
        counts.addWidget(self.warnings_label)

        self.protected_label = QLabel(LABEL_PROTECTED.format(0))
        self.protected_label.setStyleSheet("color: red;")
        counts.addWidget(self.protected_label)

        counts.addStretch()
        v.addLayout(counts)

        # Selection helpers
        sel = QHBoxLayout()
        self.select_all_button = QPushButton(BTN_SELECT_ALL)
        self.select_all_button.clicked.connect(self.table_manager.select_all)
        sel.addWidget(self.select_all_button)

        self.select_none_button = QPushButton(BTN_SELECT_NONE)
        self.select_none_button.clicked.connect(self.table_manager.select_none)
        sel.addWidget(self.select_none_button)

        self.invert_button = QPushButton(BTN_INVERT)
        self.invert_button.clicked.connect(self.table_manager.invert_selection)
        sel.addWidget(self.invert_button)

        sel.addStretch()
        v.addLayout(sel)

        return group

    def create_metadata_panel(self, layout: QVBoxLayout):
        group = QGroupBox(GROUP_METADATA)
        g = QVBoxLayout(group)

        # Title
        row = QHBoxLayout()
        row.addWidget(QLabel(LABEL_TITLE))
        self.title_input = QLineEdit()
        row.addWidget(self.title_input, 1)

        self.title_add_button = QPushButton(BTN_ADD)
        self.title_add_button.clicked.connect(self.on_add_title_replace)  # replace semantics for Title
        row.addWidget(self.title_add_button)

        self.title_clear_button = QPushButton(BTN_CLEAR)
        self.title_clear_button.clicked.connect(lambda: self.on_clear_field("title"))
        row.addWidget(self.title_clear_button)

        self.copy_filename_all_button = QPushButton(BTN_COPY_FILENAME)
        self.copy_filename_all_button.clicked.connect(self.on_copy_filename_all)
        row.addWidget(self.copy_filename_all_button)
        g.addLayout(row)

        # Author
        row = QHBoxLayout()
        row.addWidget(QLabel(LABEL_AUTHOR))
        self.author_input = QLineEdit(); row.addWidget(self.author_input, 1)
        btn = QPushButton(BTN_ADD); btn.clicked.connect(lambda: self.on_add_field("author")); row.addWidget(btn)
        btn = QPushButton(BTN_CLEAR); btn.clicked.connect(lambda: self.on_clear_field("author")); row.addWidget(btn)
        g.addLayout(row)

        # Subject
        row = QHBoxLayout()
        row.addWidget(QLabel(LABEL_SUBJECT))
        self.subject_input = QLineEdit(); row.addWidget(self.subject_input, 1)
        btn = QPushButton(BTN_ADD); btn.clicked.connect(lambda: self.on_add_field("subject")); row.addWidget(btn)
        btn = QPushButton(BTN_CLEAR); btn.clicked.connect(lambda: self.on_clear_field("subject")); row.addWidget(btn)
        g.addLayout(row)

        # Keywords
        row = QHBoxLayout()
        row.addWidget(QLabel(LABEL_KEYWORDS))
        self.keywords_input = QLineEdit(); row.addWidget(self.keywords_input, 1)
        btn = QPushButton(BTN_ADD); btn.clicked.connect(lambda: self.on_add_field("keywords")); row.addWidget(btn)
        btn = QPushButton(BTN_CLEAR); btn.clicked.connect(lambda: self.on_clear_field("keywords")); row.addWidget(btn)
        g.addLayout(row)

        # Keyword tools
        row = QHBoxLayout()
        row.addWidget(QLabel(LABEL_KEYWORD_TOOLS))

        self.sort_keywords_button = QPushButton(BTN_SORT_KEYWORDS)
        self.sort_keywords_button.setToolTip(TIP_SORT_KEYWORDS)
        self.sort_keywords_button.clicked.connect(self.clean_sort_keywords)
        row.addWidget(self.sort_keywords_button)

        self.ensure_folder_button = QPushButton(BTN_ADD_SHIB)
        self.ensure_folder_button.setToolTip(TIP_ADD_SHIB)
        self.ensure_folder_button.clicked.connect(self.ensure_folder_shib)
        row.addWidget(self.ensure_folder_button)

        self.add_shib_1234_button = QPushButton(BTN_ADD_SHIB_1234)
        self.add_shib_1234_button.setToolTip(TIP_ADD_SHIB_1234)
        self.add_shib_1234_button.clicked.connect(self.add_shib_1234)
        row.addWidget(self.add_shib_1234_button)

        self.undo_button = QPushButton(BTN_UNDO)
        self.undo_button.setToolTip(TIP_UNDO)
        self.undo_button.clicked.connect(self.undo_last)
        self.undo_button.setEnabled(False)
        row.addWidget(self.undo_button)

        row.addStretch()
        g.addLayout(row)

        note = QLabel(TEXT_NOTE)
        note.setStyleSheet("color: gray; font-size: 9pt;")
        note.setWordWrap(True)
        g.addWidget(note)

        layout.addWidget(group)



    # -------------------- Actions area --------------------
    def create_progress_area(self, layout: QVBoxLayout):
        group = QGroupBox(GROUP_PROGRESS)
        g = QVBoxLayout(group)

        row = QHBoxLayout()
        row.addWidget(QLabel(LABEL_BATCH_PROGRESS))
        self.batch_progress = QProgressBar()
        row.addWidget(self.batch_progress, 1)
        self.cancel_button = QPushButton(BTN_CANCEL)
        self.cancel_button.clicked.connect(self.cancel_operation)
        self.cancel_button.setEnabled(False)
        row.addWidget(self.cancel_button)
        g.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel(LABEL_FILE_PROGRESS))
        self.file_progress = QProgressBar()
        row.addWidget(self.file_progress, 1)
        self.file_status_label = QLabel("")
        row.addWidget(self.file_status_label)
        g.addLayout(row)

        row = QHBoxLayout()
        self.show_info_button = QPushButton(BTN_SHOW_INFO)
        self.show_info_button.clicked.connect(self.show_information)
        row.addWidget(self.show_info_button)

        self.show_errors_button = QPushButton(BTN_SHOW_ERRORS)
        self.show_errors_button.clicked.connect(self.show_errors_dialog)
        row.addWidget(self.show_errors_button)

        row.addStretch()
        g.addLayout(row)

        layout.addWidget(group)

    # -------------------- Tooltips --------------------

    def setup_tooltips(self):
        self.browse_button.setToolTip(TIP_BROWSE)
        self.rescan_button.setToolTip(TIP_RESCAN)
        self.folder_input.setToolTip(TIP_FOLDER_INPUT)
        self.select_all_button.setToolTip(TIP_SELECT_ALL)
        self.select_none_button.setToolTip(TIP_SELECT_NONE)
        self.invert_button.setToolTip(TIP_INVERT)

        self.title_add_button.setToolTip(TIP_TITLE_ADD)
        self.title_clear_button.setToolTip(TIP_TITLE_CLEAR)
        self.copy_filename_all_button.setToolTip(TIP_COPY_FILENAME)

        # Author/Subject/Keywords
        # find the two buttons by order is brittle; so we rely on above labels for title only.

        self.sort_keywords_button.setToolTip(TIP_SORT_KEYWORDS)
        self.ensure_folder_button.setToolTip(TIP_ADD_SHIB)

        self.undo_button.setToolTip(TIP_UNDO)
        self.cancel_button.setToolTip(TIP_CANCEL)

    def confirm_with_dont_ask(self, settings_key: str, title: str, text: str,
                            icon: QMessageBox.Icon = QMessageBox.Icon.Question) -> bool:
        # Auto-accept if user disabled this confirmation previously
        if self.settings.value(settings_key, False, bool):
            return True

        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Yes)

        cb = QCheckBox("Don’t ask me again")
        box.setCheckBox(cb)

        result = box.exec()
        if result == QMessageBox.StandardButton.Yes:
            if cb.isChecked():
                self.settings.setValue(settings_key, True)
            return True
        return False
    
    # -------------------- Loader integration --------------------

    def connect_loader_signals(self):
        self.loader_manager.progress.connect(self.on_loader_progress)
        self.loader_manager.status.connect(self.add_info)
        self.loader_manager.file_found.connect(self.add_file_to_table)
        self.loader_manager.scan_complete.connect(self.on_scan_complete)
        self.loader_manager.error.connect(self.on_loader_error)
        self.loader_manager.subfolder_warning.connect(self.on_subfolder_warning)

    def on_loader_progress(self, current: int, total: int):
        self.batch_progress.setMaximum(total)
        self.batch_progress.setValue(current)
        pct = int((current / total) * 100) if total else 0
        self.file_status_label.setText(STATUS_SCANNING.format(current, total, pct))

    def add_file_to_table(self, file_data: dict):
        self.table_manager.add_file(file_data)
        self.pdf_files.append(file_data)

    def on_scan_complete(self, files: list):
        self.pdf_files = files
        self.cancel_button.setEnabled(False)
        self.batch_progress.setValue(self.batch_progress.maximum())

        stats = self.loader_manager.get_statistics()
        self.total_label.setText(LABEL_TOTAL.format(stats["total"]))
        self.warnings_label.setText(LABEL_WARNINGS.format(stats["warnings"]))
        self.protected_label.setText(LABEL_PROTECTED.format(stats["protected"]))

        if stats["total"] == 0:
            self.add_info(STATUS_NO_PDFS)
        else:
            msg = STATUS_LOADED.format(stats["total"])
            if stats["protected"] > 0:
                msg += STATUS_LOADED_WITH_ISSUES.format(stats["protected"])
            if stats["warnings"] > 0:
                msg += STATUS_LOADED_WITH_WARNINGS.format(stats["warnings"])
            self.add_info(msg)

        self.update_ui_state()
        self.update_counts()

    def on_loader_error(self, error_msg: str):
        QMessageBox.critical(self, DIALOG_ERROR, error_msg)
        self.cancel_button.setEnabled(False)
        self.add_info(f"{DIALOG_ERROR}: {error_msg}")

    def on_subfolder_warning(self, subfolders: list):
        if self.has_shown_subfolder_warning:
            return
        sample = "\n".join(f"  • {sf}" for sf in subfolders[:5])
        if len(subfolders) > 5:
            sample += f"\n  ... and {len(subfolders) - 5} more"
        reply = QMessageBox.warning(
            self, "Subfolder Warning",
            WARN_SUBFOLDER.format(sample),
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Cancel:
            self.loader_manager.stop_loading()
            self.add_info(STATUS_OPERATION_CANCELLED)
        else:
            self.has_shown_subfolder_warning = True

    # -------------------- Helpers & state --------------------

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder Containing PDFs", self.current_folder or ""
        )
        if folder:
            self.folder_input.setText(folder)
            self.load_folder(folder)

    def load_folder_from_input(self):
        folder = self.folder_input.text().strip()
        if folder and os.path.exists(folder):
            self.load_folder(folder)
        elif folder:
            QMessageBox.warning(self, "Invalid Folder", WARN_INVALID_FOLDER.format(folder))

    def load_folder(self, folder: str):
        self.current_folder = folder
        self.folder_input.setText(folder)  # keep UI in sync
        self.rescan_button.setEnabled(True) # Enable rescan button
        self.has_shown_subfolder_warning = False   # Reset warning state
        self.table_manager.clear() # Clear the table
        self.pdf_files.clear() # Clear the internal file list
        self.info_messages.clear() # Clear previous info messages

        self.add_info(STATUS_LOADING_FOLDER.format(folder)) # Reset progress
        self.cancel_button.setEnabled(True) # Start cancel button
        self.batch_progress.setValue(0) # Reset batch progress
        self.file_progress.setValue(0) # Reset file progress
        self.file_status_label.setText("") # Reset file status label
        self.loader_manager.start_loading(folder) # Start the loader thread
        self._on_source_text_changed(self.folder_input.text()) # Update button state

    def rescan_folder(self):
        if self.current_folder:
            self.load_folder(self.current_folder)

    def get_selected_files(self) -> List[Dict]:
        return self.table_manager.get_selected_files()

    def add_info(self, message: str):
        # Avoid consecutive dupes
        if self.info_messages and self.info_messages[-1] == message:
            return
        self.info_messages.append(message)
        # Bound memory
        if len(self.info_messages) > 300:
            del self.info_messages[:50]

    def show_information(self):
        InfoDialog(self.info_messages, self).exec()

    def update_counts(self):
        counts = self.table_manager.get_counts()
        self.total_label.setText(LABEL_TOTAL.format(counts["total"]))
        self.selected_label.setText(LABEL_SELECTED.format(counts["selected"]))

        if getattr(self.loader_manager, "loaded_files", None):
            stats = self.loader_manager.get_statistics()
            self.warnings_label.setText(LABEL_WARNINGS.format(stats["warnings"]))
            self.protected_label.setText(LABEL_PROTECTED.format(stats["protected"]))
        self.update_ui_state()

    def update_ui_state(self):
        has_files = self.table_manager.table.rowCount() > 0
        loader_active = self.loader_manager.is_loading()
        writer_active = bool(self.writer_thread and self.writer_thread.isRunning())
        undo_active = bool(self.undo_thread and self.undo_thread.isRunning())
        busy = loader_active or writer_active or undo_active

        self.select_all_button.setEnabled(has_files and not busy)
        self.select_none_button.setEnabled(has_files and not busy)
        self.invert_button.setEnabled(has_files and not busy)
        self.undo_button.setEnabled(self.undo_manager.can_undo() and not busy)
        self.cancel_button.setEnabled(busy)

    def _on_source_text_changed(self, text: str):
        path = (text or "").strip()
        self.open_folder_button.setEnabled(bool(path and os.path.isdir(path)))

    def open_current_folder(self):
        path = (self.folder_input.text() or "").strip()
        if not (path and os.path.isdir(path)): # Ensure it's a valid folder
            QMessageBox.information(self, DIALOG_INFORMATION, "No valid folder to open.")
            return
        try:
            os.startfile(path)  # Windows
        except Exception:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    # --- Keyword input helpers (do not write to files) --------------------------

    def clean_sort_keywords(self):
        text = (self.keywords_input.text() or "").strip()
        if not text:
            return
        normalized = self._normalize_keywords_or_warn(text)
        self.keywords_input.setText(normalized)

    def ensure_folder_shib(self):
        """
        Add 'shib-[foldername]' to Keywords for the selected files (once).
        Foldername is taken from the CURRENT SOURCE FOLDER only.
        Writes immediately after confirmation. Fully undoable.
        """
        files = self.get_selected_files()
        if not files:
            QMessageBox.information(self, DIALOG_INFORMATION, MSG_NO_SELECTION)
            return

        folder_path = (self.current_folder or "").strip()
        if not folder_path or not os.path.isdir(folder_path):
            QMessageBox.information(self, DIALOG_INFORMATION, "No valid source folder selected; cannot derive shib tag.")
            return

        token = make_shib_token_from_folder(os.path.basename(folder_path))
        if not token:
            QMessageBox.information(self, DIALOG_INFORMATION, "Folder name did not produce a valid shib tag.")
            return

        # Confirm (persisted via 'Don't ask again')
        if not self.confirm_with_dont_ask(
            settings_key="confirm/add_shib_folder",
            title=CONFIRM_HEADER,
            text=CONFIRM_ADD_SHIB.format(token, len(files)),
            icon=QMessageBox.Icon.Question,
        ):
            return

        # Append immediately via writer (normalization/dedup happens in the pipeline)
        self.writer_thread = append_field(files, "keywords", token, self)
        self._connect_writer_signals()
        self._start_writer_with_progress(len(files), STATUS_WRITE_START)

    def add_shib_1234(self):
        files = self.get_selected_files()
        if not files:
            QMessageBox.information(self, DIALOG_INFORMATION, MSG_NO_SELECTION)
            return

        token = "shib-1234"

        if not self.confirm_with_dont_ask(
            settings_key="confirm/add_shib_1234",
            title=CONFIRM_HEADER,
            text=CONFIRM_ADD_SHIB_1234.format(len(files)),
            icon=QMessageBox.Icon.Question,
        ):
            return

        self.writer_thread = append_field(files, "keywords", token, self)
        self._connect_writer_signals()
        self._start_writer_with_progress(len(files), STATUS_WRITE_START)

    def _normalize_keywords_or_warn(self, text: str) -> str:
        """Normalize keywords safely. If core.rules.process_keywords fails,
        fall back to a simple, robust normalization and never crash the UI."""
        try:
            return process_keywords(text)
        except Exception as e:
            # Log to the info panel; keep the UI responsive
            self.add_info(f"Keyword normalization failed: {e!r}")

            # Fallback: split, trim, dedupe (case-insensitive), sort; put shib-* at the end
            try:
                parts = [p.strip() for p in (text or "").split(",")]
                parts = [p for p in parts if p]
                seen = set()
                dedup = []
                for p in parts:
                    k = p.casefold()
                    if k not in seen:
                        seen.add(k)
                        dedup.append(p)
                shib = [p for p in dedup if p.lower().startswith("shib-")]
                rest = [p for p in dedup if not p.lower().startswith("shib-")]
                rest.sort(key=str.casefold)
                shib.sort(key=str.casefold)
                return ", ".join(rest + shib)
            except Exception:
                QMessageBox.critical(self, DIALOG_ERROR, "Failed to normalize keywords; keeping original text.")
                return text


    # -------------------- Preview / Apply / Add / Clear --------------------

    def _maybe_show_subfolder_warning_once(self) -> bool:
        if self.has_shown_subfolder_warning:
            return True
        any_sub = any(fd.get("in_subfolder") for fd in self.pdf_files)
        if not any_sub:
            return True
        reply = QMessageBox.warning(
            self, "Subfolder Warning",
            WARN_SUBFOLDER_SIMPLE,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return False
        self.has_shown_subfolder_warning = True
        return True

    # ---- Add/Clear actions ----

    def on_add_title_replace(self):
        files = self.get_selected_files()
        if not files:
            QMessageBox.information(self, DIALOG_INFORMATION, MSG_NO_SELECTION)
            return
        text = self.title_input.text().strip()
        if not text:
            QMessageBox.information(self, DIALOG_INFORMATION, MSG_NO_TEXT.format("Title"))
            return
        if QMessageBox.question(self, CONFIRM_HEADER,
                                CONFIRM_TITLE_SET.format(text, len(files))) != QMessageBox.StandardButton.Yes:
            return
        # Direct replace op for Title
        self.writer_thread = apply_replace(files, {"title": text}, self)
        self._connect_writer_signals()
        self._start_writer_with_progress(len(files), STATUS_WRITE_START)

    def on_copy_filename_all(self):
        files = self.get_selected_files()
        if not files:
            QMessageBox.information(self, DIALOG_INFORMATION, MSG_NO_SELECTION)
            return
        if not self._maybe_show_subfolder_warning_once():
            return
        if QMessageBox.question(self, CONFIRM_HEADER,
                                CONFIRM_COPY_FILENAME.format(len(files))) != QMessageBox.StandardButton.Yes:
            return
        self.writer_thread = title_from_filename(files, self)
        self._connect_writer_signals()
        self._start_writer_with_progress(len(files), STATUS_WRITE_START)

    def on_add_field(self, field: str):
        files = self.get_selected_files()
        if not files:
            QMessageBox.information(self, DIALOG_INFORMATION, MSG_NO_SELECTION)
            return
        line: QLineEdit = getattr(self, f"{field}_input")
        text = line.text().strip()
        if not text:
            QMessageBox.information(self, DIALOG_INFORMATION, MSG_NO_TEXT.format(field.capitalize()))
            return
        if not self.confirm_with_dont_ask( 
            settings_key=f"confirm/add_{field}",
            title=CONFIRM_HEADER,
            text=CONFIRM_ADD_FIELD.format(field.capitalize(), len(files)),
            icon=QMessageBox.Icon.Question,
        ):
            return
        self.writer_thread = append_field(files, field, text, self)
        self._connect_writer_signals()
        self._start_writer_with_progress(len(files), STATUS_WRITE_START)


    def on_clear_field(self, field: str):
        files = self.get_selected_files()
        if not files:
            QMessageBox.information(self, DIALOG_INFORMATION, MSG_NO_SELECTION)
            return
        if not self.confirm_with_dont_ask(
                settings_key=f"confirm/clear_{field}",
                title=CONFIRM_HEADER,
                text=CONFIRM_CLEAR_FIELD.format(field.capitalize(), len(files)),
                icon=QMessageBox.Icon.Warning,
        ):
            return
        self.writer_thread = clear_field(files, field, self)
        self._connect_writer_signals()
        self._start_writer_with_progress(len(files), STATUS_WRITE_START)



    # -------------------- Writer plumbing --------------------

    def _connect_writer_signals(self):
        self.writer_thread.progress.connect(self._on_write_progress)
        self.writer_thread.file_progress.connect(self._on_write_file_progress)
        self.writer_thread.status.connect(self.add_info)
        self.writer_thread.error.connect(self._on_write_error)
        self.writer_thread.cancelled.connect(self._on_write_cancelled)
        self.writer_thread.finished.connect(self._on_write_finished)

    def _start_writer_with_progress(self, file_count: int, start_message: str):
        self.batch_progress.setMaximum(file_count)
        self.batch_progress.setValue(0)
        self.file_progress.setMaximum(100)
        self.file_progress.setValue(0)
        self.file_status_label.setText("")
        self.add_info(start_message)
        self.update_ui_state()
        self.writer_thread.start()

    def _on_write_progress(self, current: int, total: int):
        self.batch_progress.setMaximum(total)
        self.batch_progress.setValue(current)

    def _on_write_file_progress(self, done: int, total: int, filename: str):
        pct = int((done / total) * 100) if total else 0
        self.file_progress.setValue(pct)
        self.file_status_label.setText(STATUS_WRITE_FILE.format(done, total, filename))

    def _on_write_error(self, msg: str):
        QMessageBox.critical(self, DIALOG_WRITE_ERROR, msg)
        self.add_info(f"{DIALOG_WRITE_ERROR}: {msg}")
        self.writer_thread = None
        self.update_ui_state()

    def _on_write_cancelled(self):
        self.add_info(STATUS_WRITE_CANCELLED)
        self.writer_thread = None
        self.update_ui_state()

    def _on_write_finished(self, stats: dict, failures: List[dict], journal: List):
        self.undo_manager.push_batch(journal)
        self.add_info(STATUS_WRITE_COMPLETE.format(
            stats.get("successes", 0),
            stats.get("skipped", 0),
            stats.get("failures", 0),
        ))
        self.last_failures = failures[:]  # remember for later
        if failures:
            self.show_errors_dialog(failures)  # auto-open on errors
        self._refresh_rows_after_write()
        self.writer_thread = None
        self.update_ui_state()
        self.undo_button.setEnabled(self.undo_manager.can_undo())

    def _refresh_rows_after_write(self):
        try:
            handler = MetadataHandler()
        except FileNotFoundError:
            return
        selected = self.get_selected_files()
        paths = []
        seen = set()
        for fd in selected:
            path = fd.get("filepath") or fd.get("path")
            if path and path not in seen:
                seen.add(path)
                paths.append(path)

        for path in paths:
            meta = handler.read_metadata(path)
            self.table_manager.update_row_metadata_by_path(path, {
                "title": meta.title or "",
                "author": meta.author or "",
                "subject": meta.subject or "",
                "keywords": meta.keywords or "",
            })

    # -------------------- Undo --------------------

    def undo_last(self):
        if not self.undo_manager.can_undo():
            QMessageBox.information(self, DIALOG_INFORMATION, MSG_NO_UNDO)
            return

        batch = self.undo_manager.pop_last()
        if not batch or not batch.changes:
            QMessageBox.information(self, DIALOG_INFORMATION, MSG_UNDO_EMPTY)
            return

        self.undo_thread = UndoWorker(batch, self)
        self.undo_thread.progress.connect(self._on_undo_progress)
        self.undo_thread.file_progress.connect(self._on_undo_file_progress)
        self.undo_thread.status.connect(self.add_info)
        self.undo_thread.error.connect(self._on_undo_error)
        self.undo_thread.cancelled.connect(self._on_undo_cancelled)
        self.undo_thread.finished.connect(self._on_undo_finished)

        self.batch_progress.setMaximum(len(batch.changes))
        self.batch_progress.setValue(0)
        self.file_progress.setMaximum(100)
        self.file_progress.setValue(0)
        self.file_status_label.setText("")

        self.add_info(STATUS_UNDO_START)
        self.update_ui_state()
        self.undo_thread.start()

    def _on_undo_progress(self, current: int, total: int):
        self.batch_progress.setMaximum(total)
        self.batch_progress.setValue(current)

    def _on_undo_file_progress(self, done: int, total: int, filename: str):
        pct = int((done / total) * 100) if total else 0
        self.file_progress.setValue(pct)
        self.file_status_label.setText(STATUS_UNDO_FILE.format(done, total, filename))

    def _on_undo_error(self, msg: str):
        QMessageBox.critical(self, DIALOG_UNDO_ERROR, msg)
        self.add_info(f"{DIALOG_UNDO_ERROR}: {msg}")
        self.undo_thread = None
        self.update_ui_state()

    def _on_undo_cancelled(self):
        self.add_info(STATUS_UNDO_CANCELLED)
        self.undo_thread = None
        self.update_ui_state()

    def _on_undo_finished(self, stats: dict, failures: List[dict]):
        self.add_info(STATUS_UNDO_COMPLETE.format(
            stats.get("restored", 0), stats.get("failures", 0)
        ))
        if failures:
            self.show_errors_dialog(failures)

        # Refresh everything (simple strategy)
        try:
            handler = MetadataHandler()
        except FileNotFoundError:
            handler = None

        if handler:
            paths = []
            seen = set()
            for row in range(self.table_manager.table.rowCount()):
                fi = self.table_manager.table.item(row, int(Col.FILENAME))
                if not fi:
                    continue
                fd = fi.data(Qt.ItemDataRole.UserRole) or {}
                path = fd.get("filepath") or fd.get("path")
                if path and path not in seen:
                    seen.add(path)
                    paths.append(path)

            for path in paths:
                meta = handler.read_metadata(path)
                self.table_manager.update_row_metadata_by_path(path, {
                    "title": meta.title or "",
                    "author": meta.author or "",
                    "subject": meta.subject or "",
                    "keywords": meta.keywords or "",
                })

        self.undo_thread = None
        self.update_ui_state()

    # -------------------- Errors, miscellaneous --------------------

    def show_errors_dialog(self, failures: Optional[List[dict]] = None):
        try:
            items: List[dict] = []
            if failures:
                items = failures[:]
            else:
                if hasattr(self.loader_manager, "get_files_by_status"):
                    protected = self.loader_manager.get_files_by_status("protected") or []
                    for f in protected:
                        items.append({"filename": f.get("filename", ""), "error": ERROR_PROTECTED_SKIP})
                    err = self.loader_manager.get_files_by_status("error") or []
                    for f in err:
                        items.append({"filename": f.get("filename", ""), "error": f.get("error_message", "Error")})
            ErrorsDialog(items, self).exec()
        except Exception as e:
            QMessageBox.critical(self, DIALOG_ERRORS, f"Failed to show errors: {e}")

    def cancel_operation(self):
        if self.writer_thread and self.writer_thread.isRunning():
            self.writer_thread.cancel()
            return
        if self.undo_thread and self.undo_thread.isRunning():
            self.undo_thread.cancel()
            return
        self.loader_manager.stop_loading()
        self.cancel_button.setEnabled(False)
        self.add_info(STATUS_OPERATION_CANCELLED)

    def closeEvent(self, event: QCloseEvent):
        loader_active = self.loader_manager.is_loading()
        writer_active = bool(self.writer_thread and self.writer_thread.isRunning())
        undo_active = bool(self.undo_thread and self.undo_thread.isRunning())

        if not (loader_active or writer_active or undo_active):
            event.accept()
            return

        reply = QMessageBox.question(
            self,
            CONFIRM_HEADER,
            MSG_EXIT_WHILE_BUSY,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            event.ignore()
            return

        if writer_active and self.writer_thread:
            self.writer_thread.cancel()
            self.writer_thread.wait(5000)
        if undo_active and self.undo_thread:
            self.undo_thread.cancel()
            self.undo_thread.wait(5000)
        if loader_active:
            self.loader_manager.stop_loading()
        event.accept()

    def show_help(self):
        manual = resource_path("resources/help.html")
        if os.path.exists(manual):
            QDesktopServices.openUrl(QUrl.fromLocalFile(manual))
            return
        QMessageBox.information(self, MENU_HELP, HELP_TEXT)

    def show_about(self):
        AboutDialog(self).exec()

def main():
    app = QApplication(sys.argv)

    # App / window icon (works in dev & packaged EXE)
    app.setWindowIcon(QIcon(resource_path("resources/app.ico")))

    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
