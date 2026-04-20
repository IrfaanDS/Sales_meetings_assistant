import os
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QTextEdit
from PyQt6.QtCore import Qt
from qfluentwidgets import (
    setTheme, Theme, PrimaryPushButton, PushButton, 
    SubtitleLabel, BodyLabel, ListWidget, InfoBar, InfoBarPosition, ProgressBar
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
        
        # Dashboard: Stored Documents
        self.doc_header = BodyLabel("Knowledge Base Documents:", self)
        self.layout.addWidget(self.doc_header)
        
        self.doc_list = ListWidget(self)
        self.doc_list.itemClicked.connect(self.toggle_selection)
        self.layout.addWidget(self.doc_list)

        # Action Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        self.upload_btn = PushButton("Upload New Document", self)
        self.upload_btn.clicked.connect(self.upload_document)
        
        self.delete_btn = PushButton("Delete Selected", self)
        self.delete_btn.setObjectName("DeleteBtn")
        self.delete_btn.setStyleSheet("QPushButton#DeleteBtn { color: #f44336; }")
        self.delete_btn.clicked.connect(self.delete_selected_document)
        self.delete_btn.hide() # Only show when something is selected
        
        self.start_btn = PrimaryPushButton("Start Session", self)
        self.start_btn.clicked.connect(self.start_session)
        
        button_layout.addWidget(self.upload_btn)
        button_layout.addWidget(self.delete_btn)
        button_layout.addWidget(self.start_btn)
        self.layout.addLayout(button_layout)
        
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

        self.export_btn = PushButton("Export Clean Transcript", self)
        self.export_btn.clicked.connect(self.export_transcript)
        self.export_btn.hide()
        self.layout.addWidget(self.export_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.assistant_window = None
        self.index_thread = None
        
        self.refresh_document_list()
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

    def toggle_selection(self, item):
        # If the item was already selected, deselect it
        if hasattr(self, "_last_selected_item") and self._last_selected_item == item:
            item.setSelected(False)
            self._last_selected_item = None
            self.delete_btn.hide()
        else:
            self._last_selected_item = item
            if "📄" in item.text(): # Only show delete for real docs
                self.delete_btn.show()
            else:
                self.delete_btn.hide()

    def delete_selected_document(self):
        item = self.doc_list.currentItem()
        if not item or "📄" not in item.text():
            return
        
        filename = item.text().replace("📄 ", "").strip()
        
        # Confirmation skipped for speed as per "agentic focus", 
        # but the user requested the button specifically.
        try:
            self.store.delete_document(filename)
            self.refresh_document_list()
            InfoBar.success("Deleted", f"Removed {filename} from knowledge base.", duration=3000, parent=self)
        except Exception as e:
            InfoBar.error("Error", f"Failed to delete: {e}", duration=4000, parent=self)

    def center_on_screen(self):
        screen = self.screen().availableGeometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)

    def upload_document(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Project Document", "", "Documents (*.pdf *.txt)"
        )
        if file_path:
            self.start_btn.setDisabled(True)
            self.upload_btn.setDisabled(True)
            self.progress_bar.show()
            
            # Start indexing thread
            self.index_thread = RAGIndexThread(file_path)
            self.index_thread.finished.connect(self.on_index_finished)
            self.index_thread.error.connect(self.on_index_error)
            self.index_thread.start()

    def on_index_finished(self, assistant):
        self.progress_bar.hide()
        self.start_btn.setDisabled(False)
        self.upload_btn.setDisabled(False)
        self.refresh_document_list()
        InfoBar.success("Success", "Document indexed successfully into Qdrant.", duration=3000, parent=self)

    def on_index_error(self, err_msg):
        self.progress_bar.hide()
        self.start_btn.setDisabled(False)
        self.upload_btn.setDisabled(False)
        InfoBar.error("Error", f"Failed to index: {err_msg[:40]}...", duration=4000, parent=self)

    def start_session(self):
        if not self.store:
            InfoBar.error("Error", "Database not connected. Cannot start RAG.", duration=3000, parent=self)
            return
            
        # Get the assistant ready matching the Qdrant backend
        # Since we decoupled, we just need a SalesAssistant with store
        from core.rag_engine import SalesAssistant
        rag_assistant = SalesAssistant(self.store)

        self.assistant_window = AssistantWindow(rag_assistant)
        self.assistant_window.session_ended.connect(self.on_session_ended)
        self.assistant_window.show()
        
        self.hide()

    def on_session_ended(self, clean_transcript):
        # Update UI to Summary View
        self.doc_list.hide()
        self.doc_header.hide()
        self.upload_btn.hide()
        self.start_btn.hide()
        self.progress_bar.hide()
        
        self.title.setText("Session Ended")
        self.desc.setText("Here is the clean transcript of your meeting:")
        
        self.summary_text.setPlainText(clean_transcript)
        self.summary_text.show()
        self.export_btn.show()
        
        self.resize(650, 550)
        self.center_on_screen()
        self.show()

    def export_transcript(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Clean Transcript", "transcript.txt", "Text Files (*.txt)"
        )
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.summary_text.toPlainText())
            self.desc.setText(f"Saved to: {file_path}")
            InfoBar.success("Exported", f"Successfully saved to {os.path.basename(file_path)}", duration=3000, parent=self)
            self.export_btn.setDisabled(True)

    def closeEvent(self, event):
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()
