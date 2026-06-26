import os
import logging
import webbrowser
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from app.api import set_summary_data

class SummaryWindow(QMainWindow):
    closed = pyqtSignal()

    def __init__(self, summary_data, engine, parent=None):
        super().__init__(parent)
        self.summary_data = summary_data
        self.engine = engine
        
        # Inject data to the FastAPI backend so React can fetch it
        set_summary_data(summary_data)
        
        self.setWindowTitle("Meeting Summary")
        self.setMinimumSize(600, 500)
        self.resize(1000, 800)
        self.setWindowFlags(Qt.WindowType.Window)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # WebEngine View
        self.browser = QWebEngineView()
        # Use localhost in dev, or file:// in production if building static HTML
        # In this hybrid setup, FastAPI will serve the static React files on port 8765
        self.browser.setUrl(QUrl("http://127.0.0.1:8765/"))
        
        self.main_layout.addWidget(self.browser)

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()

