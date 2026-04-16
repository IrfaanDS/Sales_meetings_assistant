from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QLabel, QVBoxLayout, QScrollArea, QLineEdit, QPushButton
from PyQt6.QtCore import Qt, QPoint, QRect, QTimer
from .styles import get_stylesheet
from core.audio_engine import DualAudioCaptureThread
from core.transcription_engine import TranscriptionEngine
from core.meeting_logger import MeetingLogger
from core.rag_engine import RAGQueryThread, SalesAssistant

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
        
        # Dual-column layout
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 5, 5, 5)
        self.main_layout.setSpacing(15)
        
        # --- LEFT PANE (Transcription) ---
        self.left_pane = QWidget()
        self.left_layout = QVBoxLayout(self.left_pane)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel("Meeting Assistant: Listening...")
        self.left_layout.addWidget(self.label)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("TranscriptionScrollArea")
        self.scroll_area.setMinimumSize(350, 150)
        
        self.transcript_label = QLabel("")
        self.transcript_label.setWordWrap(True)
        self.transcript_label.setObjectName("TranscriptionLabel")
        self.transcript_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.scroll_area.setWidget(self.transcript_label)
        self.left_layout.addWidget(self.scroll_area)
        
        # --- RIGHT PANE (LLM Script) ---
        self.right_pane = QWidget()
        self.right_layout = QVBoxLayout(self.right_pane)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.script_title_label = QLabel("LLM Script | RAG Assistant")
        self.script_title_label.setStyleSheet("color: #FFA500; font-weight: bold; font-size: 14px;")
        self.right_layout.addWidget(self.script_title_label)
        
        self.script_scroll = QScrollArea()
        self.script_scroll.setWidgetResizable(True)
        self.script_scroll.setObjectName("TranscriptionScrollArea") # Reuse the transparent styling
        self.script_scroll.setMinimumSize(350, 150)
        
        self.script_label = QLabel("Ask a question using the text box on the handle...")
        self.script_label.setWordWrap(True)
        self.script_label.setObjectName("TranscriptionLabel") # Reuse styling
        self.script_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.script_label.setStyleSheet("color: #E0E0E0;")
        
        self.script_scroll.setWidget(self.script_label)
        self.right_layout.addWidget(self.script_scroll)
        
        # Embed into main layout
        self.main_layout.addWidget(self.left_pane)
        self.main_layout.addWidget(self.right_pane)
        
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
            
            # Since this speaker finished a statement, close OTHER speakers' active blocks
            for b in self.blocks:
                if b["speaker"] != speaker and b["is_active"] and len(b["final"]) > 0:
                    b["is_active"] = False
        else:
            active_block["interim"] = text.strip()
            
        if len(self.blocks) > 5:
            self.blocks = self.blocks[-5:]
            
        display_lines = []
        for b in self.blocks:
            combined = " ".join(b["final"])
            if b["interim"]:
                combined += (" " if combined else "") + b["interim"]
                
            if combined.strip():
                color = "#4db8ff" if b["speaker"] == "You" else "#69db7c"
                display_lines.append(f'<span style="color: {color}"><b>{b["speaker"]}:</b></span> {combined.strip()}')
                
        self.transcript_label.setText("<br><br>".join(display_lines))
        
        QTimer.singleShot(10, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

    def append_user_query(self, query):
        current_text = self.script_label.text()
        if "Ask a question" in current_text:
            current_text = ""
        else:
            current_text += "<br><br>"
            
        # Format user query using HTML
        current_text += f'<span style="color: #4db8ff"><b>Q:</b> {query}</span><br><span style="color: #FFA500"><b>A:</b> </span>'
        self.script_label.setText(current_text)
        self._scroll_script_to_bottom()

    def append_script_chunk(self, chunk):
        current_text = self.script_label.text()
        # Escape minimal HTML if necessary, or just replace newlines
        html_chunk = chunk.replace('\\n', '<br>').replace('\n', '<br>')
        self.script_label.setText(current_text + html_chunk)
        self._scroll_script_to_bottom()

    def finalize_script_chunk(self):
        pass

    def _scroll_script_to_bottom(self):
        QTimer.singleShot(10, lambda: self.script_scroll.verticalScrollBar().setValue(
            self.script_scroll.verticalScrollBar().maximum()
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
            
            # Apply delta width to BOTH columns
            new_w = max(250, self._start_size.width() + int(delta.x() / 2))
            new_h = max(100, self._start_size.height() + int(delta.y()))
            
            self.target_window.display_window.scroll_area.setFixedSize(new_w, new_h)
            self.target_window.display_window.script_scroll.setFixedSize(new_w, new_h)
            self.target_window.display_window.adjustSize()
            self.target_window.update_display_position()

    def mouseReleaseEvent(self, event):
        self._dragging = False


class AssistantWindow(QMainWindow):
    """ The interactive handle window """
    def __init__(self, rag_assistant: SalesAssistant = None):
        super().__init__()
        self.rag_assistant = rag_assistant
        self.query_thread = None
        
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
        
        # self.audio_thread.audio_data.connect(self.transcription_thread.feed_audio)
        # self.transcription_thread.new_transcript.connect(self.handle_new_transcript)
        
        # self.transcription_thread.start()
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
        
        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("CloseButton")
        self.close_btn.setFixedSize(16, 16)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close_app)
        
        # Drag handle
        self.handle = QLabel("⋮")
        self.handle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.handle.setObjectName("Handle")
        
        # Input for RAG queries
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Ask AI...")
        self.query_input.setFixedWidth(120)
        self.query_input.setStyleSheet("background-color: rgba(20,20,20,200); color: white; border: 1px solid #444; border-radius: 4px; padding: 3px;")
        if not self.rag_assistant:
             self.query_input.setPlaceholderText("No doc uploaded.")
             self.query_input.setEnabled(False)
        self.query_input.returnPressed.connect(self.submit_query)
        
        # The resize handle
        self.resize_handle = ResizeHandle(self)
        
        self.handle_layout.addWidget(self.close_btn)
        self.handle_layout.addWidget(self.handle)
        self.handle_layout.addWidget(self.query_input)
        self.handle_layout.addWidget(self.resize_handle)
        
        self.layout.addWidget(self.handle_container)
        
        self.setStyleSheet(get_stylesheet())
        
        self.resize(140, 150)
        self.move(100, 100)
        
        self._old_pos = None

    def submit_query(self):
        query = self.query_input.text().strip()
        if not query or not self.rag_assistant:
            return
            
        self.query_input.clear()
        self.query_input.setEnabled(False)
        self.query_input.setPlaceholderText("Thinking...")
        self.display_window.append_user_query(query)
        
        self.query_thread = RAGQueryThread(self.rag_assistant, query)
        self.query_thread.chunk_received.connect(self.display_window.append_script_chunk)
        self.query_thread.completed.connect(self.on_query_completed)
        self.query_thread.start()

    def on_query_completed(self):
        self.query_input.setEnabled(True)
        self.query_input.setPlaceholderText("Ask AI...")
        self.query_input.setFocus()
        self.display_window.finalize_script_chunk()

    def close_app(self):
        self.close()
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._old_pos is not None:
            delta = event.globalPosition().toPoint() - self._old_pos
            self.move(self.pos() + delta)
            self._old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self._old_pos = None

    def update_display_position(self):
        handle_pos = self.pos()
        self.display_window.move(handle_pos.x() + self.width(), handle_pos.y())
        
    def moveEvent(self, event):
        super().moveEvent(event)
        self.update_display_position()
        
    def showEvent(self, event):
        super().showEvent(event)
        self.display_window.show()
        self.update_display_position()

    def handle_new_transcript(self, speaker, text, is_final):
        self.display_window.update_transcript_visual(speaker, text, is_final)
        if is_final:
            self.meeting_logger.log_utterance(speaker, text)

    def closeEvent(self, event):
        if hasattr(self, 'audio_thread'):
            self.audio_thread.stop()
        # if hasattr(self, 'transcription_thread'):
        #     self.transcription_thread.stop()
        if hasattr(self, 'meeting_logger'):
            self.meeting_logger.flush()
        self.display_window.close()
        super().closeEvent(event)
