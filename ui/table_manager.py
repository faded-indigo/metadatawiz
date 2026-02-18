# ui/table_manager.py
"""
Table management for the file list display.
Handles table creation, population, and selection operations.
"""
from __future__ import annotations

from typing import List, Dict, Optional
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from ui.constants import *


class FileTableManager(QObject):
    """Manages the file table widget and its operations."""
    
    selection_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.table = QTableWidget()
        self.setup_table()
        
    def setup_table(self):
        """Configure the table widget."""
        self.table.setColumnCount(len(TABLE_HEADERS))
        self.table.setHorizontalHeaderLabels(TABLE_HEADERS)

        header = self.table.horizontalHeader()
        header.setSectionsMovable(True)          # allow drag reorder
        header.setSortIndicatorShown(True)

        # Sizing:
        #  - Checkbox tight
        header.setSectionResizeMode(int(Col.CHECK), QHeaderView.ResizeMode.ResizeToContents)
        header.resizeSection(int(Col.CHECK), 30)

        #  - Filename stretches to fill space
        header.setSectionResizeMode(int(Col.FILENAME), QHeaderView.ResizeMode.Stretch)

        #  - Other metadata columns interactive with sane defaults
        for col, width in [
            (int(Col.TITLE),    200),
            (int(Col.KEYWORDS), 260),
            (int(Col.AUTHOR),   150),
            (int(Col.SUBJECT),  150),
        ]:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            header.resizeSection(col, width)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows) # select whole rows
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True) # zebra striping
        self.table.itemChanged.connect(self._on_item_changed) # handle checkbox changes
        self.table.setSortingEnabled(True) # enable sorting by columns

        # Ensure ~10 rows visible initially
        row_h = self.table.verticalHeader().defaultSectionSize()
        header_h = self.table.horizontalHeader().height()
        self.table.setMinimumHeight(int(header_h + row_h * 10.5))
    
    def clear(self):
        """Clear all rows from the table."""
        self.table.setRowCount(0)
        
    def add_file(self, file_data: dict) -> int:
        """Add a file to the table. Returns row index."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Checkbox column
        cb = QTableWidgetItem()
        cb.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        if file_data.get('is_protected') or file_data.get('is_corrupted'):
            cb.setFlags(Qt.ItemFlag.ItemIsUserCheckable)
        cb.setCheckState(Qt.CheckState.Unchecked)
        self.table.setItem(row, 0, cb)
        
        # Filename column with icons and tooltips
        fname = file_data.get('filename', '')
        if file_data.get('is_protected'):
            fname = TEXT_PROTECTED + " " + fname
        elif file_data.get('filename_warning'):
            fname = TEXT_FILENAME_WARNING + " " + fname
            
        fi = self._readonly_item(fname)
        fi.setData(Qt.ItemDataRole.UserRole, file_data)
        
        if file_data.get('filename_warning'):
            fi.setToolTip(file_data['filename_warning'])
        elif file_data.get('is_protected'):
            fi.setToolTip("Password protected - cannot modify")
        elif file_data.get('is_corrupted'):
            fi.setToolTip(file_data.get('error_message', 'Corrupted PDF'))
            
        self.table.setItem(row, int(Col.FILENAME), fi)
        
        # Metadata columns (uniform)
        for field in METADATA_FIELDS:
            col = int(COL_INDEX[field])
            self.table.setItem(row, col, self._readonly_item(file_data.get(field, "")))
        return row
    
    def get_selected_files(self) -> List[Dict]:
        """Get list of file data for all checked rows."""
        selected = []
        for row in range(self.table.rowCount()):
            cb = self.table.item(row, 0)
            if cb and cb.checkState() == Qt.CheckState.Checked:
                fi = self.table.item(row, int(Col.FILENAME))
                if fi:
                    fd = fi.data(Qt.ItemDataRole.UserRole)
                    if fd:
                        selected.append(fd)
        return selected
    
    def select_all(self):
        """Check all enabled rows."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsEnabled:
                item.setCheckState(Qt.CheckState.Checked)
        self.selection_changed.emit()
        
    def select_none(self):
        """Uncheck all rows."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.selection_changed.emit()
        
    def invert_selection(self):
        """Toggle check state for enabled rows."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsEnabled:
                current = item.checkState()
                item.setCheckState(Qt.CheckState.Unchecked if current == Qt.CheckState.Checked 
                                  else Qt.CheckState.Checked)
        self.selection_changed.emit()
    
    def update_row_metadata(self, row: int, metadata: dict):
        """Update metadata display for a specific row."""
        if row < 0 or row >= self.table.rowCount():
            return

        # Prevent row reordering while cells are being updated under active sorting.
        sorting_was_enabled = self.table.isSortingEnabled()
        if sorting_was_enabled:
            self.table.setSortingEnabled(False)

        try:
            # Uniform cell updates based on field->column mapping
            for field, value in metadata.items():
                if field in COL_INDEX:
                    self.table.setItem(row, int(COL_INDEX[field]), self._readonly_item(value or ""))

            # Update stored data blob on the filename cell
            fi = self.table.item(row, int(Col.FILENAME))
            if fi:
                fd = fi.data(Qt.ItemDataRole.UserRole) or {}
                fd.update(metadata)
                fi.setData(Qt.ItemDataRole.UserRole, fd)
        finally:
            if sorting_was_enabled:
                self.table.setSortingEnabled(True)

    def update_row_metadata_by_path(self, filepath: str, metadata: dict) -> bool:
        """Update metadata display using file path lookup to avoid stale row indexes."""
        row = self.get_row_by_path(filepath)
        if row is None:
            return False
        self.update_row_metadata(row, metadata)
        return True
    
    def get_row_by_path(self, filepath: str) -> Optional[int]:
        """Find row index for a given file path."""
        for row in range(self.table.rowCount()):
            fi = self.table.item(row, int(Col.FILENAME))
            if fi:
                fd = fi.data(Qt.ItemDataRole.UserRole)
                if fd and (fd.get('filepath') or fd.get('path')) == filepath:
                    return row
        return None

    def get_current_file_data(self) -> Optional[Dict]:
        """Return file-data blob for the currently focused row, if any."""
        row = self.table.currentRow()
        if row < 0:
            return None
        fi = self.table.item(row, int(Col.FILENAME))
        if not fi:
            return None
        fd = fi.data(Qt.ItemDataRole.UserRole)
        return fd if isinstance(fd, dict) else None
    
    def get_counts(self) -> Dict[str, int]:
        """Get counts of total and selected files."""
        total = self.table.rowCount()
        selected = len(self.get_selected_files())
        return {'total': total, 'selected': selected}
    
    def _on_item_changed(self, item):
        """Handle checkbox state changes."""
        if item.column() == 0:
            self.selection_changed.emit()

    @staticmethod
    def _readonly_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text or "")
        item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        return item
