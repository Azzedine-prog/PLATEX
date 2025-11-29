import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QFile, QPoint, Qt, QTimer, QTextStream
from PySide6.QtGui import QAction, QColor, QFont, QPalette
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QTextEdit,
    QToolButton,
    QToolBar,
    QStatusBar,
    QSplitter,
)


class EditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PLATEX – Lightweight LaTeX Editor")
        self.resize(1000, 700)

        self._apply_theme()

        self.editor = QTextEdit()
        self.editor.setTabStopDistance(32)
        self._style_editor()

        self.preview_document = QPdfDocument(self)
        self.preview = QPdfView()
        self.preview.setDocument(self.preview_document)
        self.preview.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.preview.setStyleSheet(
            "QPdfView { background: #eef2f7; border-left: 1px solid #dbe2ec; }"
        )

        splitter = QSplitter()
        splitter.addWidget(self.editor)
        splitter.addWidget(self.preview)
        splitter.setSizes([650, 350])
        self.setCentralWidget(splitter)

        self.current_file: Path | None = None
        self.project_root: Path | None = None
        self.last_pdf_output: Path | None = None
        self.is_compiling = False
        self.live_preview_enabled = True
        self.live_preview_timer = QTimer(self)
        self.live_preview_timer.setSingleShot(True)
        self.live_preview_timer.setInterval(900)
        self.live_preview_timer.timeout.connect(lambda: self.compile_pdf(auto=True))
        self.status = QStatusBar()
        self.status.setStyleSheet(
            "QStatusBar { background: #ffffff; color: #0b172a; padding-left: 8px; border-top: 1px solid #dbe2ec; }"
        )
        self.setStatusBar(self.status)

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_context_menu()
        self.editor.textChanged.connect(self._schedule_live_preview)
        self._update_title()

    def _apply_theme(self) -> None:
        base_font = QFont("Inter", 11)
        base_font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
        QApplication.instance().setFont(base_font)

        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#f3f6fb"))
        palette.setColor(QPalette.WindowText, QColor("#1f2937"))
        palette.setColor(QPalette.Base, QColor("#f8fafc"))
        palette.setColor(QPalette.AlternateBase, QColor("#e9eef5"))
        palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
        palette.setColor(QPalette.ToolTipText, QColor("#1f2937"))
        palette.setColor(QPalette.Text, QColor("#111827"))
        palette.setColor(QPalette.Button, QColor("#0a66c2"))
        palette.setColor(QPalette.ButtonText, QColor("#ffffff"))
        palette.setColor(QPalette.Highlight, QColor("#0a66c2"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.Link, QColor("#0a66c2"))
        self.setPalette(palette)

    def _style_editor(self) -> None:
        font = QFont("JetBrains Mono", 12)
        font.setStyleHint(QFont.Monospace)
        self.editor.setFont(font)
        palette = self.editor.palette()
        palette.setColor(QPalette.Base, QColor("#f8fafc"))
        palette.setColor(QPalette.Text, QColor("#0b172a"))
        palette.setColor(QPalette.Highlight, QColor("#0a66c2"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        self.editor.setPalette(palette)
        self.editor.setStyleSheet(
            "QTextEdit { padding: 14px; border: 1px solid #dbe2ec; border-radius: 10px; }"
            "QTextEdit:focus { border: 1px solid #0a66c2; box-shadow: 0 0 0 3px rgba(10,102,194,0.18); }"
            "QScrollBar:vertical { background: #e9eef5; width: 12px; border-radius: 6px; }"
            "QScrollBar::handle:vertical { background: #0a66c2; min-height: 30px; border-radius: 6px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

    def _create_actions(self) -> None:
        self.new_project_action = QAction("New Project Folder", self)
        self.new_project_action.triggered.connect(self.create_project)

        self.open_project_action = QAction("Open Project Folder", self)
        self.open_project_action.triggered.connect(self.open_project)

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

        self.live_preview_action = QAction("Live Preview", self, checkable=True)
        self.live_preview_action.setChecked(True)
        self.live_preview_action.triggered.connect(self._toggle_live_preview)

        self.template_action = QAction("New from Template", self)
        self.template_action.triggered.connect(self.new_from_template)

        self.figure_action = QAction("Insert Figure", self)
        self.figure_action.triggered.connect(lambda: self.insert_snippet("figure"))

        self.table_action = QAction("Insert Table", self)
        self.table_action.triggered.connect(lambda: self.insert_snippet("table"))

        self.bibliography_action = QAction("Insert Bibliography", self)
        self.bibliography_action.triggered.connect(lambda: self.insert_snippet("bibliography"))

        self.section_action = QAction("Insert Section", self)
        self.section_action.triggered.connect(lambda: self.insert_snippet("section"))

        self.equation_action = QAction("Insert Equation", self)
        self.equation_action.triggered.connect(lambda: self.insert_snippet("equation"))

        self.list_action = QAction("Insert List", self)
        self.list_action.triggered.connect(lambda: self.insert_snippet("list"))

        self.toc_action = QAction("Insert TOC", self)
        self.toc_action.triggered.connect(lambda: self.insert_snippet("toc"))

        self.theorem_action = QAction("Insert Theorem", self)
        self.theorem_action.triggered.connect(lambda: self.insert_snippet("theorem"))

        self.code_action = QAction("Insert Code", self)
        self.code_action.triggered.connect(lambda: self.insert_snippet("code"))

        self.open_pdf_action = QAction("Open PDF Externally", self)
        self.open_pdf_action.triggered.connect(self.open_pdf_externally)

        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self.show_about)

    def _create_menus(self) -> None:
        menu_bar = QMenuBar(self)
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)

        project_menu = menu_bar.addMenu("Project")
        project_menu.addAction(self.new_project_action)
        project_menu.addAction(self.open_project_action)
        project_menu.addAction(self.template_action)

        insert_menu = menu_bar.addMenu("Insert")
        insert_menu.addAction(self.section_action)
        insert_menu.addAction(self.figure_action)
        insert_menu.addAction(self.table_action)
        insert_menu.addAction(self.bibliography_action)
        insert_menu.addAction(self.equation_action)
        insert_menu.addAction(self.list_action)
        insert_menu.addAction(self.toc_action)
        insert_menu.addAction(self.theorem_action)
        insert_menu.addAction(self.code_action)

        preview_menu = menu_bar.addMenu("Preview")
        preview_menu.addAction(self.compile_action)
        preview_menu.addAction(self.live_preview_action)
        preview_menu.addAction(self.open_pdf_action)

        help_menu = menu_bar.addMenu("Help")
        help_menu.addAction(self.about_action)
        menu_bar.setStyleSheet(
            "QMenuBar { background: #ffffff; border-bottom: 1px solid #dbe2ec; }"
            "QMenuBar::item { padding: 6px 10px; margin: 2px; }"
            "QMenuBar::item:selected { background: #e9eef5; color: #0a66c2; border-radius: 6px; }"
            "QMenu { background: #ffffff; border: 1px solid #dbe2ec; }"
            "QMenu::item:selected { background: #e9eef5; color: #0a66c2; }"
        )
        self.setMenuBar(menu_bar)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self.new_project_action)
        toolbar.addAction(self.open_project_action)
        toolbar.addSeparator()
        toolbar.addAction(self.new_action)
        toolbar.addAction(self.template_action)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.save_action)
        toolbar.addAction(self.save_as_action)
        toolbar.addSeparator()
        toolbar.addAction(self.compile_action)
        toolbar.addAction(self.live_preview_action)
        toolbar.addAction(self.open_pdf_action)
        toolbar.addSeparator()
        toolbar.addAction(self.figure_action)
        toolbar.addAction(self.table_action)
        toolbar.addAction(self.bibliography_action)
        toolbar.addAction(self.section_action)
        toolbar.addAction(self.equation_action)
        toolbar.addAction(self.list_action)
        toolbar.addAction(self.toc_action)
        toolbar.addAction(self.theorem_action)
        toolbar.addAction(self.code_action)
        toolbar.addSeparator()
        toolbar.addAction(self.about_action)
        snippet_menu = QMenu("Insert Snippet", self)
        for action in (
            self.figure_action,
            self.table_action,
            self.bibliography_action,
            self.section_action,
            self.equation_action,
            self.list_action,
            self.toc_action,
            self.theorem_action,
            self.code_action,
        ):
            snippet_menu.addAction(action)

        snippet_button = QToolButton()
        snippet_button.setText("Snippets")
        snippet_button.setMenu(snippet_menu)
        snippet_button.setPopupMode(QToolButton.InstantPopup)
        snippet_button.setStyleSheet(
            "QToolButton { background: #0a66c2; color: white; padding: 8px 12px;"
            " border-radius: 8px; font-weight: 600; letter-spacing: 0.3px; }"
            "QToolButton::menu-indicator { image: none; }"
            "QToolButton:hover { background: #004182; }"
        )
        toolbar.addWidget(snippet_button)

        toolbar.setStyleSheet(
            "QToolBar { background: #ffffff; spacing: 8px; padding: 8px; border-bottom: 1px solid #dbe2ec; }"
            "QToolButton { color: #0b172a; padding: 7px 10px; border-radius: 8px; }"
            "QToolButton:hover { background: #e9eef5; }"
            "QToolButton:checked { background: #d7e7fb; color: #0a66c2; }"
        )
        self.addToolBar(toolbar)

    def _create_context_menu(self) -> None:
        self.editor.setContextMenuPolicy(Qt.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos: QPoint) -> None:
        menu = self.editor.createStandardContextMenu()
        menu.addSeparator()
        menu.addAction(self.compile_action)
        menu.addAction(self.live_preview_action)
        menu.addAction(self.open_pdf_action)

        snippet_menu = QMenu("Insert snippet", self)
        for action in (
            self.section_action,
            self.figure_action,
            self.table_action,
            self.equation_action,
            self.list_action,
            self.bibliography_action,
            self.toc_action,
            self.theorem_action,
            self.code_action,
        ):
            snippet_menu.addAction(action)
        menu.addMenu(snippet_menu)
        menu.exec(self.editor.mapToGlobal(pos))

    def _update_title(self) -> None:
        filename = self.current_file.name if self.current_file else "Untitled.tex"
        self.setWindowTitle(f"PLATEX – {filename}")

    def _schedule_live_preview(self) -> None:
        if not self.live_preview_enabled:
            return
        self.live_preview_timer.start()

    def _toggle_live_preview(self, enabled: bool) -> None:
        self.live_preview_enabled = enabled
        if enabled:
            self.status.showMessage("Live preview on – compiling after edits", 2000)
            self._schedule_live_preview()
        else:
            self.status.showMessage("Live preview paused", 2000)

    def new_file(self) -> None:
        if self._confirm_discard_changes():
            self.editor.clear()
            if self.project_root:
                self.current_file = self.project_root / "main.tex"
            else:
                self.current_file = None
            self.last_pdf_output = None
            self._update_title()
            self.status.showMessage("New file created", 2000)

    def create_project(self) -> None:
        base_dir = QFileDialog.getExistingDirectory(self, "Choose where to create your project")
        if not base_dir:
            return

        project_name, ok = QInputDialog.getText(self, "Project name", "Name your project")
        if not ok or not project_name.strip():
            return

        target = Path(base_dir) / project_name.strip()
        try:
            target.mkdir(parents=True, exist_ok=True)
            (target / "images").mkdir(exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "Error", f"Could not create project folder: {exc}")
            return

        main_tex = target / "main.tex"
        bib_file = target / "references.bib"
        if not main_tex.exists():
            main_tex.write_text(
                """\\documentclass{article}
\\usepackage[utf8]{inputenc}
\\usepackage{graphicx}
\\title{Project Title}
\\author{Your Name}
\\begin{document}
\\maketitle

\\section{Overview}
Welcome to your new PLATEX project. Add sections, figures, and more from the toolbar.

\\section{Next steps}
\\begin{itemize}
  \item Add images to the images/ folder and reference them with \includegraphics.
  \item Insert figures, tables, and bibliography snippets from the toolbar.
  \item Compile to preview the PDF on the right.
\\end{itemize}

\\bibliographystyle{plain}
\\bibliography{references}
\\end{document}
""",
                encoding="utf-8",
            )

        if not bib_file.exists():
            bib_file.write_text(
                """@article{example,
  title={Getting Started with PLATEX},
  author={Author, A.},
  journal={Journal of Examples},
  year={2024}
}
""",
                encoding="utf-8",
            )

        self.project_root = target
        self._load_file(main_tex)
        self.status.showMessage(f"Project created at {target}", 4000)

    def open_project(self) -> None:
        target = QFileDialog.getExistingDirectory(self, "Open project folder")
        if not target:
            return

        project_path = Path(target)
        tex_files = list(project_path.glob("*.tex"))
        if not tex_files:
            QMessageBox.information(self, "No TeX file", "That folder has no .tex files to open.")
            return

        self.project_root = project_path
        self._load_file(tex_files[0])
        self.status.showMessage(f"Opened project {project_path}", 3000)

    def new_from_template(self) -> None:
        if not self._confirm_discard_changes():
            return

        templates = {
            "Article": """\\documentclass{article}
\\usepackage[utf8]{inputenc}
\\usepackage{amsmath,amssymb}
\\title{Your Title}
\\author{Your Name}
\\begin{document}
\\maketitle

\\section{Introduction}
Start writing here.

\\end{document}
""",
            "Report": """\\documentclass{report}
\\usepackage[utf8]{inputenc}
\\usepackage{graphicx}
\\title{Project Report}
\\author{Your Name}
\\begin{document}
\\maketitle

\\chapter{Overview}
Content goes here.

\\end{document}
""",
            "Beamer": """\\documentclass{beamer}
\\usetheme{Madrid}
\\title{Your Talk}
\\author{Your Name}
\\begin{document}
\\begin{frame}\titlepage\end{frame}
\\begin{frame}{Agenda}
  \begin{itemize}
    \item Point 1
    \item Point 2
  \end{itemize}
\\end{frame}
\\end{document}
""",
        }

        names = list(templates.keys())
        name, ok = QInputDialog.getItem(self, "New from template", "Choose a starting point", names, 0, False)
        if ok and name in templates:
            self.editor.setPlainText(templates[name])
            self.current_file = None
            self._update_title()
            self.status.showMessage(f"Loaded {name} template", 2000)

    def open_file(self) -> None:
        start_dir = str(self.project_root) if self.project_root else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open LaTeX File", start_dir, "TeX Files (*.tex);;All Files (*)"
        )
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
        self.last_pdf_output = None
        self._update_title()
        self.status.showMessage(f"Opened {path}", 2000)

    def save_file(self, save_as: bool = False) -> None:
        if save_as or not self.current_file:
            default_dir = str(self.project_root) if self.project_root else ""
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save LaTeX File",
                os.path.join(default_dir, "Untitled.tex") if default_dir else "Untitled.tex",
                "TeX Files (*.tex);;All Files (*)",
            )
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

    def compile_pdf(self, auto: bool = False) -> None:
        if self.is_compiling:
            return
        self.is_compiling = True
        if not self.current_file:
            base = self.project_root or Path.home() / "PLATEX"
            base.mkdir(parents=True, exist_ok=True)
            self.current_file = base / "main.tex"

        assert self.current_file is not None
        self.save_file()
        tex_file = self.current_file
        pdf_output = tex_file.with_suffix(".pdf")
        self.last_pdf_output = pdf_output

        command = self._detect_compiler()
        if not command:
            self.status.showMessage("Preparing LaTeX toolchain…", 4000)
            command = self._install_toolchain()
        if not command:
            if not auto:
                QMessageBox.warning(
                    self,
                    "Compiler missing",
                    "No LaTeX compiler was found or could be installed automatically.\n"
                    "Please install TeX Live (macOS/Linux) or MiKTeX (Windows) and try again.",
                )
            self.is_compiling = False
            return

        if not auto:
            self.status.showMessage("Compiling…", 2000)
        env = os.environ.copy()
        env.setdefault("MIKTEX_AUTOINSTALL", "1")
        env.setdefault("MIKTEX_ON_THE_FLY", "1")

        cmd_name = Path(command).name.lower()
        compile_cmd = [command, "-interaction=nonstopmode", str(tex_file.name if tex_file.parent else tex_file)]
        if "latexmk" in cmd_name:
            compile_cmd = [command, "-pdf", "-interaction=nonstopmode", "-halt-on-error", tex_file.name]

        try:
            result = subprocess.run(
                compile_cmd,
                cwd=tex_file.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=60,
                check=False,
                env=env,
            )
        except subprocess.TimeoutExpired:
            if not auto:
                QMessageBox.critical(self, "Timeout", "Compilation took too long and was stopped.")
            self.is_compiling = False
            return
        except OSError as exc:
            if not auto:
                QMessageBox.critical(self, "Error", f"Failed to run compiler: {exc}")
            self.is_compiling = False
            return

        if result.returncode == 0 and pdf_output.exists():
            self.status.showMessage("Compilation successful (preview refreshed)", 2000)
            self._load_preview(pdf_output)
        else:
            if not auto:
                QMessageBox.critical(self, "Compilation failed", result.stdout or "No output")
            else:
                self.status.showMessage("Live preview compile failed – check document", 3000)
        self.is_compiling = False

    def _load_preview(self, pdf_output: Path) -> None:
        load_status = self.preview_document.load(str(pdf_output))
        if load_status == QPdfDocument.Status.Ready:
            self.preview.setPageMode(QPdfView.PageMode.MultiPage)
            self.preview.update()
            return
        self.status.showMessage("Preview unavailable – PDF saved to disk", 4000)

    def open_pdf_externally(self) -> None:
        if not self.last_pdf_output or not self.last_pdf_output.exists():
            QMessageBox.information(
                self,
                "No PDF yet",
                "Compile your document first, then click this to open the generated PDF.",
            )
            return

        path = self.last_pdf_output
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
        for candidate in ("latexmk", "pdflatex", "xelatex"):
            path = shutil.which(candidate)
            if path:
                return path
        return None

    def _install_toolchain(self) -> str | None:
        """Best-effort, unattended installation of a LaTeX toolchain."""
        if sys.platform.startswith("win"):
            if shutil.which("winget"):
                self.status.showMessage("Installing MiKTeX via winget…", 4000)
                subprocess.run(
                    [
                        "winget",
                        "install",
                        "--id",
                        "MiKTeX.MiKTeX",
                        "-e",
                        "--silent",
                        "--accept-package-agreements",
                        "--accept-source-agreements",
                    ],
                    check=False,
                )
                subprocess.run(["initexmf", "--mklinks", "--force"], check=False)
                subprocess.run(["mpm", "--admin", "--update-db"], check=False)
                subprocess.run(["mpm", "--admin", "--install=collection-latexrecommended"], check=False)
            else:
                QMessageBox.information(
                    self,
                    "Install MiKTeX",
                    "Please install MiKTeX from https://miktex.org/download to compile locally.",
                )
        elif sys.platform.startswith("darwin"):
            if shutil.which("brew"):
                self.status.showMessage("Installing BasicTeX via Homebrew…", 4000)
                subprocess.run(["brew", "install", "--cask", "basictex"], check=False)
                subprocess.run(["sudo", "/Library/TeX/texbin/tlmgr", "option", "repository", "https://mirror.ctan.org/systems/texlive/tlnet"], check=False)
                subprocess.run(["sudo", "/Library/TeX/texbin/tlmgr", "update", "--self", "--all"], check=False)
                subprocess.run(["sudo", "/Library/TeX/texbin/tlmgr", "install", "latexmk"], check=False)
        else:
            if shutil.which("apt-get"):
                self.status.showMessage("Installing TeX Live (this may take a few minutes)…", 4000)
                subprocess.run(["sudo", "apt-get", "update"], check=False)
                subprocess.run(["sudo", "apt-get", "install", "-y", "texlive-full", "latexmk"], check=False)

        return self._detect_compiler()

    def insert_snippet(self, kind: str) -> None:
        snippets = {
            "figure": """\\begin{figure}[h]
  \centering
  \includegraphics[width=0.8\\linewidth]{example-image}
  \caption{Caption text}
  \label{fig:label}
\\end{figure}

""",
            "table": """\\begin{table}[h]
  \centering
  \begin{tabular}{lll}
    \hline
    A & B & C \\
    \hline
    1 & 2 & 3 \\
    4 & 5 & 6 \\
    \hline
  \end{tabular}
  \caption{Table caption}
  \label{tab:label}
\\end{table}

""",
            "bibliography": """% Add this near the end of your document
\\bibliographystyle{plain}
\\bibliography{references}

% Example .bib entry
% @article{key,
%   title={Example},
%   author={Author, A.},
%   journal={Journal},
%   year={2024}
% }
""",
            "section": """\\section{New Section}
Write your section text here.

""",
            "equation": """\\begin{equation}
E = mc^2
\\end{equation}

""",
            "list": """\\begin{itemize}
  \item First item
  \item Second item
\\end{itemize}

""",
            "toc": """% Table of contents
\\tableofcontents
\\newpage

""",
            "theorem": """% Add to preamble: \\usepackage{amsthm}
\\begin{theorem}[Sample]
Let a, b \in \mathbb{R}. Then a + b = b + a.
\\end{theorem}

""",
            "code": """% Add to preamble: \\usepackage{listings}
\\begin{lstlisting}[language=Python, caption={Example code}]
def hello():
    print("Hello, PLATEX!")
\\end{lstlisting}

""",
        }

        text = snippets.get(kind)
        if text:
            cursor = self.editor.textCursor()
            cursor.insertText(text)
            self.status.showMessage(f"Inserted {kind} snippet", 2000)

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
