import threading
from pynput import keyboard
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QLabel, QVBoxLayout, QScrollArea, QLineEdit, QPushButton, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QPoint, QRect, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QColor
from .styles import get_stylesheet
from core.audio_engine import DualAudioCaptureThread
from core.transcription_engine import TranscriptionEngine
from core.meeting_logger import MeetingLogger
from core.rag_engine import RAGQueryThread, SalesAssistant, IntentGatekeeper, IntentGatekeeperThread

class StatusIndicator(QWidget):
    """ A small, pulsing indicator for 'Detecting' or 'Thinking' states """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.color = "#0078D4"
        self._opacity = 0.5
        self._visible = False
        self.hide()
        
        # Pulse animation
        self.animation = QPropertyAnimation(self, b"opacity_val")
        self.animation.setDuration(1000)
        self.animation.setStartValue(0.2)
        self.animation.setEndValue(0.9)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.animation.setLoopCount(-1)

    @pyqtProperty(float)
    def opacity_val(self):
        return self._opacity

    @opacity_val.setter
    def opacity_val(self, value):
        self._opacity = value
        self.update()

    def set_state(self, state):
        if state in ["detecting", "thinking"]:
            self.color = "#4db8ff" if state == "detecting" else "#FFA500"
            self.show()
            self._visible = True
            if self.animation.state() != QPropertyAnimation.State.Running:
                self.animation.start()
        else:
            self.animation.stop()
            self.hide()
            self._visible = False

    def paintEvent(self, event):
        if not self._visible: return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self.color)
        color.setAlphaF(self._opacity)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(5, 5, 10, 10)


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
        
        # Header with status indicator
        self.header_layout = QHBoxLayout()
        self.script_title_label = QLabel("LLM Script | RAG Assistant")
        self.script_title_label.setStyleSheet("color: #FFA500; font-weight: bold; font-size: 14px;")
        
        self.status_indicator = StatusIndicator()
        self.header_layout.addWidget(self.script_title_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.status_indicator)
        
        self.right_layout.addLayout(self.header_layout)
        
        self.script_scroll = QScrollArea()
        self.script_scroll.setWidgetResizable(True)
        self.script_scroll.setObjectName("TranscriptionScrollArea")
        self.script_scroll.setMinimumSize(350, 150)
        
        self.script_label = QLabel("Waiting for client questions...")
        self.script_label.setWordWrap(True)
        self.script_label.setObjectName("TranscriptionLabel")
        self.script_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        # Opacity effect for the Ghost phase
        self.script_opacity_effect = QGraphicsOpacityEffect()
        self.script_label.setGraphicsEffect(self.script_opacity_effect)
        self.script_opacity_effect.setOpacity(1.0)
        
        self.script_anim = QPropertyAnimation(self.script_opacity_effect, b"opacity")
        self.script_anim.setDuration(500)
        self.script_anim.setStartValue(0.4)
        self.script_anim.setEndValue(1.0)
        
        self.script_scroll.setWidget(self.script_label)
        self.right_layout.addWidget(self.script_scroll)
        
        # Embed into main layout
        self.main_layout.addWidget(self.left_pane)
        self.main_layout.addWidget(self.right_pane)
        
        self.blocks = []
        self.last_rag_answer = ""
        
        self.setStyleSheet(get_stylesheet())

    def set_status(self, state):
        self.status_indicator.set_state(state)

    def update_audio_visual(self, rep_rms, client_rms):
        MAX_RMS_SCALE = 10000
        rep_lvl = min(max(int((rep_rms / MAX_RMS_SCALE) * 10), 0), 10)
        rep_bar = "█" * rep_lvl + "-" * (10 - rep_lvl)
        cli_lvl = min(max(int((client_rms / MAX_RMS_SCALE) * 10), 0), 10)
        cli_bar = "█" * cli_lvl + "-" * (10 - cli_lvl)
        self.label.setText(f"Mic: |{rep_bar}|  Sys: |{cli_bar}|")

    def update_transcript_visual(self, speaker, text, is_final):
        active_block = next((b for b in reversed(self.blocks) if b["speaker"] == speaker and b.get("is_active", False)), None)
        if not active_block:
            active_block = {"speaker": speaker, "final": [], "interim": "", "is_active": True}
            self.blocks.append(active_block)
            
        if is_final:
            active_block["final"].append(text.strip())
            active_block["interim"] = ""
            for b in self.blocks:
                if b["speaker"] != speaker and b["is_active"] and len(b["final"]) > 0:
                    b["is_active"] = False
        else:
            active_block["interim"] = text.strip()
            
        if len(self.blocks) > 5: self.blocks = self.blocks[-5:]
            
        display_lines = []
        for b in self.blocks:
            combined = (" ".join(b["final"]) + " " + b["interim"]).strip()
            if combined:
                color = "#4db8ff" if b["speaker"] == "You" else "#69db7c"
                display_lines.append(f'<span style="color: {color}"><b>{b["speaker"]}:</b></span> {combined}')
                
        self.transcript_label.setText("<br><br>".join(display_lines))
        self._scroll_to_bottom(self.scroll_area)

    def prepare_script_view(self, query=None, is_manual=False):
        self.last_rag_answer = ""
        prefix = "[Refine] " if is_manual else ""
        if query:
            header = f'<span style="color: #4db8ff"><b>{prefix}Q:</b> {query}</span><br><span style="color: #FFA500"><b>A:</b> </span>'
        else:
            header = f'<span style="color: #FFA500"><b>Auto-Script:</b> </span>'
        self.script_label.setText(header)
        # Dim text while generating
        self.script_opacity_effect.setOpacity(0.4)
        self._scroll_to_bottom(self.script_scroll)

    def append_script_chunk(self, chunk):
        self.last_rag_answer += chunk
        current_text = self.script_label.text()
        html_chunk = chunk.replace('\\n', '<br>').replace('\n', '<br>')
        self.script_label.setText(current_text + html_chunk)
        self._scroll_to_bottom(self.script_scroll)

    def finalize_script_chunk(self):
        # Fade in to 100% when complete
        self.script_anim.start()

    def _scroll_to_bottom(self, scroll_area):
        QTimer.singleShot(10, lambda: scroll_area.verticalScrollBar().setValue(
            scroll_area.verticalScrollBar().maximum()
        ))


class ResizeHandle(QLabel):
    def __init__(self, target_window):
        super().__init__("↘")
        self.target_window = target_window
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setObjectName("ResizeHandle")
        self._dragging = False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._start_global_pos = event.globalPosition()
            self._start_size = self.target_window.display_window.scroll_area.size()

    def mouseMoveEvent(self, event):
        if self._dragging:
            delta = event.globalPosition() - self._start_global_pos
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
        self.gatekeeper = IntentGatekeeper()
        self.query_thread = None
        self.gatekeeper_thread = None
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.display_window = AssistantDisplay()
        self.audio_thread = DualAudioCaptureThread()
        self.audio_thread.audio_levels.connect(self.display_window.update_audio_visual)
        self.meeting_logger = MeetingLogger()
        self.transcription_thread = TranscriptionEngine()
        
        self.audio_thread.audio_data.connect(self.transcription_thread.feed_audio)
        self.transcription_thread.new_transcript.connect(self.handle_new_transcript)
        
        self.transcription_thread.start()
        self.audio_thread.start()
        
        # Global Hotkey for Manual Refinement
        self.hotkey_listener = keyboard.GlobalHotKeys({'<ctrl>+<space>': self.on_hotkey_triggered})
        self.hotkey_listener.start()
        
        # UI
        self.central_widget = QWidget(); self.central_widget.setObjectName("MainWidget")
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget); self.layout.setContentsMargins(5, 5, 0, 5)
        
        self.handle_container = QWidget()
        self.handle_layout = QVBoxLayout(self.handle_container); self.handle_layout.setContentsMargins(0, 0, 0, 0); self.handle_layout.setSpacing(5)
        
        self.close_btn = QPushButton("×"); self.close_btn.setObjectName("CloseButton"); self.close_btn.setFixedSize(16, 16)
        self.close_btn.clicked.connect(self.close_app)
        
        self.handle = QLabel("⋮"); self.handle.setAlignment(Qt.AlignmentFlag.AlignCenter); self.handle.setObjectName("Handle")
        
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Ask AI..."); self.query_input.setFixedWidth(120)
        self.query_input.setStyleSheet("background-color: rgba(20,20,20,200); color: white; border: 1px solid #444; border-radius: 4px; padding: 3px;")
        if not self.rag_assistant: self.query_input.setEnabled(False)
        self.query_input.returnPressed.connect(self.submit_query)
        
        self.resize_handle = ResizeHandle(self)
        self.handle_layout.addWidget(self.close_btn); self.handle_layout.addWidget(self.handle); self.handle_layout.addWidget(self.query_input); self.handle_layout.addWidget(self.resize_handle)
        self.layout.addWidget(self.handle_container)
        
        self.setStyleSheet(get_stylesheet())
        self.resize(140, 150); self.move(100, 100); self._old_pos = None

    def on_hotkey_triggered(self):
        """ Triggered by Ctrl+Space """
        # We need to run this on the main thread or use signals
        QTimer.singleShot(0, self.manual_refine)

    def manual_refine(self):
        if not self.rag_assistant: return
        # Grab last 5 final utterances
        client_utterances = [u["text"] for u in self.meeting_logger.get_history() if u["speaker"] == "Client"][-5:]
        if not client_utterances: return
        
        context = " ".join(client_utterances)
        
        # Intentionally cancel any running auto-query
        if self.query_thread and self.query_thread.isRunning():
            self.query_thread.cancel()
            self.query_thread.wait(100)
            
        self.run_rag_query(context, is_manual=True)

    def handle_new_transcript(self, speaker, text, is_final):
        self.display_window.update_transcript_visual(speaker, text, is_final)
        if is_final:
            self.meeting_logger.log_utterance(speaker, text)
            if speaker == "Client" and self.rag_assistant:
                # Debounce check: skip if gatekeeper or a query is running
                if self.gatekeeper_thread and self.gatekeeper_thread.isRunning(): return
                if self.query_thread and self.query_thread.isRunning(): return
                
                # Fire the Gatekeeper
                self.display_window.set_status("detecting")
                self.gatekeeper_thread = IntentGatekeeperThread(self.gatekeeper, text)
                self.gatekeeper_thread.intent_detected.connect(self.on_intent_detected)
                self.gatekeeper_thread.start()

    def on_intent_detected(self, is_high_intent, transcript):
        if is_high_intent:
            self.run_rag_query(transcript)
        else:
            self.display_window.set_status("idle")

    def submit_query(self):
        query = self.query_input.text().strip()
        if query and self.rag_assistant:
            self.query_input.clear(); self.query_input.setEnabled(False)
            self.run_rag_query(query, is_manual=True)

    def run_rag_query(self, query, is_manual=False):
        if self.query_thread and self.query_thread.isRunning(): return
        
        self.display_window.set_status("thinking")
        self.display_window.prepare_script_view(query if is_manual else None, is_manual)
        
        self.query_thread = RAGQueryThread(self.rag_assistant, query, is_manual=is_manual)
        self.query_thread.chunk_received.connect(self.display_window.append_script_chunk)
        self.query_thread.completed.connect(self.on_query_completed)
        self.query_thread.start()

    def on_query_completed(self):
        self.query_input.setEnabled(True)
        self.display_window.set_status("idle")
        self.display_window.finalize_script_chunk()
        self.meeting_logger.log_rag_interaction("Context Inquiry", self.display_window.last_rag_answer)

    def close_app(self):
        self.close()
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self._old_pos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event):
        if self._old_pos:
            delta = event.globalPosition().toPoint() - self._old_pos
            self.move(self.pos() + delta); self._old_pos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event): self._old_pos = None
    def update_display_position(self):
        self.display_window.move(self.pos().x() + self.width(), self.pos().y())
    def moveEvent(self, event): super().moveEvent(event); self.update_display_position()
    def showEvent(self, event): super().showEvent(event); self.display_window.show(); self.update_display_position()
    def closeEvent(self, event):
        self.audio_thread.stop()
        self.transcription_thread.stop()
        self.hotkey_listener.stop()
        self.meeting_logger.flush()
        self.display_window.close()
        super().closeEvent(event)
