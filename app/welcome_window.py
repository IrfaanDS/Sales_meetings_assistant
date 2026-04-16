from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog
from PyQt6.QtCore import Qt
from app.assistant_window import AssistantWindow
from core.rag_engine import RAGIndexThread

class WelcomeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Meetings Assistant")
        self.resize(450, 320)
        
        # UI Setup
        self.central_widget = QWidget()
        self.central_widget.setStyleSheet("background-color: #1E1E1E; color: white;")
        self.setCentralWidget(self.central_widget)
        
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.setSpacing(15)
        
        # Title
        self.title = QLabel("AI Sales Meeting Assistant")
        self.title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 5px;")
        
        # Description
        self.desc = QLabel("Your unobtrusive AI companion for sales calls.")
        self.desc.setStyleSheet("font-size: 14px; color: #A0A0A0;")
        
        # Document Upload Section
        self.doc_label = QLabel("No document selected (Optional)")
        self.doc_label.setStyleSheet("font-size: 12px; color: #808080; font-style: italic;")
        
        self.browse_btn = QPushButton("Browse Project Document (.pdf, .txt)")
        self.browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_btn.setFixedSize(250, 35)
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #444444; }
        """)
        self.browse_btn.clicked.connect(self.browse_file)
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 13px; color: #FFA500;")
        
        # Start Button
        self.start_btn = QPushButton("Start Session")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setFixedSize(160, 45)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D4;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #106EBE; }
            QPushButton:pressed { background-color: #005A9E; }
            QPushButton:disabled { background-color: #555555; color: #999999; }
        """)
        self.start_btn.clicked.connect(self.start_session)
        
        # Add widgets to layout
        self.layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.desc, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addSpacing(10)
        self.layout.addWidget(self.browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.doc_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addSpacing(10)
        self.layout.addWidget(self.start_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Keep references
        self.assistant_window = None
        self.rag_assistant = None
        self.index_thread = None
        self.selected_file = None
        
        self.center_on_screen()

    def center_on_screen(self):
        screen = self.screen().availableGeometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Project Document", "", "Documents (*.pdf *.txt)"
        )
        if file_path:
            self.selected_file = file_path
            import os
            self.doc_label.setText(f"Selected: {os.path.basename(file_path)}")
            # Start embedding
            self.start_btn.setDisabled(True)
            self.browse_btn.setDisabled(True)
            self.status_label.setText("Building index, please wait...")
            
            self.index_thread = RAGIndexThread(self.selected_file)
            self.index_thread.finished.connect(self.on_index_finished)
            self.index_thread.error.connect(self.on_index_error)
            self.index_thread.start()

    def on_index_finished(self, assistant):
        self.rag_assistant = assistant
        self.status_label.setText("✅ Ready!")
        self.start_btn.setDisabled(False)
        self.browse_btn.setDisabled(False)

    def on_index_error(self, err_msg):
        self.status_label.setText(f"❌ Error: {err_msg[:30]}...")
        self.start_btn.setDisabled(False)
        self.browse_btn.setDisabled(False)
        self.selected_file = None
        self.doc_label.setText("No document selected (Optional)")

    def start_session(self):
        # Instantiate and show the transparent HUD
        self.assistant_window = AssistantWindow(self.rag_assistant)
        self.assistant_window.show()
        
        # Hide the welcome window instead of closing it
        self.hide()

    def closeEvent(self, event):
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()
