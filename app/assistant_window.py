from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QLabel, QVBoxLayout, QScrollArea
from PyQt6.QtCore import Qt, QPoint, QRect
from .styles import get_stylesheet
from core.audio_engine import DualAudioCaptureThread
from core.transcription_engine import TranscriptionEngine
from core.meeting_logger import MeetingLogger

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
        self.layout.addWidget(self.label)
        
        # New rolling-window transcript label wrapped in a scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("TranscriptionScrollArea")
        self.scroll_area.setMinimumSize(350, 150)
        
        self.transcript_label = QLabel("")
        self.transcript_label.setWordWrap(True)
        self.transcript_label.setObjectName("TranscriptionLabel")
        self.transcript_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.scroll_area.setWidget(self.transcript_label)
        self.layout.addWidget(self.scroll_area)
        
        # State machine for chronological blocks
        self.blocks = []
        
        self.setStyleSheet(get_stylesheet())

    def update_audio_visual(self, rep_rms, client_rms):
        MAX_RMS_SCALE = 10000
        
        rep_lvl = int((rep_rms / MAX_RMS_SCALE) * 10)
        rep_lvl = min(max(rep_lvl, 0), 10)
        rep_bar = "█" * rep_lvl + "-" * (10 - rep_lvl)
        
        cli_lvl = int((client_rms / MAX_RMS_SCALE) * 10)
        cli_lvl = min(max(cli_lvl, 0), 10)
        cli_bar = "█" * cli_lvl + "-" * (10 - cli_lvl)
        
        self.label.setText(f"Mic: |{rep_bar}|  Sys: |{cli_bar}|")

    def update_transcript_visual(self, speaker, text, is_final):
        # Find the last active block for this speaker
        active_block = next((b for b in reversed(self.blocks) if b["speaker"] == speaker and b.get("is_active", False)), None)
        
        if not active_block:
            active_block = {"speaker": speaker, "final": [], "interim": "", "is_active": True}
            self.blocks.append(active_block)
            
        if is_final:
            active_block["final"].append(text.strip())
            active_block["interim"] = ""
            
            # Since this speaker finished a statement, we can close the OTHER speakers' active blocks IF they have some final text.
            for b in self.blocks:
                if b["speaker"] != speaker and b["is_active"] and len(b["final"]) > 0:
                    b["is_active"] = False
        else:
            active_block["interim"] = text.strip()
            
        # Clean up old blocks (keep last 5 to avoid filling the screen too much)
        if len(self.blocks) > 5:
            self.blocks = self.blocks[-5:]
            
        # Render
        display_lines = []
        for b in self.blocks:
            combined = " ".join(b["final"])
            if b["interim"]:
                combined += (" " if combined else "") + b["interim"]
                
            if combined.strip():
                color = "#4db8ff" if b["speaker"] == "You" else "#69db7c"
                display_lines.append(f'<span style="color: {color}"><b>{b["speaker"]}:</b></span> {combined.strip()}')
                
        self.transcript_label.setText("<br><br>".join(display_lines))
        
        # Auto-scroll to bottom
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(10, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

class ResizeHandle(QLabel):
    def __init__(self, target_window):
        super().__init__("↘")
        self.target_window = target_window
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setObjectName("ResizeHandle")
        self._dragging = False
        self._start_global_pos = None
        self._start_size = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._start_global_pos = event.globalPosition()
            self._start_size = self.target_window.display_window.scroll_area.size()

    def mouseMoveEvent(self, event):
        if self._dragging:
            current_global_pos = event.globalPosition()
            delta = current_global_pos - self._start_global_pos
            
            new_w = max(250, self._start_size.width() + int(delta.x()))
            new_h = max(100, self._start_size.height() + int(delta.y()))
            
            self.target_window.display_window.scroll_area.setFixedSize(new_w, new_h)
            self.target_window.display_window.adjustSize()
            self.target_window.update_display_position()

    def mouseReleaseEvent(self, event):
        self._dragging = False

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
        
        # Local Hard Drive Session Logger
        self.meeting_logger = MeetingLogger()
        
        # Deepgram Transcription Thread
        self.transcription_thread = TranscriptionEngine()
        
        # Crucial link: Pipe raw audio bytes directly into transcription socket
        self.audio_thread.audio_data.connect(self.transcription_thread.feed_audio)
        self.transcription_thread.new_transcript.connect(self.handle_new_transcript)
        
        self.transcription_thread.start()
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
        
        # The resize handle
        self.resize_handle = ResizeHandle(self)
        
        self.handle_layout.addWidget(self.close_btn)
        self.handle_layout.addWidget(self.handle)
        self.handle_layout.addWidget(self.resize_handle)
        
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

    def handle_new_transcript(self, speaker, text, is_final):
        # Pass visual render payload directly to HUD
        self.display_window.update_transcript_visual(speaker, text, is_final)
        
        # Log to JSONL when sentence is finalized by endpointing
        if is_final:
            self.meeting_logger.log_utterance(speaker, text)

    def closeEvent(self, event):
        if hasattr(self, 'audio_thread'):
            self.audio_thread.stop()
        if hasattr(self, 'transcription_thread'):
            self.transcription_thread.stop()
        if hasattr(self, 'meeting_logger'):
            self.meeting_logger.flush()
        self.display_window.close()
        super().closeEvent(event)

