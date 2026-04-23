import logging
import threading
import sys
import ctypes
from pynput import keyboard
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QLabel, QVBoxLayout, QScrollArea, QLineEdit, QPushButton, QGraphicsOpacityEffect, QMessageBox, QFrame, QApplication
from PyQt6.QtCore import Qt, QPoint, QRect, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QCursor
from .styles import get_stylesheet
from core.audio_engine import DualAudioCaptureThread
from core.transcription_engine import TranscriptionEngine
from core.meeting_logger import MeetingLogger
from core.rag_engine import RAGQueryThread, SalesAssistant, IntentGatekeeper, IntentGatekeeperThread
from core.summary_engine import MeetingSummaryEngine, SummaryThread
from .summary_window import SummaryWindow
from .transcript_window import TranscriptWindow
from .dialogs import EndSessionDialog, ProcessingDialog

def apply_stealth_affinity(window):
    if sys.platform == "win32":
        try:
            WDA_EXCLUDEFROMCAPTURE = 0x00000011
            hwnd = int(window.winId())
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        except Exception as e:
            logging.error(f"Failed to apply stealth display affinity: {e}")


class StatusIndicator(QWidget):
    """ A small, pulsing indicator for 'Live' state as per code1.html """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self.color = "#10b981" # Emerald
        self._opacity = 1.0
        self._visible = True
        
        # Pulse animation
        self.animation = QPropertyAnimation(self, b"opacity_val")
        self.animation.setDuration(1000)
        self.animation.setStartValue(0.4)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.animation.setLoopCount(-1)
        self.animation.start()

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
    def __init__(self, is_stealth=False):
        super().__init__()
        self.is_stealth = is_stealth
        self.setObjectName("AssistantDisplayWindow")
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Apply anti-screenshare display affinity
        apply_stealth_affinity(self)
        
        # Dual-column layout
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 5, 5, 5)
        self.main_layout.setSpacing(15)
        
        # --- LEFT PANE (Transcription) ---
        self.left_pane = QFrame()
        self.left_pane.setObjectName("FrostedPanel")
        self.left_pane.setProperty("class", "FrostedPanel")
        self.left_layout = QVBoxLayout(self.left_pane)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(0)
        
        # Audio Indicators (code1.html)
        self.audio_pane = QWidget()
        self.audio_pane.setFixedHeight(40)
        self.audio_pane.setStyleSheet("background-color: rgba(0, 0, 0, 0.2); border-bottom: 1px solid rgba(255, 255, 255, 0.05);")
        self.audio_layout = QHBoxLayout(self.audio_pane)
        self.audio_layout.setContentsMargins(15, 0, 15, 0)
        
        self.rep_tag = QLabel("YOU")
        self.rep_tag.setObjectName("SpeakerTag")
        self.rep_tag.setObjectName("SpeakerYou")
        
        self.rep_bars = QHBoxLayout()
        self.rep_bars.setSpacing(2)
        self.rep_bar_widgets = []
        for _ in range(5):
            b = QFrame()
            b.setFixedWidth(2)
            b.setFixedHeight(4)
            b.setStyleSheet("background-color: #a5c8ff; border-radius: 1px;")
            self.rep_bars.addWidget(b)
            self.rep_bar_widgets.append(b)
        
        self.audio_layout.addWidget(self.rep_tag)
        self.audio_layout.addLayout(self.rep_bars)
        self.audio_layout.addStretch()
        
        self.cli_bars = QHBoxLayout()
        self.cli_bars.setSpacing(2)
        self.cli_bar_widgets = []
        for _ in range(5):
            b = QFrame()
            b.setFixedWidth(2)
            b.setFixedHeight(4)
            b.setStyleSheet("background-color: #10b981; border-radius: 1px;")
            self.cli_bars.addWidget(b)
            self.cli_bar_widgets.append(b)
            
        self.cli_tag = QLabel("CLIENT")
        self.cli_tag.setObjectName("SpeakerTag")
        self.cli_tag.setObjectName("SpeakerClient")
        
        self.audio_layout.addLayout(self.cli_bars)
        self.audio_layout.addWidget(self.cli_tag)
        
        self.left_layout.addWidget(self.audio_pane)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumSize(350, 250)
        self.scroll_area.viewport().setStyleSheet("background: transparent;")
        
        self.transcript_label = QLabel("")
        self.transcript_label.setWordWrap(True)
        self.transcript_label.setObjectName("TranscriptionLabel")
        self.transcript_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.scroll_area.setWidget(self.transcript_label)
        self.left_layout.addWidget(self.scroll_area)
        
        # --- RIGHT PANE (LLM Insight) ---
        self.right_pane = QFrame()
        self.right_pane.setObjectName("FrostedPanel")
        self.right_pane.setProperty("class", "FrostedPanel")
        self.right_layout = QVBoxLayout(self.right_pane)
        self.right_layout.setContentsMargins(15, 15, 15, 15)
        
        # Header for AI Response
        self.header_layout = QHBoxLayout()
        ai_icon = QLabel("✨")
        ai_icon.setStyleSheet("color: #a5c8ff; font-size: 14px;")
        self.script_title_label = QLabel("AI INSIGHT")
        self.script_title_label.setObjectName("SectionHeader")
        self.script_title_label.setStyleSheet("color: #ffffff; font-size: 10px; font-weight: 800;")
        
        self.header_layout.addWidget(ai_icon)
        self.header_layout.addWidget(self.script_title_label)
        self.header_layout.addStretch()
        
        self.right_layout.addLayout(self.header_layout)
        
        self.script_scroll = QScrollArea()
        self.script_scroll.setWidgetResizable(True)
        self.script_scroll.setMinimumSize(350, 150)
        self.script_scroll.viewport().setStyleSheet("background: transparent;")
        
        self.script_label = QLabel("Waiting for client questions...")
        self.script_label.setWordWrap(True)
        self.script_label.setObjectName("TranscriptionLabel")
        self.script_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.script_scroll.setWidget(self.script_label)
        self.right_layout.addWidget(self.script_scroll)
        
        # Embed into main layout
        self.main_layout.addWidget(self.left_pane)
        self.main_layout.addWidget(self.right_pane)
        
        self.setStyleSheet(get_stylesheet())
        
        # If stealth mode, start transparent and fade in
        if is_stealth:
            self.setWindowOpacity(0.0)
        else:
            self.setWindowOpacity(0.9)
        
        self.show() # Show the window immediately
        
        # Status Indicator (re-added)
        self.status_indicator = StatusIndicator()
        self.header_layout.addWidget(self.status_indicator)
        
        # Opacity and Animations
        self.script_opacity_effect = QGraphicsOpacityEffect()
        self.script_label.setGraphicsEffect(self.script_opacity_effect)
        self.script_opacity_effect.setOpacity(1.0)
        
        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(500)
        
        self.script_anim = QPropertyAnimation(self.script_opacity_effect, b"opacity")
        self.script_anim.setDuration(500)
        self.script_anim.setStartValue(0.4)
        self.script_anim.setEndValue(1.0)
        
        self.blocks = []
        self.last_rag_answer = ""
        
        self.setStyleSheet(get_stylesheet())

    def fade_in(self):
        if not self.is_stealth: return
        self.fade_anim.stop()
        self.fade_anim.setStartValue(self.windowOpacity())
        self.fade_anim.setEndValue(0.9)
        self.fade_anim.start()

    def set_status(self, state):
        self.status_indicator.set_state(state)

    def update_audio_visual(self, rep_rms, client_rms):
        MAX_RMS_SCALE = 5000
        rep_lvl = min(max(int((rep_rms / MAX_RMS_SCALE) * 20), 4), 20)
        cli_lvl = min(max(int((client_rms / MAX_RMS_SCALE) * 20), 4), 20)
        
        # Update bar heights
        for i, b in enumerate(self.rep_bar_widgets):
            # Add some jitter/variation to look like a wave
            h = max(4, rep_lvl - (i * 2)) if i < 3 else max(4, rep_lvl - ((4-i) * 2))
            b.setFixedHeight(h)
            
        for i, b in enumerate(self.cli_bar_widgets):
            h = max(4, cli_lvl - (i * 2)) if i < 3 else max(4, cli_lvl - ((4-i) * 2))
            b.setFixedHeight(h)

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
                speaker_type = "YOU" if b["speaker"] == "You" else "CLIENT"
                tag_class = "SpeakerYou" if speaker_type == "YOU" else "SpeakerClient"
                
                tag_color = "#93c5fd" if speaker_type == "YOU" else "#10b981"
                tag_bg = "rgba(147, 197, 253, 0.1)" if speaker_type == "YOU" else "rgba(16, 185, 129, 0.1)"
                tag_icon = "𝄗"
                
                line = f"""
                <div style="margin-bottom: 16px;">
                    <div style="margin-bottom: 6px;">
                        <span style="font-family: 'Inter'; font-size: 10px; color: {tag_color}; font-weight: 700; padding: 3px 6px; border-radius: 4px; background-color: {tag_bg}; letter-spacing: 0.1em;">{speaker_type} {tag_icon}</span>
                    </div>
                    <p style="color: #e2e8f0; font-family: 'Inter'; font-size: 13px; line-height: 1.5; margin: 0;">{combined}</p>
                </div>
                """
                display_lines.append(line)
                
        self.transcript_label.setText("".join(display_lines))
        self._scroll_to_bottom(self.scroll_area)

    def prepare_script_view(self, query=None, is_manual=False):
        if self.is_stealth: self.fade_in()
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
            
            # Use the entire display window's size rather than just scroll area
            self._start_left_size = self.target_window.display_window.scroll_area.size()
            self._start_right_size = self.target_window.display_window.script_scroll.size()

    def mouseMoveEvent(self, event):
        if self._dragging:
            delta = event.globalPosition() - self._start_global_pos
            
            # Total delta divided amongst the visible panes
            visible_panes = 1
            if self.target_window.display_window.right_pane.isVisible():
                visible_panes = 2
                
            w_delta = int(delta.x() / visible_panes)
            h_delta = int(delta.y())

            new_left_w = max(250, self._start_left_size.width() + w_delta)
            new_h = max(100, self._start_left_size.height() + h_delta)
            self.target_window.display_window.scroll_area.setFixedSize(new_left_w, new_h)

            if visible_panes == 2:
                new_right_w = max(250, self._start_right_size.width() + w_delta)
                self.target_window.display_window.script_scroll.setFixedSize(new_right_w, new_h)

            self.target_window.display_window.adjustSize()
            
            # Sync the width of the control bar to match the display window width
            self.target_window.setFixedWidth(self.target_window.display_window.width())

    def mouseReleaseEvent(self, event):
        self._dragging = False


class AssistantWindow(QMainWindow):
    """ The interactive handle window """
    session_ended = pyqtSignal(str) # Emits the clean transcript

    def __init__(self, rag_assistant: SalesAssistant = None, is_stealth=False):
        super().__init__()
        self.rag_assistant = rag_assistant
        self.is_stealth = is_stealth
        self.gatekeeper = IntentGatekeeper()
        self.query_thread = None
        self.gatekeeper_thread = None
        self.summary_engine = MeetingSummaryEngine()
        self.summary_thread = None
        self.summary_window = None
        
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self._trigger_gatekeeper)
        self.pending_text = ""
        
        self.display_window = AssistantDisplay(is_stealth=is_stealth)
        self.display_window.show()
        if is_stealth:
            self.display_window.fade_in()
        self.audio_thread = DualAudioCaptureThread()
        self.audio_thread.audio_levels.connect(self.display_window.update_audio_visual)
        self.meeting_logger = MeetingLogger()
        self.transcription_thread = TranscriptionEngine()
        
        self.audio_thread.audio_data.connect(self.transcription_thread.feed_audio)
        self.transcription_thread.new_transcript.connect(self.handle_new_transcript)
        
        self.transcription_thread.start()
        self.audio_thread.start()

        # Safety flush timer — prevents data loss if the app crashes mid-speaker-block
        self.safety_flush_timer = QTimer(self)
        self.safety_flush_timer.timeout.connect(lambda: self.meeting_logger.flush_if_stale(30))
        self.safety_flush_timer.start(30000)  # Every 30 seconds

        # Global Hotkeys
        self.hotkey_listener = keyboard.GlobalHotKeys({
            '<ctrl>+<space>': self.on_hotkey_triggered,
            '<ctrl>+<shift>+h': self.on_toggle_visibility_triggered
        })
        self.hotkey_listener.start()
        
        # UI
        self.central_widget = QFrame()
        self.central_widget.setObjectName("AssistantMainWidget")
        self.setCentralWidget(self.central_widget)
        # Use horizontal layout representing a top bar
        self.layout = QHBoxLayout(self.central_widget)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        self.handle_container = QWidget()
        self.handle_container.setStyleSheet("background-color: #131417; border: 1px solid #2c2d31; border-radius: 12px;")
        
        self.handle_layout = QHBoxLayout(self.handle_container)
        self.handle_layout.setContentsMargins(12, 8, 12, 8)
        self.handle_layout.setSpacing(10)
        
        self.handle = QLabel("🟢 LIVE")
        self.handle.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 700; letter-spacing: 0.05em;")
        self.handle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.handle.setToolTip("Drag to move")
        self.handle.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        
        self.timer_label = QLabel("00:00")
        self.timer_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-family: 'JetBrains Mono', monospace;")
        
        self.drag_dots = QLabel("•••")
        self.drag_dots.setStyleSheet("color: #475569; font-size: 14px; font-weight: 800;")
        self.drag_dots.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drag_dots.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        
        self.toggle_llm_btn = QPushButton("Hide LLM")
        self.toggle_llm_btn.setObjectName("SecondaryButton")
        self.toggle_llm_btn.setFixedHeight(32)
        self.toggle_llm_btn.clicked.connect(self.toggle_llm_pane)
        
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Ask AI...")
        self.query_input.setFixedWidth(200)
        self.query_input.setStyleSheet("background-color: #09090b; color: #fafafa; border: 1px solid #27272a; border-radius: 6px; padding: 6px 10px;")
        if not self.rag_assistant: self.query_input.setEnabled(False)
        self.query_input.returnPressed.connect(self.submit_query)

        self.end_session_btn = QPushButton("End Session")
        self.end_session_btn.setObjectName("EndButton")
        self.end_session_btn.setToolTip("End Session")
        self.end_session_btn.clicked.connect(self.end_session)
        
        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("SecondaryButton")
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.clicked.connect(self.close_app)
        
        self.resize_handle = ResizeHandle(self)
        self.resize_handle.setFixedSize(24, 24)
        self.resize_handle.setStyleSheet("font-weight: bold; font-size: 16px; color: gray;")
        
        self.handle_layout.addWidget(self.handle)
        self.handle_layout.addWidget(self.timer_label)
        self.handle_layout.addStretch()
        self.handle_layout.addWidget(self.drag_dots)
        self.handle_layout.addStretch()
        self.handle_layout.addWidget(self.toggle_llm_btn)
        self.handle_layout.addWidget(self.query_input)
        self.handle_layout.addWidget(self.end_session_btn)
        self.handle_layout.addWidget(self.close_btn)
        self.handle_layout.addWidget(self.resize_handle)
        
        self.layout.addWidget(self.handle_container)
        
        self.setStyleSheet(get_stylesheet())
        self.resize(720, 50); self.move(100, 100); self._old_pos = None

        apply_stealth_affinity(self)
            
        # Hover auto-hide logic
        self.hover_check_timer = QTimer(self)
        self.hover_check_timer.timeout.connect(self._check_hover)
        self.hover_check_timer.start(100) # Check every 100ms
        
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._hide_controls)
        
        self._is_hovering = True

    def toggle_llm_pane(self):
        is_visible = self.display_window.right_pane.isVisible()
        
        # If we are hiding the LLM, kill any AI processes to stop detection/generation
        if is_visible:
            if self.query_thread and self.query_thread.isRunning():
                self.query_thread.cancel()
            if self.gatekeeper_thread and self.gatekeeper_thread.isRunning():
                self.gatekeeper_thread.terminate()
                
            self.debounce_timer.stop()
            self.pending_text = ""
            self.display_window.set_status("idle")
            
        self.display_window.right_pane.setVisible(not is_visible)
        self.toggle_llm_btn.setText("Show LLM" if is_visible else "Hide LLM")
        self.display_window.adjustSize()
        self.setFixedWidth(self.display_window.width())

    def _check_hover(self):
        cursor_pos = QCursor.pos()
        
        # Don't try to calculate if display_window is fully hidden and we are too
        if not self.display_window.isVisible() and not self.isVisible():
            return
            
        display_rect = self.display_window.geometry()
        # To make it easier to hover the invisible toolbar padding, add a little buffer
        control_rect = self.geometry()
        
        # Consider hover true if inside the display transcript or over the control bar
        is_hovering = display_rect.contains(cursor_pos) or control_rect.contains(cursor_pos)
        
        if is_hovering:
            if not self._is_hovering:
                self._is_hovering = True
                self.show()
                # Reposition right away just in case
                self.setFixedWidth(self.display_window.width())
            self.hide_timer.stop()
        else:
            if self._is_hovering:
                self._is_hovering = False
                self.hide_timer.start(10000) # Hide after 10 seconds

    def _hide_controls(self):
        if not self._is_hovering:
            self.hide()

    def on_hotkey_triggered(self):
        """ Triggered by Ctrl+Space """
        # We need to run this on the main thread or use signals
        QTimer.singleShot(0, self.manual_refine)

    def manual_refine(self):
        if not self.rag_assistant or not self.display_window.right_pane.isVisible(): return
        # Grab last 5 final utterances
        client_utterances = [u["text"] for u in self.meeting_logger.get_history() if u["speaker"] == "Client"][-5:]
        if not client_utterances: return
        
        context = " ".join(client_utterances)
        
        # Intentionally cancel any running auto-query
        if self.query_thread and self.query_thread.isRunning():
            self.query_thread.cancel()
            self.query_thread.wait(100)
            
        self.run_rag_query(context, is_manual=True)
        pass

    def handle_new_transcript(self, speaker, text, is_final):
        self.display_window.update_transcript_visual(speaker, text, is_final)
        if is_final:
            self.meeting_logger.log_utterance(speaker, text)
            if speaker == "Client":
                self.pending_text += " " + text
                # Debounce for 1.5 seconds
                self.debounce_timer.start(1500)

    def _trigger_gatekeeper(self):
        if not self.display_window.right_pane.isVisible(): return
        
        text = self.pending_text.strip()
        self.pending_text = ""
        if not text: return
        
        if self.gatekeeper_thread and self.gatekeeper_thread.isRunning(): return
        if self.query_thread and self.query_thread.isRunning(): return
        
        # Fire the Gatekeeper
        self.gatekeeper_thread = IntentGatekeeperThread(self.gatekeeper, text)
        self.gatekeeper_thread.intent_detected.connect(self.on_intent_detected)
        self.gatekeeper_thread.start()
        pass

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
            pass

    def run_rag_query(self, query, is_manual=False):
        if not self.display_window.right_pane.isVisible(): return
        if self.query_thread and self.query_thread.isRunning(): return
        
        self.display_window.set_status("thinking")
        self.display_window.prepare_script_view(query if is_manual else None, is_manual)
        
        context_window = self.meeting_logger.get_recent_context_window(n=4)
        
        self.query_thread = RAGQueryThread(self.rag_assistant, query, context_window=context_window, is_manual=is_manual)
        self.query_thread.chunk_received.connect(self.display_window.append_script_chunk)
        self.query_thread.source_received.connect(self.display_window.append_script_chunk)
        self.query_thread.completed.connect(self.on_query_completed)
        self.query_thread.start()

    def on_query_completed(self):
        self.query_input.setEnabled(True)
        self.display_window.set_status("idle")
        self.display_window.finalize_script_chunk()
        self.meeting_logger.log_rag_interaction("Context Inquiry", self.display_window.last_rag_answer)

    def end_session(self):
        # Stop safety flush
        self.safety_flush_timer.stop()
        self.meeting_logger.flush()
        
        # Hide session windows immediately to clear the screen
        self.hide()
        self.display_window.hide()
        QApplication.processEvents() # Force UI update before blocking dialog
        
        dialog = EndSessionDialog(self)
        choice = dialog.get_choice()
        
        if not choice:
            self.show()
            self.display_window.show()
            self.safety_flush_timer.start(30000)
            return

        # They have chosen to truly end the session
        self.audio_thread.stop()
        self.transcription_thread.stop()
        self.meeting_logger.save_clean_transcript()

        clean_transcript = self.meeting_logger.get_clean_transcript(include_ai=False)

        if choice == "dashboard":
            self.display_window.close()
            self.session_ended.emit(clean_transcript)
            self.close()
            return

        if choice == "transcript":
            history = self.meeting_logger.get_history()
            self.transcript_window = TranscriptWindow(history)
            self.transcript_window.show()
            self.transcript_window.closed.connect(self._finalize_session)
            return

        if not clean_transcript.strip():
            QMessageBox.information(self, "No Transcript", "The meeting transcript is empty. Nothing to summarize.")
            self.display_window.close()
            self.session_ended.emit("")
            self.close()
            return

        # Start summary generation
        self.processing_dialog = ProcessingDialog("Generating Summary...", self)
        self.processing_dialog.show()
        
        self.summary_thread = SummaryThread(self.summary_engine, clean_transcript)
        self.summary_thread.finished.connect(self.on_summary_generated)
        self.summary_thread.error.connect(self.on_summary_error)
        self.summary_thread.start()

    def on_summary_generated(self, summary_data):
        if hasattr(self, 'processing_dialog'):
            self.processing_dialog.close()
            
        self.end_session_btn.setText("🛑 Stop Session")
        self.end_session_btn.setEnabled(True)
        
        if "error" in summary_data:
            QMessageBox.warning(self, "Summary Error", summary_data["error"])
        else:
            # Show summary window
            self.summary_window = SummaryWindow(summary_data, self.summary_engine)
            self.summary_window.show()
            # We don't close the main app yet, let the user see the summary
            # When summary window is closed, we can emit session_ended
            self.summary_window.closed.connect(self._finalize_session)

    def on_summary_error(self, error_msg):
        if hasattr(self, 'processing_dialog'):
            self.processing_dialog.close()
            
        self.end_session_btn.setText("🛑 Stop Session")
        self.end_session_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Failed to generate summary: {error_msg}")

    def _finalize_session(self):
        clean_transcript = self.meeting_logger.get_clean_transcript(include_ai=False)
        self.display_window.close()
        self.session_ended.emit(clean_transcript)
        self.close()

    def close_app(self):
        self.close()
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()

    def on_toggle_visibility_triggered(self):
        """ Triggered by Ctrl+Shift+H """
        QTimer.singleShot(0, self.toggle_visibility)

    def toggle_visibility(self):
        # Toggle whole app visibility (Handle + Display)
        if self.isVisible():
            self.hide()
            self.display_window.hide()
        else:
            self.show()
            self.display_window.show()
            self.raise_()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self._old_pos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event):
        if self._old_pos:
            delta = event.globalPosition().toPoint() - self._old_pos
            self.move(self.pos() + delta); self._old_pos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event): self._old_pos = None
    
    def update_display_position(self):
        # Display window sits elegantly underneath the title bar (this control window)
        self.display_window.move(self.pos().x(), self.pos().y() + self.height())
        
    def moveEvent(self, event): 
        super().moveEvent(event)
        # Always snap display to bottom of title bar when moved
        self.update_display_position()

    def showEvent(self, event): 
        super().showEvent(event)
        self.display_window.show()
        self.update_display_position()
    def closeEvent(self, event):
        logging.info("Close event received. Shutting down threads...")
        try:
            self.safety_flush_timer.stop()
            if hasattr(self, 'audio_thread') and self.audio_thread.isRunning():
                self.audio_thread.stop()
            if hasattr(self, 'transcription_thread') and self.transcription_thread.isRunning():
                self.transcription_thread.stop()
            if hasattr(self, 'hotkey_listener'):
                self.hotkey_listener.stop()
            if hasattr(self, 'meeting_logger'):
                self.meeting_logger.flush()
            self.display_window.close()
        except Exception as e:
            logging.error(f"Shutdown error: {e}", exc_info=True)
        event.accept()
