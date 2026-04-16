from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QPoint, QRect
from .styles import get_stylesheet
from core.audio_engine import DualAudioCaptureThread

class AssistantDisplay(QMainWindow):
    """ The truly unclickable, transparent window displaying the text """
    def __init__(self):
        super().__init__()
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 5, 5, 5)
        
        self.label = QLabel("Meeting Assistant: Listening...")
        self.label.setObjectName("TranscriptionLabel")
        self.layout.addWidget(self.label)
        
        self.setStyleSheet(get_stylesheet())

    def update_audio_visual(self, rep_rms, client_rms):
        MAX_RMS_SCALE = 10000
        
        rep_lvl = int((rep_rms / MAX_RMS_SCALE) * 10)
        rep_lvl = min(max(rep_lvl, 0), 10)
        rep_bar = "█" * rep_lvl + "-" * (10 - rep_lvl)
        
        cli_lvl = int((client_rms / MAX_RMS_SCALE) * 10)
        cli_lvl = min(max(cli_lvl, 0), 10)
        cli_bar = "█" * cli_lvl + "-" * (10 - cli_lvl)
        
        self.label.setText(f"Mic (You): |{rep_bar}|  Sys (Client): |{cli_bar}|")

class AssistantWindow(QMainWindow):
    """ The interactive handle window """
    def __init__(self):
        super().__init__()
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Display Window
        self.display_window = AssistantDisplay()
        
        # Audio Listener (Dual Capture Strategy)
        self.audio_thread = DualAudioCaptureThread()
        self.audio_thread.audio_levels.connect(self.display_window.update_audio_visual)
        self.audio_thread.start()
        
        # UI
        self.central_widget = QWidget()
        self.central_widget.setObjectName("MainWidget")
        self.setCentralWidget(self.central_widget)
        
        self.layout = QHBoxLayout(self.central_widget)
        self.layout.setContentsMargins(5, 5, 0, 5)
        
        self.handle_container = QWidget()
        self.handle_layout = QVBoxLayout(self.handle_container)
        self.handle_layout.setContentsMargins(0, 0, 0, 0)
        self.handle_layout.setSpacing(5)
        
        from PyQt6.QtWidgets import QPushButton
        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("CloseButton")
        self.close_btn.setFixedSize(16, 16)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close_app)
        
        # The drag handle
        from PyQt6.QtWidgets import QLabel
        self.handle = QLabel("⋮")
        self.handle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.handle.setObjectName("Handle")
        
        self.handle_layout.addWidget(self.close_btn)
        self.handle_layout.addWidget(self.handle)
        
        self.layout.addWidget(self.handle_container)
        
        self.setStyleSheet(get_stylesheet())
        
        self.resize(36, 100)
        self.move(100, 100)
        
        self._old_pos = None

    def close_app(self):
        self.close()
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        # Fallback manual drag if nativeEvent doesn't trigger
        if self._old_pos is not None:
            delta = event.globalPosition().toPoint() - self._old_pos
            self.move(self.pos() + delta)
            self._old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self._old_pos = None

    def update_display_position(self):
        # Position the display window right next to the handle
        handle_pos = self.pos()
        self.display_window.move(handle_pos.x() + self.width(), handle_pos.y())
        
    def moveEvent(self, event):
        # Automatically keeps the text glued to the handle whenever it moves
        super().moveEvent(event)
        self.update_display_position()
        
    def showEvent(self, event):
        super().showEvent(event)
        self.display_window.show()
        self.update_display_position()

    def closeEvent(self, event):
        if hasattr(self, 'audio_thread'):
            self.audio_thread.stop()
        self.display_window.close()
        super().closeEvent(event)

