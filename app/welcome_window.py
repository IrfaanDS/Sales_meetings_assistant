import os
import logging
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QFileDialog, QTextEdit, QSystemTrayIcon, QMenu, QStyle,
                             QLabel, QPushButton, QScrollArea, QFrame, QCheckBox, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QAction

from app.assistant_window import AssistantWindow
from app.transcript_window import TranscriptWindow
from core.rag_engine import RAGIndexThread
from core.vector_store import get_vector_store
from .styles import get_stylesheet

class DashboardItem(QFrame):
    clicked = pyqtSignal(object)
    
    def __init__(self, icon_text, title, subtitle, color="#a5c8ff", data=None, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.data = data
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(15)
        
        icon_map = {
            "description": "📄",
            "calendar_today": "📅",
            "insert_drive_file": "📄",
            "history": "🕒"
        }
        icon_char = icon_map.get(icon_text, "•")
        
        icon = QLabel(icon_char)
        icon.setStyleSheet(f"color: {color}; font-size: 18px; margin-right: 5px;")
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: #ffffff; font-weight: 600; font-size: 13px;")
        
        sub_lbl = QLabel(subtitle)
        sub_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        
        text_layout.addWidget(title_lbl)
        text_layout.addWidget(sub_lbl)
        
        layout.addWidget(icon)
        layout.addLayout(text_layout, 1)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.data)
        super().mousePressEvent(event)

class WelcomeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Sales Meeting Assistant")
        self.setMinimumSize(700, 500)
        self.resize(1000, 700) # Open larger by default
        
        # Initialize Vector Store
        try:
            self.store = get_vector_store()
        except Exception as e:
            logging.error(f"Error connecting to Qdrant: {e}")
            self.store = None

        self.central_widget = QFrame()
        self.central_widget.setObjectName("WelcomeMainWidget")
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Header
        header = QWidget()
        header.setFixedHeight(80)
        header.setStyleSheet("background-color: transparent; border-bottom: 1px solid #2c2d31;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)
        
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        title_vbox.addStretch()
        
        title_lbl = QLabel("AI Sales Meeting Assistant")
        title_lbl.setObjectName("HeaderTitle")
        
        desc_lbl = QLabel("Your AI copilot for sales calls")
        desc_lbl.setObjectName("Timestamp")
        
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(desc_lbl)
        title_vbox.addStretch()
        
        header_layout.addLayout(title_vbox)
        header_layout.addStretch()
        
        # Mac-like dots decoration
        dots_layout = QHBoxLayout()
        dots_layout.setSpacing(6)
        for color in ["#3f3f46", "#3f3f46", "#71717a"]: # Reference image has dark grey dots with one slightly lighter
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 14px;")
            dots_layout.addWidget(dot)
            
        header_layout.addLayout(dots_layout)
        
        self.main_layout.addWidget(header)
        
        # Lists Split (Main content)
        content_split = QHBoxLayout()
        content_split.setContentsMargins(15, 15, 15, 15)
        content_split.setSpacing(15)
        
        # Left: Knowledge Base
        kb_pane = QVBoxLayout()
        kb_header = QHBoxLayout()
        kb_title = QLabel("KNOWLEDGE BASE")
        kb_title.setObjectName("SectionHeader")
        kb_icon = QLabel("ℹ️")
        kb_icon.setStyleSheet("color: #64748b; font-size: 12px;")
        kb_header.addWidget(kb_title)
        kb_header.addStretch()
        kb_header.addWidget(kb_icon)
        kb_pane.addLayout(kb_header)
        
        self.kb_scroll = QScrollArea()
        self.kb_scroll.setWidgetResizable(True)
        self.kb_container = QWidget()
        self.kb_layout = QVBoxLayout(self.kb_container)
        self.kb_layout.setContentsMargins(0, 0, 5, 0)
        self.kb_layout.setSpacing(8)
        self.kb_layout.addStretch()
        self.kb_scroll.setWidget(self.kb_container)
        kb_pane.addWidget(self.kb_scroll)
        
        # Right: Recent Meetings
        history_pane = QVBoxLayout()
        history_header = QHBoxLayout()
        history_title = QLabel("RECENT MEETINGS")
        history_title.setObjectName("SectionHeader")
        hist_icon = QLabel("🕘")
        hist_icon.setStyleSheet("color: #64748b; font-size: 12px;")
        history_header.addWidget(history_title)
        history_header.addStretch()
        history_header.addWidget(hist_icon)
        history_pane.addLayout(history_header)
        
        self.history_scroll = QScrollArea()
        self.history_scroll.setWidgetResizable(True)
        self.history_container = QWidget()
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setContentsMargins(0, 0, 5, 0)
        self.history_layout.setSpacing(8)
        self.history_layout.addStretch()
        self.history_scroll.setWidget(self.history_container)
        history_pane.addWidget(self.history_scroll)
        
        content_split.addLayout(kb_pane, 1)
        content_split.addLayout(history_pane, 1)
        
        self.main_layout.addLayout(content_split, 1)
        
        # Footer Action Bar
        footer = QWidget()
        footer.setFixedHeight(80)
        footer.setStyleSheet("background-color: transparent; border-top: 1px solid #2c2d31;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 15, 24, 15)
        
        left_btns = QHBoxLayout()
        left_btns.setSpacing(10)
        self.upload_btn = QPushButton("↑ Upload Document")
        self.upload_btn.setObjectName("SecondaryButton")
        self.upload_btn.clicked.connect(self.upload_document)
        left_btns.addWidget(self.upload_btn)
        
        self.delete_btn = QPushButton("🗑 Delete Selected")
        self.delete_btn.setObjectName("EndButton")
        self.delete_btn.setVisible(False)
        self.delete_btn.clicked.connect(self.delete_selected)
        left_btns.addWidget(self.delete_btn)
        
        footer_layout.addLayout(left_btns)
        footer_layout.addStretch()
        
        right_actions = QVBoxLayout()
        self.start_btn = QPushButton("Start Session →")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.setFixedHeight(40)
        self.start_btn.clicked.connect(self.start_session)
        
        self.stealth_checkbox = QCheckBox("Start in background")
        self.stealth_checkbox.setObjectName("Timestamp")
        self.stealth_checkbox.setStyleSheet("color: #8b919e; font-size: 11px;")
        
        right_actions.addWidget(self.start_btn)
        right_actions.addWidget(self.stealth_checkbox, alignment=Qt.AlignmentFlag.AlignRight)
        
        footer_layout.addLayout(right_actions)
        self.main_layout.addWidget(footer)
        
        self.setStyleSheet(get_stylesheet())
        
        self.selected_docs = []
        self.selected_item_widget = None
        
        self.refresh_document_list()
        self.refresh_transcript_list()
        self.center_on_screen()

    def refresh_document_list(self):
        # Clear kb_layout (except stretch)
        for i in reversed(range(self.kb_layout.count() - 1)):
            self.kb_layout.itemAt(i).widget().setParent(None)
            
        if self.store:
            docs = self.store.list_documents()
            for doc in docs:
                item = DashboardItem("description", doc, "Knowledge Base", data=doc)
                item.clicked.connect(self.toggle_document_selection)
                self.kb_layout.insertWidget(self.kb_layout.count() - 1, item)
        else:
            self.kb_layout.insertWidget(0, QLabel("Database connection error."))

    def refresh_transcript_list(self):
        for i in reversed(range(self.history_layout.count() - 1)):
            self.history_layout.itemAt(i).widget().setParent(None)
            
        app_data = Path.home() / "AppData" / "Local" / "AI_Meetings_Assistant"
        transcripts_dir = str(app_data / "transcripts")
        if not os.path.exists(transcripts_dir):
            os.makedirs(transcripts_dir, exist_ok=True)
            
        files = [f for f in os.listdir(transcripts_dir) if f.endswith(".txt")]
        files.sort(reverse=True)
        
        for f in files:
            mtime = os.path.getmtime(os.path.join(transcripts_dir, f))
            date_str = datetime.fromtimestamp(mtime).strftime("%b %d, %H:%M")
            item = DashboardItem("calendar_today", f, date_str, color="#ffb867", data=f)
            item.clicked.connect(self.view_logged_transcript)
            self.history_layout.insertWidget(self.history_layout.count() - 1, item)

    def toggle_document_selection(self, filename):
        if filename in self.selected_docs:
            self.selected_docs.remove(filename)
        else:
            self.selected_docs.append(filename)
            
        # Update visual state
        for i in range(self.kb_layout.count() - 1):
            widget = self.kb_layout.itemAt(i).widget()
            if widget and hasattr(widget, 'data'):
                if widget.data == filename:
                    if filename in self.selected_docs:
                        widget.setStyleSheet("background-color: #1e1f24; border: 1px solid #3b82f6;")
                    else:
                        widget.setStyleSheet("")
        
        self.delete_btn.setVisible(len(self.selected_docs) > 0)

    def view_logged_transcript(self, filename):
        app_data = Path.home() / "AppData" / "Local" / "AI_Meetings_Assistant"
        file_path = str(app_data / "transcripts" / filename)
        try:
            # We should use TranscriptWindow instead of just showing text
            # But we need the structured history. For legacy .txt files, we'll mock it.
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Simple parsing for legacy txt
            history = []
            current_speaker = "Unknown"
            current_text = []
            for line in content.split("\n"):
                line = line.strip()
                if not line or line.startswith("===") or line.startswith("Meeting Transcript"):
                    continue
                if line.endswith(":"):
                    if current_text:
                        history.append({"speaker": current_speaker, "text": " ".join(current_text), "timestamp": ""})
                    current_speaker = line[:-1]
                    current_text = []
                else:
                    current_text.append(line)
            if current_text:
                history.append({"speaker": current_speaker, "text": " ".join(current_text), "timestamp": ""})
            
            from .transcript_window import TranscriptWindow
            self.transcript_win = TranscriptWindow(history)
            self.transcript_win.show()
        except Exception as e:
            print(f"Error reading transcript: {e}")

    def upload_document(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Document", "", "Documents (*.pdf *.txt)")
        if file_path:
            self.upload_btn.setEnabled(False)
            self.start_btn.setEnabled(False)
            self.index_thread = RAGIndexThread(file_path)
            self.index_thread.finished.connect(self.on_index_finished)
            self.index_thread.error.connect(self.on_index_error)
            self.index_thread.start()

    def on_index_finished(self, assistant):
        self.upload_btn.setEnabled(True)
        self.start_btn.setEnabled(True)
        self.refresh_document_list()

    def on_index_error(self, err_msg):
        self.upload_btn.setEnabled(True)
        self.start_btn.setEnabled(True)
        print(f"Indexing error: {err_msg}")

    def delete_selected(self):
        if not self.selected_docs: return
        for doc in self.selected_docs:
            try:
                self.store.delete_document(doc)
            except Exception as e:
                print(f"Delete error: {e}")
        self.selected_docs = []
        self.delete_btn.hide()
        self.refresh_document_list()

    def start_session(self):
        logging.info("Attempting to start session...")
        if not self.store:
            logging.error("Store not initialized.")
            QMessageBox.critical(self, "Error", "Database not connected. Please restart the app.")
            return

        try:
            from core.rag_engine import SalesAssistant
            logging.info(f"Creating SalesAssistant with docs: {self.selected_docs}")
            rag_assistant = SalesAssistant(self.store, selected_docs=self.selected_docs)
            
            is_stealth = self.stealth_checkbox.isChecked()
            logging.info(f"Initializing AssistantWindow (Stealth: {is_stealth})")
            
            self.assistant_window = AssistantWindow(rag_assistant, is_stealth=is_stealth)
            self.assistant_window.session_ended.connect(self.on_session_ended)
            self.assistant_window.show()
            
            self.hide()
            logging.info("Session started successfully.")
        except Exception as e:
            logging.error(f"Failed to start session: {e}", exc_info=True)
            QMessageBox.critical(self, "Session Error", f"Failed to start meeting assistant:\n{str(e)}")

    def on_session_ended(self, transcript_data=None):
        self.show()
        self.refresh_transcript_list()

    def center_on_screen(self):
        screen = self.screen().availableGeometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)
        
    def closeEvent(self, event):
        from core.vector_store import close_vector_store
        close_vector_store()
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()
