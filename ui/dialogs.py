# ui/dialogs.py
from __future__ import annotations

from typing import List
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QWidget, QTextEdit, QHBoxLayout, QApplication
from PyQt6.QtCore import Qt, QUrl
from infra.bundled import resource_path
from core.version import APP_NAME, __version__ as APP_VERSION
from PyQt6.QtGui import QPixmap, QIcon, QDesktopServices
from ui.constants import (
    MAIN_WINDOW_TITLE, DIALOG_ABOUT, BTN_CLOSE,
    TITLECARD_PROCEED, TITLECARD_AUTHOR, TITLECARD_VERSION, TITLECARD_HELP, TITLECARD_LICENSE
)


def _load_help_html() -> str:
    """Load resources/help.html and substitute version/app name placeholders."""
    path = resource_path("resources/help.html")
    try:
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception:
        html = "<h1>{app}</h1><p>Version: v{ver}</p>".format(app=APP_NAME, ver=APP_VERSION)

    return html.replace("{{APP_VERSION}}", APP_VERSION).replace("{{APP_NAME}}", APP_NAME)


def open_help_page() -> bool:
    """
    Render Help HTML with placeholders resolved and open it in the user's browser.
    Returns True when a launch was attempted successfully.
    """
    try:
        html = _load_help_html()
        out_dir = Path(tempfile.gettempdir()) / "HSPMetadataWizard"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "help_resolved.html"
        out_path.write_text(html, encoding="utf-8")
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(out_path)))
    except Exception:
        raw_path = resource_path("resources/help.html")
        if Path(raw_path).exists():
            return QDesktopServices.openUrl(QUrl.fromLocalFile(raw_path))
        return False


class TitleCardDialog(QDialog):
    """
    Modal title card shown before the main window.
    - Centered square icon
    - Large Proceed button
    - Inline Help / License links opening local HTML files
    - Author and Version labels
    """
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(MAIN_WINDOW_TITLE)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.Dialog)
        self.setMinimumWidth(420)
        self.setMinimumHeight(380)
        self.setWindowIcon(QIcon(resource_path("resources/app.ico")))

        # Icon (centered)
        icon_label = QLabel(self)
        pix = QPixmap(resource_path("resources/app.ico"))
        if not pix.isNull():
            icon_label.setPixmap(pix.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Proceed button
        proceed_btn = QPushButton(TITLECARD_PROCEED, self)
        proceed_btn.setMinimumHeight(40)
        proceed_btn.setDefault(True)
        proceed_btn.clicked.connect(self.accept)

        # Help / License links (inline)
        help_link = QLabel(self)
        help_link.setTextFormat(Qt.TextFormat.RichText)
        help_link.setText(f'<a href="local:help">{TITLECARD_HELP}</a>')
        help_link.setOpenExternalLinks(False)
        help_link.linkActivated.connect(lambda _href: open_help_page())

        license_link = QLabel(self)
        license_link.setTextFormat(Qt.TextFormat.RichText)
        license_link.setText(f'<a href="local:license">{TITLECARD_LICENSE}</a>')
        license_link.setOpenExternalLinks(False)
        license_link.linkActivated.connect(lambda _href: QDesktopServices.openUrl(QUrl.fromLocalFile(resource_path("resources/license.html"))))

        links_row = QHBoxLayout()
        links_row.addStretch(1)
        links_row.addWidget(help_link)
        links_row.addSpacing(12)
        links_row.addWidget(license_link)
        links_row.addStretch(1)

        # Author / Version
        author_label = QLabel(TITLECARD_AUTHOR, self)
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label = QLabel(TITLECARD_VERSION, self)
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Layout
        root = QVBoxLayout(self)
        root.addStretch(1)
        root.addWidget(icon_label)
        root.addSpacing(16)
        root.addWidget(proceed_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        root.addSpacing(12)
        root.addLayout(links_row)
        root.addSpacing(8)
        root.addWidget(author_label)
        root.addWidget(version_label)
        root.addStretch(1)
        self.setLayout(root)


class AboutDialog(QDialog):
    """
    About dialog surfaced from Help > About.
    Shows the splash image plus links and app/version details.
    """
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(DIALOG_ABOUT)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.Dialog)
        self.setMinimumWidth(560)
        self.setMinimumHeight(420)
        self.setWindowIcon(QIcon(resource_path("resources/app.ico")))

        splash_label = QLabel(self)
        pix = QPixmap(resource_path("resources/splash.png"))
        if pix.isNull():
            pix = QPixmap(resource_path("resources/app.ico"))
        if not pix.isNull():
            splash_label.setPixmap(
                pix.scaled(
                    520,
                    260,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        splash_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(MAIN_WINDOW_TITLE, self)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Help / License links (inline)
        help_link = QLabel(self)
        help_link.setTextFormat(Qt.TextFormat.RichText)
        help_link.setText(f'<a href="local:help">{TITLECARD_HELP}</a>')
        help_link.setOpenExternalLinks(False)
        help_link.linkActivated.connect(lambda _href: open_help_page())

        license_link = QLabel(self)
        license_link.setTextFormat(Qt.TextFormat.RichText)
        license_link.setText(f'<a href="local:license">{TITLECARD_LICENSE}</a>')
        license_link.setOpenExternalLinks(False)
        license_link.linkActivated.connect(
            lambda _href: QDesktopServices.openUrl(QUrl.fromLocalFile(resource_path("resources/license.html")))
        )

        links_row = QHBoxLayout()
        links_row.addStretch(1)
        links_row.addWidget(help_link)
        links_row.addSpacing(12)
        links_row.addWidget(license_link)
        links_row.addStretch(1)

        # Author / Version
        author_label = QLabel(TITLECARD_AUTHOR, self)
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label = QLabel(TITLECARD_VERSION, self)
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        close_btn = QPushButton(BTN_CLOSE, self)
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)

        root = QVBoxLayout(self)
        root.addWidget(splash_label)
        root.addSpacing(8)
        root.addWidget(title_label)
        root.addSpacing(8)
        root.addLayout(links_row)
        root.addSpacing(6)
        root.addWidget(author_label)
        root.addWidget(version_label)
        root.addSpacing(12)
        root.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.setLayout(root)


class InfoDialog(QDialog):
    def __init__(self, messages: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Information")
        v = QVBoxLayout(self)
        self.text = QTextEdit(self); self.text.setReadOnly(True)
        self.text.setPlainText("\n".join(messages) if messages else "No information.")
        v.addWidget(self.text)
        btns = QHBoxLayout()
        copy = QPushButton("Copy"); copy.clicked.connect(lambda: QApplication.clipboard().setText(self.text.toPlainText()))
        ok = QPushButton("Close"); ok.clicked.connect(self.accept)
        btns.addStretch(); btns.addWidget(copy); btns.addWidget(ok)
        v.addLayout(btns)

class ErrorsDialog(QDialog):
    def __init__(self, failures: List[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Errors")
        v = QVBoxLayout(self)
        self.text = QTextEdit(self); self.text.setReadOnly(True)
        lines = []
        for f in failures:
            lines.append(f"• {f.get('filename')} — {f.get('error')}")
        self.text.setPlainText("\n".join(lines) if lines else "No errors.")
        v.addWidget(self.text)
        btns = QHBoxLayout()
        copy = QPushButton("Copy"); copy.setToolTip("Copy all errors to clipboard")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.text.toPlainText()))
        ok = QPushButton("Close"); ok.clicked.connect(self.accept)
        btns.addStretch(); btns.addWidget(copy); btns.addWidget(ok)
        v.addLayout(btns)

