from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from app.assistant_window import AssistantWindow

class WelcomeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Meetings Assistant")
        self.resize(400, 250)
        
        # UI Setup
        self.central_widget = QWidget()
        self.central_widget.setStyleSheet("background-color: #1E1E1E; color: white;")
        self.setCentralWidget(self.central_widget)
        
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Title
        self.title = QLabel("AI Sales Meeting Assistant")
        self.title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 10px;")
        
        # Description
        self.desc = QLabel("Your unobtrusive AI companion for sales calls.")
        self.desc.setStyleSheet("font-size: 14px; color: #A0A0A0; margin-bottom: 30px;")
        
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
            QPushButton:hover {
                background-color: #106EBE;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
        """)
        self.start_btn.clicked.connect(self.start_session)
        
        # Add widgets to layout
        self.layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.desc, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.start_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Keep a reference to the assistant window so it's not garbage collected
        self.assistant_window = None
        
        self.center_on_screen()

    def center_on_screen(self):
        # Center the window on the active screen
        screen = self.screen().availableGeometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)

    def start_session(self):
        # Instantiate and show the transparent HUD
        self.assistant_window = AssistantWindow()
        self.assistant_window.show()
        
        # Hide the welcome window instead of closing it
        self.hide()

    def closeEvent(self, event):
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()
