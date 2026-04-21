import os
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QTextEdit, QSystemTrayIcon, QMenu, QStyle
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QAction
from qfluentwidgets import (
    setTheme, Theme, PrimaryPushButton, PushButton, 
    SubtitleLabel, BodyLabel, ListWidget, InfoBar, InfoBarPosition, ProgressBar, CheckBox
)

from app.assistant_window import AssistantWindow
from core.rag_engine import RAGIndexThread
from core.vector_store import get_vector_store

class WelcomeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Set Dark Fluent Theme
        setTheme(Theme.DARK)
        
        self.setWindowTitle("AI Sales Meeting Assistant")
        self.resize(550, 400)
        
        # System Tray Setup
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        
        tray_menu = QMenu()
        show_action = QAction("Show Dashboard", self)
        show_action.triggered.connect(self.show)
        exit_action = QAction("Exit App", self)
        exit_action.triggered.connect(self.close)
        
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

        # Initialize Vector Store
        try:
            self.store = get_vector_store()
        except Exception as e:
            print(f"Error connecting to Qdrant: {e}")
            self.store = None

        self.central_widget = QWidget()
        self.central_widget.setObjectName("WelcomeCentral")
        self.central_widget.setStyleSheet("QWidget#WelcomeCentral { background-color: #202020; }")
        self.setCentralWidget(self.central_widget)
        
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(30, 30, 30, 30)
        self.layout.setSpacing(20)
        
        # Title and Subtitle
        self.title = SubtitleLabel("AI Sales Meeting Assistant", self)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.desc = BodyLabel("Your unobtrusive AI companion for sales calls.", self)
        self.desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.desc.setTextColor("#A0A0A0")
        
        self.layout.addWidget(self.title)
        self.layout.addWidget(self.desc)
        
        # --- DASHBOARD: Dual Lists ---
        self.lists_container = QWidget()
        self.lists_layout = QHBoxLayout(self.lists_container)
        self.lists_layout.setContentsMargins(0, 0, 0, 0)
        self.lists_layout.setSpacing(20)
        
        # Left: Documents
        self.doc_pane = QWidget()
        self.doc_vbox = QVBoxLayout(self.doc_pane)
        self.doc_vbox.setContentsMargins(0,0,0,0)
        self.doc_header = BodyLabel("Knowledge Base Documents:", self)
        self.doc_list = ListWidget(self)
        self.doc_list.setSelectionMode(ListWidget.SelectionMode.MultiSelection)
        self.doc_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.doc_vbox.addWidget(self.doc_header)
        self.doc_vbox.addWidget(self.doc_list)
        self.lists_layout.addWidget(self.doc_pane)
        
        # Right: Recent Transcripts
        self.transcript_pane = QWidget()
        self.transcript_vbox = QVBoxLayout(self.transcript_pane)
        self.transcript_vbox.setContentsMargins(0,0,0,0)
        self.transcript_header = BodyLabel("Meeting History:", self)
        self.transcript_list = ListWidget(self)
        self.transcript_list.itemClicked.connect(self.view_logged_transcript)
        self.transcript_vbox.addWidget(self.transcript_header)
        self.transcript_vbox.addWidget(self.transcript_list)
        self.lists_layout.addWidget(self.transcript_pane)
        
        self.layout.addWidget(self.lists_container)

        # Action Buttons Container
        self.buttons_container = QWidget()
        self.button_layout = QHBoxLayout(self.buttons_container)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setSpacing(15)
        
        self.upload_btn = PushButton("Upload New Document", self)
        self.upload_btn.clicked.connect(self.upload_document)
        
        self.delete_btn = PushButton("Delete Selected", self)
        self.delete_btn.setObjectName("DeleteBtn")
        self.delete_btn.setStyleSheet("QPushButton#DeleteBtn { color: #f44336; }")
        self.delete_btn.clicked.connect(self.delete_selected_document)
        self.delete_btn.hide()
        
        self.start_btn = PrimaryPushButton("Start Session", self)
        self.start_btn.clicked.connect(self.start_session)
        
        self.button_layout.addWidget(self.upload_btn)
        self.button_layout.addWidget(self.delete_btn)
        self.button_layout.addWidget(self.start_btn)
        self.layout.addWidget(self.buttons_container)
        
        # Stealth Mode Option
        self.stealth_checkbox = CheckBox("Start in Background (Stealth Mode)", self)
        self.stealth_checkbox.setToolTip("Hides all UI elements. Use Ctrl+Space for manual refinement.")
        self.layout.addWidget(self.stealth_checkbox, alignment=Qt.AlignmentFlag.AlignCenter)

        # Progress Bar overlay for indexing
        self.progress_bar = ProgressBar(self)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()
        self.layout.addWidget(self.progress_bar)

        # Summary Elements (Hidden initially)
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setStyleSheet("""
            QTextEdit {
                background-color: #2D2D2D; 
                color: #E0E0E0; 
                border: 1px solid #444; 
                border-radius: 6px; 
                padding: 10px;
                font-family: 'Inter', sans-serif; 
                font-size: 14px;
            }
        """)
        self.summary_text.hide()
        self.layout.addWidget(self.summary_text)

        self.back_btn = PushButton("Back to Dashboard", self)
        self.back_btn.clicked.connect(self.return_to_dashboard)
        self.back_btn.hide()
        self.layout.addWidget(self.back_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.assistant_window = None
        self.index_thread = None
        
        self.refresh_document_list()
        self.refresh_transcript_list()
        self.center_on_screen()

    def refresh_document_list(self):
        self.doc_list.clear()
        self.delete_btn.hide()
        if self.store:
            docs = self.store.list_documents()
            if docs:
                for doc in docs:
                    self.doc_list.addItem(f"📄 {doc}")
            else:
                self.doc_list.addItem("No documents found in knowledge base.")
        else:
            self.doc_list.addItem("Database connection error.")

    def refresh_transcript_list(self):
        self.transcript_list.clear()
        transcripts_dir = os.path.join(os.getcwd(), "transcripts")
        if not os.path.exists(transcripts_dir):
            os.makedirs(transcripts_dir, exist_ok=True)
        
        files = [f for f in os.listdir(transcripts_dir) if f.endswith(".txt")]
        # Sort by date (filename has YYYY-MM-DD_HH-MM-SS)
        files.sort(reverse=True)
        
        if files:
            for f in files:
                self.transcript_list.addItem(f"📝 {f}")
        else:
            self.transcript_list.addItem("No previous transcripts found.")

    def on_selection_changed(self):
        selected_items = self.doc_list.selectedItems()
        valid_selection = any("📄" in item.text() for item in selected_items)
        if valid_selection:
            self.delete_btn.show()
        else:
            self.delete_btn.hide()

    def toggle_selection(self, item):
        # Deprecated by on_selection_changed but keeping for compatibility if called elsewhere
        pass

    def view_logged_transcript(self, item):
        if "📝" not in item.text():
            return
        
        filename = item.text().replace("📝 ", "").strip()
        file_path = os.path.join(os.getcwd(), "transcripts", filename)
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.show_summary_view(content, f"Viewing: {filename}")
        except Exception as e:
            InfoBar.error("Error", f"Could not read transcript: {e}", parent=self)

    def delete_selected_document(self):
        item = self.doc_list.currentItem()
        if not item or "📄" not in item.text():
            return
        filename = item.text().replace("📄 ", "").strip()
        try:
            self.store.delete_document(filename)
            self.refresh_document_list()
            InfoBar.success("Deleted", f"Removed {filename}", duration=3000, parent=self)
        except Exception as e:
            InfoBar.error("Error", f"Failed to delete: {e}", duration=4000, parent=self)

    def upload_document(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Document", "", "Documents (*.pdf *.txt)")
        if file_path:
            self.start_btn.setDisabled(True)
            self.upload_btn.setDisabled(True)
            self.progress_bar.show()
            self.index_thread = RAGIndexThread(file_path)
            self.index_thread.finished.connect(self.on_index_finished)
            self.index_thread.error.connect(self.on_index_error)
            self.index_thread.start()

    def on_index_finished(self, assistant):
        self.progress_bar.hide()
        self.start_btn.setDisabled(False)
        self.upload_btn.setDisabled(False)
        
        # Determine the name of the file we just uploaded from the thread if possible
        new_filename = None
        if hasattr(self, "index_thread") and self.index_thread:
            new_filename = os.path.basename(self.index_thread.file_path)

        self.refresh_document_list()
        
        # Auto-select the newly uploaded document
        if new_filename:
            for i in range(self.doc_list.count()):
                item = self.doc_list.item(i)
                if new_filename in item.text():
                    item.setSelected(True)
        
        InfoBar.success("Success", "Document indexed.", duration=3000, parent=self)

    def on_index_error(self, err_msg):
        self.progress_bar.hide()
        self.start_btn.setDisabled(False)
        self.upload_btn.setDisabled(False)
        InfoBar.error("Error", f"Indexing failed: {err_msg[:40]}", duration=4000, parent=self)

    def start_session(self):
        if not self.store:
            InfoBar.error("Error", "Database not connected.", duration=3000, parent=self)
            return

        # Gather selected documents
        selected_items = self.doc_list.selectedItems()
        selected_docs = [item.text().replace("📄 ", "").strip() for item in selected_items if "📄" in item.text()]
        
        from core.rag_engine import SalesAssistant
        rag_assistant = SalesAssistant(self.store, selected_docs=selected_docs)
        is_stealth = self.stealth_checkbox.isChecked()

        self.assistant_window = AssistantWindow(rag_assistant, is_stealth=is_stealth)
        self.assistant_window.session_ended.connect(self.on_session_ended)
        self.assistant_window.show()
        
        self.hide()

    def on_session_ended(self, clean_transcript):
        self.show_summary_view(clean_transcript, "Meeting Ended Automatically Saved")
        self.refresh_transcript_list()

    def show_summary_view(self, text, subtitle):
        self.lists_container.hide()
        self.buttons_container.hide()
        
        self.title.setText("Meeting Transcript")
        self.desc.setText(subtitle)
        
        self.summary_text.setPlainText(text)
        self.summary_text.show()
        self.back_btn.show()
        
        self.resize(650, 550)
        self.center_on_screen()
        self.show()

    def return_to_dashboard(self):
        self.summary_text.hide()
        self.back_btn.hide()
        
        self.title.setText("AI Sales Meeting Assistant")
        self.desc.setText("Your unobtrusive AI companion for sales calls.")
        
        self.lists_container.show()
        self.buttons_container.show()
        
        self.resize(550, 400)
        self.center_on_screen()
        self.refresh_transcript_list()

    def closeEvent(self, event):
        from core.vector_store import close_vector_store
        close_vector_store()
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()

    def center_on_screen(self):
        screen = self.screen().availableGeometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()
