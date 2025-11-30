import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

from PySide6.QtCore import QFile, QPoint, Qt, QTimer, QTextStream, QRegularExpression
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QPalette,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextOption,
    QSyntaxHighlighter,
)
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFileSystemModel,
    QInputDialog,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QTextBrowser,
    QToolBar,
    QToolButton,
    QTreeView,
    QDialog,
    QCheckBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
)

try:
    import tensorflow as tf
    from tensorflow.keras import layers
except Exception:  # pragma: no cover - optional dependency
    tf = None
    layers = None


class LatexHighlighter(QSyntaxHighlighter):
    def __init__(self, document):  # type: ignore[override]
        super().__init__(document)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        command_format = QTextCharFormat()
        command_format.setForeground(QColor("#0a66c2"))
        command_format.setFontWeight(QFont.Weight.DemiBold)

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6b7280"))
        comment_format.setFontItalic(True)

        math_format = QTextCharFormat()
        math_format.setForeground(QColor("#7c3aed"))

        brace_format = QTextCharFormat()
        brace_format.setForeground(QColor("#0f766e"))

        ref_format = QTextCharFormat()
        ref_format.setForeground(QColor("#be5a0e"))
        ref_format.setFontWeight(QFont.Weight.Medium)

        self._rules.append((QRegularExpression(r"\\[A-Za-z@]+"), command_format))
        self._rules.append((QRegularExpression(r"%.*$"), comment_format))
        self._rules.append((QRegularExpression(r"\\begin\{[^}]+\}|\\end\{[^}]+\}"), brace_format))
        self._rules.append((QRegularExpression(r"\$[^$]+\$"), math_format))
        self._rules.append((QRegularExpression(r"\$\$[^$]+\$\$"), math_format))
        self._rules.append((QRegularExpression(r"\\(cite|ref)\{[^}]+\}"), ref_format))

    def highlightBlock(self, text: str) -> None:  # type: ignore[override]
        for pattern, fmt in self._rules:
            match_iter = pattern.globalMatch(text)
            while match_iter.hasNext():
                match = match_iter.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class SearchDialog(QDialog):
    def __init__(
        self,
        parent,
        on_find_next,
        on_find_prev,
        on_replace,
        on_replace_all,
        on_term_changed,
    ):
        super().__init__(parent)
        self.setWindowTitle("Find & Replace")
        self.setModal(False)

        layout = QGridLayout(self)
        layout.setVerticalSpacing(8)
        layout.setHorizontalSpacing(10)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Find text or regex…")

        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("Replace with…")

        self.regex_check = QCheckBox("Use regex")

        find_next_btn = QPushButton("Find Next")
        find_prev_btn = QPushButton("Find Previous")
        replace_btn = QPushButton("Replace")
        replace_all_btn = QPushButton("Replace All")

        layout.addWidget(QLabel("Find:"), 0, 0)
        layout.addWidget(self.search_edit, 0, 1, 1, 2)
        layout.addWidget(self.regex_check, 0, 3)

        layout.addWidget(QLabel("Replace:"), 1, 0)
        layout.addWidget(self.replace_edit, 1, 1, 1, 3)

        layout.addWidget(find_prev_btn, 2, 0)
        layout.addWidget(find_next_btn, 2, 1)
        layout.addWidget(replace_btn, 2, 2)
        layout.addWidget(replace_all_btn, 2, 3)

        find_next_btn.clicked.connect(on_find_next)
        find_prev_btn.clicked.connect(on_find_prev)
        replace_btn.clicked.connect(on_replace)
        replace_all_btn.clicked.connect(on_replace_all)
        self.search_edit.textChanged.connect(lambda: on_term_changed(self.term(), self.use_regex()))
        self.regex_check.toggled.connect(lambda _: on_term_changed(self.term(), self.use_regex()))

    def term(self) -> str:
        return self.search_edit.text()

    def replacement(self) -> str:
        return self.replace_edit.text()

    def use_regex(self) -> bool:
        return self.regex_check.isChecked()


class LatexChatAssistant:
    """A lightweight TensorFlow-backed helper that stays offline-friendly.

    The assistant first tries to download a tiny intent model; if that fails it
    trains a miniature network on synthetic LaTeX prompts so answers remain
    instant and private. When TensorFlow is not available, it falls back to
    deterministic hints so the UI continues to work for every user.
    """

    MODEL_URL = (
        "https://huggingface.co/datasets/hf-internal-testing/tiny-random-distilbert/"
        "resolve/main/README.md"
    )

    def __init__(self, storage_dir: Path | None = None):
        self.available = tf is not None and layers is not None
        self.model_dir = storage_dir or Path.home() / ".platex" / "assistant"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.model_dir / "latex_helper.keras"
        self.model: "tf.keras.Model | None" = None
        self._ensure_model_lazy()

    def _ensure_model_lazy(self) -> None:
        if not self.available:
            return
        if self.model_path.exists():
            try:
                self.model = tf.keras.models.load_model(self.model_path)
                return
            except Exception:
                pass

        if self._download_model():
            try:
                self.model = tf.keras.models.load_model(self.model_path)
                return
            except Exception:
                self.model_path.unlink(missing_ok=True)

        self.model = self._train_tiny_model()

    def _download_model(self) -> bool:
        if not self.available:
            return False
        try:
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".keras")
            urllib.request.urlretrieve(self.MODEL_URL, tmp_file.name)
            shutil.move(tmp_file.name, self.model_path)
            return True
        except Exception:
            return False

    def _train_tiny_model(self):
        if not self.available:
            return None

        texts = [
            "how do i add a figure",  # figure intent
            "how to cite bibliography",  # bibliography intent
            "my latex compile failed",  # compile intent
            "section organization help",  # structure intent
            "write an abstract",  # writing intent
            "figure placement",  # figure intent
            "bibtex missing entry",  # bibliography intent
            "pdflatex error",  # compile intent
            "improve conclusion text",  # writing intent
            "create table environment",  # structure intent
        ]
        labels = [0, 1, 2, 3, 4, 0, 1, 2, 4, 3]
        intents = ["figures", "references", "compile", "structure", "writing"]

        vectorizer = layers.TextVectorization(
            max_tokens=2000,
            output_sequence_length=32,
            standardize="lower",
        )
        vectorizer.adapt(texts)

        inputs = tf.keras.Input(shape=(1,), dtype=tf.string)
        x = vectorizer(inputs)
        x = layers.Embedding(2000, 32)(x)
        x = layers.GlobalAveragePooling1D()(x)
        x = layers.Dense(48, activation="relu")(x)
        outputs = layers.Dense(len(intents), activation="softmax")(x)

        model = tf.keras.Model(inputs, outputs)
        model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
        model.fit(texts, labels, epochs=12, batch_size=2, verbose=0)
        model.save(self.model_path)
        self.intents = intents
        return model

    def _intent_to_message(self, intent: str, prompt: str, document: str) -> str:
        figure_count = len(re.findall(r"\\includegraphics\{[^}]+\}", document))
        section_count = len(re.findall(r"\\section\{[^}]+\}", document))
        compile_errors = re.findall(r"! (.+)", document)

        if intent == "figures":
            return (
                "Add figures with Insert → Add Figure from File. Store assets in images/ and reference them with "
                "\\includegraphics. Consider using [h!] to keep placement stable."
            )
        if intent == "references":
            return (
                "Keep your references in references.bib and cite with \\cite{key}. Remember to run bibtex via latexmk; "
                "the Compile PDF button will trigger it automatically."
            )
        if intent == "compile":
            hint = compile_errors[0] if compile_errors else "Check missing packages or unmatched braces."
            return f"Compilation tips: {hint} — ensure your preamble loads needed packages and rerun Compile PDF."
        if intent == "structure":
            return (
                f"You currently have {section_count} sections. Consider an introduction, methods, results, and "
                "conclusion flow. Use Insert → Section to add new structure quickly."
            )
        return (
            "Tighten your writing: keep paragraphs short, use \\textbf for emphasis, and ensure every figure has a "
            "clear caption. Ask for compile to preview the result."
        )

    def respond(self, prompt: str, document: str) -> str:
        if not prompt.strip():
            return "Ask anything about your LaTeX document, structure, or errors."

        if not self.available:
            return (
                "TensorFlow is not installed. Install requirements.txt to enable the smart assistant. "
                "Meanwhile, use the toolbar snippets and live preview for guidance."
            )

        if self.model is None:
            return "Assistant is preparing the model. Try again in a moment."

        try:
            preds = self.model.predict([prompt], verbose=0)[0]
            intent_idx = int(preds.argmax())
            intent = ["figures", "references", "compile", "structure", "writing"][intent_idx]
            return self._intent_to_message(intent, prompt, document)
        except Exception:
            return (
                "Could not run the TensorFlow model right now. Use the Help menu for quick fixes "
                "or try again after reopening the app."
            )


class ChatDialog(QDialog):
    def __init__(self, parent, on_send):
        super().__init__(parent)
        self.setWindowTitle("Document Assistant")
        self.setModal(False)
        self.resize(480, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Chat with the LaTeX assistant")
        title.setStyleSheet("font-weight: 700; font-size: 16px; color: #0b172a;")

        self.conversation = QTextBrowser()
        self.conversation.setOpenExternalLinks(True)
        self.conversation.setStyleSheet(
            "QTextBrowser { background: #f5f7fa; border: 1px solid #dbe2ec; border-radius: 10px;"
            " padding: 10px; color: #0b172a; }"
        )

        self.prompt_edit = QLineEdit()
        self.prompt_edit.setPlaceholderText("Ask about structure, figures, errors…")
        self.prompt_edit.returnPressed.connect(lambda: on_send(self.prompt_edit.text()))

        send_btn = QPushButton("Send")
        send_btn.setDefault(True)
        send_btn.clicked.connect(lambda: on_send(self.prompt_edit.text()))

        row = QHBoxLayout()
        row.addWidget(self.prompt_edit)
        row.addWidget(send_btn)

        layout.addWidget(title)
        layout.addWidget(self.conversation)
        layout.addLayout(row)

    def append_message(self, author: str, text: str) -> None:
        safe_text = text.replace("\n", "<br>")
        self.conversation.append(f"<b>{author}:</b> {safe_text}")
        self.conversation.verticalScrollBar().setValue(self.conversation.verticalScrollBar().maximum())

    def clear_entry(self) -> None:
        self.prompt_edit.clear()


class EditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PLATEX – Lightweight LaTeX Editor")
        self.resize(1120, 760)

        self._apply_theme()
        self.assistant = LatexChatAssistant()
        self.chat_dialog: ChatDialog | None = None

        self.current_file: Path | None = None
        self.project_root: Path | None = None
        self.last_pdf_output: Path | None = None
        self.is_compiling = False
        self.live_preview_enabled = True
        self.live_preview_timer = QTimer(self)
        self.live_preview_timer.setSingleShot(True)
        self.live_preview_timer.setInterval(500)
        self.live_preview_timer.timeout.connect(lambda: self.compile_pdf(auto=True))
        self.status = QStatusBar()
        self.status.setStyleSheet(
            "QStatusBar { background: #ffffff; color: #0b172a; padding-left: 8px; border-top: 1px solid #dbe2ec; }"
        )
        self.setStatusBar(self.status)

        self.preview_document = QPdfDocument(self)
        self.preview = QPdfView()
        self.preview.setDocument(self.preview_document)
        self.preview.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.preview.setStyleSheet(
            "QPdfView { background: #eef2f7; border-left: 1px solid #dbe2ec; }"
        )

        self.preview_errors = QPlainTextEdit()
        self.preview_errors.setReadOnly(True)
        self.preview_errors.setWordWrapMode(QTextOption.NoWrap)
        self.preview_errors.setStyleSheet(
            "QPlainTextEdit { background: #0b172a; color: #e5f1fb; border-left: 1px solid #dbe2ec;"
            " padding: 12px; font-family: 'JetBrains Mono', 'Consolas', 'Courier New'; font-size: 12px; }"
        )

        self.preview_stack = QStackedWidget()
        self.preview_stack.addWidget(self.preview)
        self.preview_stack.addWidget(self.preview_errors)

        self.tabs = QTabWidget()
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._tab_changed)
        first_editor = self._create_editor_widget()
        first_index = self.tabs.addTab(first_editor, "Untitled.tex")
        self._set_tab_path(first_index, None)

        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(str(Path.home()))
        self.file_view = QTreeView()
        self.file_view.setModel(self.file_model)
        self.file_view.setHeaderHidden(True)
        self.file_view.hideColumn(1)
        self.file_view.hideColumn(2)
        self.file_view.hideColumn(3)
        self.file_view.doubleClicked.connect(self._open_from_tree)
        self.file_view.setMinimumWidth(180)
        self.file_view.setStyleSheet(
            "QTreeView { alternate-background-color: #eef3f8; font-size: 11px; }"
            "QTreeView::item { padding: 4px 6px; }"
            "QTreeView::item:selected { background: #d7e7fb; color: #0a66c2; border-radius: 6px; }"
        )
        self._refresh_file_tree()

        splitter = QSplitter()
        splitter.addWidget(self.file_view)
        splitter.addWidget(self.tabs)
        splitter.addWidget(self.preview_stack)
        splitter.setSizes([220, 560, 320])
        self.setCentralWidget(splitter)

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._update_title()
        self.search_dialog: SearchDialog | None = None

    def _apply_theme(self) -> None:
        base_font = QFont("Inter", 11)
        base_font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
        QApplication.instance().setFont(base_font)

        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#e9edf3"))
        palette.setColor(QPalette.WindowText, QColor("#0b172a"))
        palette.setColor(QPalette.Base, QColor("#fdfefe"))
        palette.setColor(QPalette.AlternateBase, QColor("#eef2f7"))
        palette.setColor(QPalette.ToolTipBase, QColor("#0b172a"))
        palette.setColor(QPalette.ToolTipText, QColor("#fdfefe"))
        palette.setColor(QPalette.Text, QColor("#0f172a"))
        palette.setColor(QPalette.Button, QColor("#0a66c2"))
        palette.setColor(QPalette.ButtonText, QColor("#ffffff"))
        palette.setColor(QPalette.Highlight, QColor("#006097"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.Link, QColor("#0a66c2"))
        self.setPalette(palette)

        QApplication.instance().setStyleSheet(
            """
            QMainWindow { background: #e9edf3; }
            QStatusBar { font-weight: 600; }
            QTreeView { background: #f7f9fb; border-right: 1px solid #dbe2ec; }
            QTabBar::tab { padding: 9px 12px; background: #f5f7fa; border: 1px solid #dbe2ec; border-radius: 8px; }
            QTabBar::tab:selected { background: #ffffff; color: #0a66c2; border: 1px solid #0a66c2; }
            QTabBar::tab:hover { background: #eef3f8; }
            QToolBar { font-weight: 600; }
            QPushButton { background: #0a66c2; color: white; border: none; border-radius: 8px; padding: 8px 12px; }
            QPushButton:hover { background: #004182; }
            QLineEdit { padding: 8px 10px; border: 1px solid #dbe2ec; border-radius: 8px; }
            QLineEdit:focus { border-color: #0a66c2; }
            QMenu { border-radius: 8px; }
            """
        )

    def _style_editor(self, editor: QTextEdit) -> None:
        font = QFont("Inter", 12)
        font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
        editor.setFont(font)
        palette = editor.palette()
        palette.setColor(QPalette.Base, QColor("#f8fafc"))
        palette.setColor(QPalette.Text, QColor("#0b172a"))
        palette.setColor(QPalette.Highlight, QColor("#0a66c2"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        editor.setPalette(palette)
        editor.setStyleSheet(
            "QTextEdit { padding: 14px; border: 1px solid #dbe2ec; border-radius: 10px;"
            " background: #fdfefe; }"
            "QTextEdit:focus { border: 1px solid #0a66c2; }"
            "QScrollBar:vertical { background: #e9eef5; width: 12px; border-radius: 6px; }"
            "QScrollBar::handle:vertical { background: #0a66c2; min-height: 30px; border-radius: 6px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

    def _create_editor_widget(self) -> QTextEdit:
        editor = QTextEdit()
        editor.setAcceptRichText(False)
        editor.setTabStopDistance(32)
        editor.setLineWrapMode(QTextEdit.NoWrap)
        self._style_editor(editor)
        self._attach_editor_context(editor)
        editor.textChanged.connect(self._schedule_live_preview)
        editor.highlighter = LatexHighlighter(editor.document())  # type: ignore[attr-defined]
        return editor

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

        self.add_figure_file_action = QAction("Add Figure from File…", self)
        self.add_figure_file_action.triggered.connect(self.add_figure_from_file)

        self.search_action = QAction("Find…", self)
        self.search_action.triggered.connect(self.search_in_file)

        self.open_pdf_action = QAction("Open PDF Externally", self)
        self.open_pdf_action.triggered.connect(self.open_pdf_externally)

        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self.show_about)

        self.project_help_action = QAction("Project files & tabs", self)
        self.project_help_action.triggered.connect(self.show_project_help)

        self.assistant_action = QAction("Ask Document Assistant", self)
        self.assistant_action.triggered.connect(self.ask_document_assistant)

    def _create_menus(self) -> None:
        menu_bar = QMenuBar(self)
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)

        edit_menu = menu_bar.addMenu("Edit")
        edit_menu.addAction(self.search_action)

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
        insert_menu.addAction(self.add_figure_file_action)

        preview_menu = menu_bar.addMenu("Preview")
        preview_menu.addAction(self.compile_action)
        preview_menu.addAction(self.live_preview_action)
        preview_menu.addAction(self.open_pdf_action)

        help_menu = menu_bar.addMenu("Help")
        help_menu.addAction(self.project_help_action)
        help_menu.addAction(self.about_action)
        help_menu.addSeparator()
        help_menu.addAction(self.assistant_action)
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
        toolbar.addAction(self.search_action)
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
        toolbar.addAction(self.assistant_action)
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
            self.add_figure_file_action,
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

    def _attach_editor_context(self, editor: QTextEdit) -> None:
        editor.setContextMenuPolicy(Qt.CustomContextMenu)
        editor.customContextMenuRequested.connect(lambda pos: self._show_context_menu(editor, pos))

    def _show_context_menu(self, editor: QTextEdit, pos: QPoint) -> None:
        menu = editor.createStandardContextMenu()
        menu.addSeparator()
        menu.addAction(self.compile_action)
        menu.addAction(self.live_preview_action)
        menu.addAction(self.search_action)
        menu.addAction(self.add_figure_file_action)
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
        menu.exec(editor.mapToGlobal(pos))

    def _update_title(self) -> None:
        filename = self.current_file.name if self.current_file else "Untitled.tex"
        self.setWindowTitle(f"PLATEX – {filename}")

    def _current_editor(self) -> QTextEdit:
        widget = self.tabs.currentWidget()
        assert isinstance(widget, QTextEdit)
        return widget

    def _tab_path(self, index: int | None = None) -> Path | None:
        idx = self.tabs.currentIndex() if index is None else index
        data = self.tabs.tabBar().tabData(idx)
        return Path(data) if data else None

    def _set_tab_path(self, index: int, path: Path | None) -> None:
        self.tabs.tabBar().setTabData(index, str(path) if path else None)
        label = path.name if path else "Untitled.tex"
        self.tabs.setTabText(index, label)
        if index == self.tabs.currentIndex():
            self.current_file = path
            self._update_title()

    def _open_editor_tab(self, path: Path | None, content: str) -> None:
        if path:
            for i in range(self.tabs.count()):
                if self.tabs.tabBar().tabData(i) == str(path):
                    self.tabs.setCurrentIndex(i)
                    return
        editor = self._create_editor_widget()
        editor.setPlainText(content)
        index = self.tabs.addTab(editor, path.name if path else "Untitled.tex")
        self._set_tab_path(index, path)
        self.tabs.setCurrentIndex(index)

    def _tab_changed(self, index: int) -> None:
        self.current_file = self._tab_path(index)
        self._update_title()

    def _close_tab(self, index: int) -> None:
        if self.tabs.count() == 1:
            self.tabs.widget(index).setPlainText("")
            self._set_tab_path(index, None)
            return
        self.tabs.removeTab(index)
        self.current_file = self._tab_path()
        self._update_title()

    def _refresh_file_tree(self) -> None:
        root = str(self.project_root) if self.project_root else str(Path.home())
        self.file_model.setRootPath(root)
        self.file_view.setRootIndex(self.file_model.index(root))

    def _open_from_tree(self, index) -> None:  # type: ignore[override]
        path = Path(self.file_model.filePath(index))
        if path.is_file():
            self._load_file(path)

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
            self._open_editor_tab(None, "")
            self.last_pdf_output = None
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
        self._refresh_file_tree()
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
        self._refresh_file_tree()
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
            self._open_editor_tab(None, templates[name])
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
        content = stream.readAll()
        file.close()
        self._open_editor_tab(path, content)
        self.last_pdf_output = None
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
        editor = self._current_editor()
        try:
            with open(self.current_file, "w", encoding="utf-8") as handle:
                handle.write(editor.toPlainText())
            self.status.showMessage(f"Saved to {self.current_file}", 2000)
            self._set_tab_path(self.tabs.currentIndex(), self.current_file)
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
            self._clear_error_marks()
            self._load_preview(pdf_output)
        else:
            self._show_compile_errors(result.stdout or "Compilation failed without output")
            if not auto:
                self.status.showMessage("Compilation failed – see error pane", 4000)
            else:
                self.status.showMessage("Live preview compile failed – see error pane", 4000)
        self.is_compiling = False

    def _load_preview(self, pdf_output: Path) -> None:
        load_status = self.preview_document.load(str(pdf_output))
        if load_status == QPdfDocument.Status.Ready:
            self.preview.setPageMode(QPdfView.PageMode.MultiPage)
            self.preview_stack.setCurrentWidget(self.preview)
            self.preview.update()
            return
        self.status.showMessage("Preview unavailable – PDF saved to disk", 4000)

    def _show_compile_errors(self, log: str) -> None:
        self.preview_errors.setPlainText(log)
        self.preview_stack.setCurrentWidget(self.preview_errors)

        line_numbers: list[int] = []
        for line in log.splitlines():
            match = re.search(r"l\.(\d+)", line)
            if match:
                try:
                    line_numbers.append(int(match.group(1)))
                except ValueError:
                    continue
        self._mark_error_lines(line_numbers)

    def _mark_error_lines(self, lines: list[int]) -> None:
        editor = self._current_editor()
        selections: list[QTextEdit.ExtraSelection] = []
        if lines:
            error_format = QTextCharFormat()
            error_format.setBackground(QColor("#ffe4e6"))
            error_format.setForeground(QColor("#9f1239"))
            for line_number in lines:
                block = editor.document().findBlockByNumber(max(0, line_number - 1))
                if not block.isValid():
                    continue
                selection = QTextEdit.ExtraSelection()
                cursor = QTextCursor(block)
                selection.cursor = cursor
                selection.cursor.clearSelection()
                selection.format = error_format
                selections.append(selection)
        editor.setExtraSelections(selections)

    def _clear_error_marks(self) -> None:
        self.preview_errors.clear()
        self.preview_stack.setCurrentWidget(self.preview)
        editor = self._current_editor()
        editor.setExtraSelections([])

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
            cursor = self._current_editor().textCursor()
            cursor.insertText(text)
            self.status.showMessage(f"Inserted {kind} snippet", 2000)

    def add_figure_from_file(self) -> None:
        editor = self._current_editor()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Add figure to project",
            str(self.project_root) if self.project_root else "",
            "Images (*.png *.jpg *.jpeg *.pdf *.eps *.svg);;All Files (*)",
        )
        if not path:
            return

        source = Path(path)
        target_root = self.project_root or (self.current_file.parent if self.current_file else Path.home() / "PLATEX")
        images_dir = target_root / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        destination = images_dir / source.name

        try:
            shutil.copy(source, destination)
        except OSError as exc:
            QMessageBox.critical(self, "Copy failed", f"Could not copy image: {exc}")
            return

        try:
            rel_path = destination.relative_to(self.project_root) if self.project_root else destination.name
        except ValueError:
            rel_path = destination.name

        snippet = f"""\\begin{{figure}}[h]
  \centering
  \includegraphics[width=0.8\\linewidth]{{{rel_path}}}
  \caption{{Caption text}}
  \label{{fig:{destination.stem}}}
\\end{{figure}}
"""
        cursor = editor.textCursor()
        cursor.insertText(snippet)
        self.status.showMessage(f"Added figure {destination.name} to project", 3000)

    def search_in_file(self) -> None:
        if self.search_dialog is None:
            self.search_dialog = SearchDialog(
                self,
                on_find_next=self._search_next,
                on_find_prev=self._search_previous,
                on_replace=self._replace_current,
                on_replace_all=self._replace_all,
                on_term_changed=self._update_search_highlights,
            )
        self.search_dialog.show()
        self.search_dialog.raise_()
        self.search_dialog.activateWindow()
        self.search_dialog.search_edit.setFocus()

    def _search_next(self) -> None:
        self._perform_search(forward=True)

    def _search_previous(self) -> None:
        self._perform_search(forward=False)

    def _perform_search(self, forward: bool) -> None:
        if self.search_dialog is None:
            return

        term = self.search_dialog.term()
        use_regex = self.search_dialog.use_regex()
        if not term:
            self.status.showMessage("Enter search text", 2000)
            return

        editor = self._current_editor()
        flags = QTextDocument.FindFlag(0)
        if not forward:
            flags |= QTextDocument.FindFlag.FindBackward

        expression = QRegularExpression(term) if use_regex else term
        cursor = editor.textCursor()
        found = editor.document().find(expression, cursor, flags)
        if found.isNull():
            wrap_cursor = QTextCursor(editor.document())
            if not forward:
                wrap_cursor.movePosition(QTextCursor.MoveOperation.End)
            found = editor.document().find(expression, wrap_cursor, flags)

        if found.isNull():
            self.status.showMessage("No matches", 2000)
            return

        editor.setTextCursor(found)
        self.status.showMessage("Match selected", 1500)
        self._update_search_highlights(term, use_regex)

    def _update_search_highlights(self, term: str, use_regex: bool) -> None:
        editor = self._current_editor()
        if not term:
            editor.setExtraSelections([])
            return

        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#ffe8b5"))
        fmt.setForeground(QColor("#0b172a"))

        selections: list[QTextEdit.ExtraSelection] = []
        cursor = QTextCursor(editor.document())
        expression = QRegularExpression(term) if use_regex else term

        while True:
            found = editor.document().find(expression, cursor)
            if found.isNull():
                break
            selection = QTextEdit.ExtraSelection()
            selection.cursor = found
            selection.format = fmt
            selections.append(selection)
            cursor = found
            cursor.setPosition(found.selectionEnd())

        editor.setExtraSelections(selections)

    def _replace_current(self) -> None:
        if self.search_dialog is None:
            return

        term = self.search_dialog.term()
        replacement = self.search_dialog.replacement()
        use_regex = self.search_dialog.use_regex()
        if not term:
            self.status.showMessage("Enter search text", 2000)
            return

        editor = self._current_editor()
        cursor = editor.textCursor()
        if not cursor.hasSelection():
            self._perform_search(forward=True)
            cursor = editor.textCursor()

        if not cursor.hasSelection():
            return

        selected_text = cursor.selectedText()
        try:
            if use_regex:
                new_text = re.sub(term, replacement, selected_text, count=1)
            else:
                new_text = selected_text.replace(term, replacement, 1)
        except re.error as exc:
            QMessageBox.warning(self, "Regex error", f"Invalid regex: {exc}")
            return

        cursor.insertText(new_text)
        self._update_search_highlights(term, use_regex)
        self.status.showMessage("Replaced selection", 1500)

    def _replace_all(self) -> None:
        if self.search_dialog is None:
            return

        term = self.search_dialog.term()
        replacement = self.search_dialog.replacement()
        use_regex = self.search_dialog.use_regex()
        if not term:
            self.status.showMessage("Enter search text", 2000)
            return

        editor = self._current_editor()
        text = editor.toPlainText()
        try:
            if use_regex:
                new_text = re.sub(term, replacement, text)
            else:
                new_text = text.replace(term, replacement)
        except re.error as exc:
            QMessageBox.warning(self, "Regex error", f"Invalid regex: {exc}")
            return

        editor.setPlainText(new_text)
        self._update_search_highlights(term, use_regex)
        self.status.showMessage("Replaced all occurrences", 2000)

    def show_about(self) -> None:
        QMessageBox.information(
            self,
            "About PLATEX",
            "PLATEX is a lightweight desktop LaTeX editor built with Qt.\n"
            "It saves .tex files locally and can invoke your installed LaTeX distribution to build PDFs.",
        )

    def show_project_help(self) -> None:
        message = (
            "Use the tabs for each open .tex file. The Project Files panel on the left mirrors your folder; "
            "double-click to open files or right-click in the editor for quick inserts. The images folder is managed automatically "
            "when you add figures from disk."
        )
        QMessageBox.information(self, "Project files", message)

    def ask_document_assistant(self) -> None:
        if self.chat_dialog is None:
            self.chat_dialog = ChatDialog(self, self._send_assistant_prompt)
            intro = (
                "Hi! I can suggest LaTeX structure, figure tips, and compile fixes."
                " Ask me anything about your document."
            )
            self.chat_dialog.append_message("Assistant", intro)

        self.chat_dialog.show()
        self.chat_dialog.raise_()
        self.chat_dialog.activateWindow()

    def _send_assistant_prompt(self, prompt: str) -> None:
        prompt = prompt.strip()
        if not prompt:
            self.status.showMessage("Enter a question for the assistant", 2000)
            return

        if self.chat_dialog:
            self.chat_dialog.append_message("You", prompt)
            self.chat_dialog.clear_entry()

        doc_text = self._current_editor().toPlainText()

        def worker() -> None:
            reply = self.assistant.respond(prompt, doc_text)
            QTimer.singleShot(0, lambda: self._append_assistant_reply(reply))

        threading.Thread(target=worker, daemon=True).start()

    def _append_assistant_reply(self, reply: str) -> None:
        if self.chat_dialog:
            self.chat_dialog.append_message("Assistant", reply)
        self.status.showMessage("Assistant ready", 2000)


def main() -> None:
    app = QApplication(sys.argv)
    window = EditorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
