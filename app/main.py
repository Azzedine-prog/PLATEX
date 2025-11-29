import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QFile, QTextStream
from PySide6.QtGui import QAction
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QTextEdit,
    QToolBar,
    QStatusBar,
    QSplitter,
)


class EditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PLATEX – Lightweight LaTeX Editor")
        self.resize(1000, 700)

        self.editor = QTextEdit()
        self.editor.setTabStopDistance(32)

        self.preview_document = QPdfDocument(self)
        self.preview = QPdfView()
        self.preview.setDocument(self.preview_document)
        self.preview.setZoomMode(QPdfView.ZoomMode.FitToWidth)

        splitter = QSplitter()
        splitter.addWidget(self.editor)
        splitter.addWidget(self.preview)
        splitter.setSizes([650, 350])
        self.setCentralWidget(splitter)

        self.current_file: Path | None = None
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self._create_actions()
        self._create_toolbar()
        self._update_title()

    def _create_actions(self) -> None:
        self.new_action = QAction("New", self)
        self.new_action.triggered.connect(self.new_file)

        self.open_action = QAction("Open…", self)
        self.open_action.triggered.connect(self.open_file)

        self.save_action = QAction("Save", self)
        self.save_action.triggered.connect(self.save_file)

        self.save_as_action = QAction("Save As…", self)
        self.save_as_action.triggered.connect(lambda: self.save_file(save_as=True))

        self.compile_action = QAction("Compile PDF", self)
        self.compile_action.triggered.connect(self.compile_pdf)

        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self.show_about)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self.new_action)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.save_action)
        toolbar.addAction(self.save_as_action)
        toolbar.addSeparator()
        toolbar.addAction(self.compile_action)
        toolbar.addSeparator()
        toolbar.addAction(self.about_action)
        self.addToolBar(toolbar)

    def _update_title(self) -> None:
        filename = self.current_file.name if self.current_file else "Untitled.tex"
        self.setWindowTitle(f"PLATEX – {filename}")

    def new_file(self) -> None:
        if self._confirm_discard_changes():
            self.editor.clear()
            self.current_file = None
            self._update_title()
            self.status.showMessage("New file created", 2000)

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open LaTeX File", "", "TeX Files (*.tex);;All Files (*)")
        if path:
            self._load_file(Path(path))

    def _load_file(self, path: Path) -> None:
        file = QFile(str(path))
        if not file.open(QFile.ReadOnly | QFile.Text):
            QMessageBox.warning(self, "Error", f"Cannot open file: {path}")
            return
        stream = QTextStream(file)
        self.editor.setPlainText(stream.readAll())
        file.close()
        self.current_file = path
        self._update_title()
        self.status.showMessage(f"Opened {path}", 2000)

    def save_file(self, save_as: bool = False) -> None:
        if save_as or not self.current_file:
            path, _ = QFileDialog.getSaveFileName(self, "Save LaTeX File", "Untitled.tex", "TeX Files (*.tex);;All Files (*)")
            if not path:
                return
            self.current_file = Path(path)

        assert self.current_file is not None
        try:
            with open(self.current_file, "w", encoding="utf-8") as handle:
                handle.write(self.editor.toPlainText())
            self.status.showMessage(f"Saved to {self.current_file}", 2000)
            self._update_title()
        except OSError as exc:
            QMessageBox.critical(self, "Error", f"Failed to save file: {exc}")

    def _confirm_discard_changes(self) -> bool:
        reply = QMessageBox.question(
            self,
            "Discard changes?",
            "Any unsaved changes will be lost. Continue?",
            QMessageBox.Yes | QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def compile_pdf(self) -> None:
        if not self.current_file:
            self.save_file(save_as=True)
            if not self.current_file:
                return

        assert self.current_file is not None
        self.save_file()
        tex_file = self.current_file
        pdf_output = tex_file.with_suffix(".pdf")

        command = self._detect_compiler()
        if not command:
            QMessageBox.warning(
                self,
                "Compiler missing",
                "No LaTeX compiler (pdflatex or xelatex) was found in PATH.\n"
                "Install TeX Live or MiKTeX and try again.",
            )
            return

        self.status.showMessage("Compiling…", 2000)
        try:
            result = subprocess.run(
                [command, "-interaction=nonstopmode", str(tex_file)],
                cwd=tex_file.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=60,
                check=False,
            )
        except subprocess.TimeoutExpired:
            QMessageBox.critical(self, "Timeout", "Compilation took too long and was stopped.")
            return
        except OSError as exc:
            QMessageBox.critical(self, "Error", f"Failed to run compiler: {exc}")
            return

        if result.returncode == 0 and pdf_output.exists():
            self.status.showMessage(f"Compilation successful → {pdf_output}", 4000)
            self._load_preview(pdf_output)
        else:
            QMessageBox.critical(self, "Compilation failed", result.stdout or "No output")

    def _load_preview(self, pdf_output: Path) -> None:
        load_status = self.preview_document.load(str(pdf_output))
        if load_status == QPdfDocument.Status.Ready:
            self.preview.setPageMode(QPdfView.PageMode.MultiPage)
            QMessageBox.information(self, "Success", f"PDF created: {pdf_output}")
        else:
            QMessageBox.warning(
                self,
                "Preview unavailable",
                f"Compiled PDF saved to {pdf_output}, but the in-app preview could not be loaded.",
            )
            self._open_file(pdf_output)

    def _open_file(self, path: Path) -> None:
        try:
            if sys.platform.startswith("darwin"):
                subprocess.run(["open", str(path)], check=False)
            elif os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except Exception as exc:  # pragma: no cover - platform-specific
            QMessageBox.warning(self, "Open file", f"Could not open file: {exc}")

    def _detect_compiler(self) -> str | None:
        for candidate in ("pdflatex", "xelatex"):
            if shutil.which(candidate):
                return candidate
        return None

    def show_about(self) -> None:
        QMessageBox.information(
            self,
            "About PLATEX",
            "PLATEX is a lightweight desktop LaTeX editor built with Qt.\n"
            "It saves .tex files locally and can invoke your installed LaTeX distribution to build PDFs.",
        )


def main() -> None:
    app = QApplication(sys.argv)
    window = EditorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
