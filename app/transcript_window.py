import os
from datetime import datetime
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QScrollArea, QPushButton, QFileDialog, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from .styles import get_stylesheet

class TranscriptEntry(QWidget):
    def __init__(self, timestamp, speaker, text, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(15)
        
        meta_widget = QWidget()
        meta_widget.setFixedWidth(80)
        meta_layout = QVBoxLayout(meta_widget)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        
        time_lbl = QLabel(timestamp)
        time_lbl.setObjectName("Timestamp")
        
        speaker_lbl = QLabel(speaker.upper())
        speaker_lbl.setObjectName("SpeakerTag")
        if "YOU" in speaker.upper() or "REP" in speaker.upper():
            speaker_lbl.setStyleSheet("color: #93c5fd; font-family: 'Inter'; font-weight: 700; font-size: 10px; letter-spacing: 0.1em;")
        else:
            speaker_lbl.setStyleSheet("color: #fdba74; font-family: 'Inter'; font-weight: 700; font-size: 10px; letter-spacing: 0.1em;")
            
        meta_layout.addWidget(time_lbl)
        meta_layout.addWidget(speaker_lbl)
        meta_layout.addStretch()
        
        content_lbl = QLabel(text)
        content_lbl.setWordWrap(True)
        content_lbl.setObjectName("TranscriptionLabel")
        content_lbl.setStyleSheet("color: #ededed;")
        
        layout.addWidget(meta_widget)
        layout.addWidget(content_lbl, 1)

class TranscriptWindow(QMainWindow):
    closed = pyqtSignal()

    def __init__(self, transcript_data, parent=None):
        super().__init__(parent)
        self.transcript_data = transcript_data
        
        self.setWindowTitle("Meeting Transcript")
        self.setMinimumSize(600, 400)
        self.resize(800, 700)
        self.setWindowFlags(Qt.WindowType.Window) # Allow normal window behavior
        
        self.central_widget = QFrame()
        self.central_widget.setObjectName("SummaryMainWidget") # Use same style as Summary window
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)
        
        # Header
        header_layout = QVBoxLayout()
        top_row = QHBoxLayout()
        
        title = QLabel("Meeting Transcript")
        title.setObjectName("HeaderTitle")
        title.setStyleSheet("font-size: 24px;")
        
        date_lbl = QLabel(datetime.now().strftime("%B %d, %Y"))
        date_lbl.setObjectName("Timestamp")
        
        top_row.addWidget(title)
        top_row.addStretch()
        top_row.addWidget(date_lbl)
        
        header_layout.addLayout(top_row)
        
        sub_title = QLabel("InsightPulse AI Analysis")
        sub_title.setObjectName("SectionHeader")
        header_layout.addWidget(sub_title)
        
        self.main_layout.addLayout(header_layout)
        
        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: transparent; border-top: 1px solid #2c2d31; border-bottom: 1px solid #2c2d31; border-left: none; border-right: none;")
        
        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(20, 10, 20, 10)
        self.content_layout.setSpacing(0) # Spacing handled by TranscriptEntry
        
        # Add transcript lines
        # Assuming transcript_data is a list of lines or the full history
        if isinstance(transcript_data, list):
            for entry in transcript_data:
                speaker = entry.get("speaker", "Unknown")
                text = entry.get("text", "")
                ts = entry.get("timestamp", "")
                if ts and "T" in ts: # ISO format
                    ts = datetime.fromisoformat(ts).strftime("%H:%M")
                
                self.content_layout.addWidget(TranscriptEntry(ts, speaker, text))
                # Add divider
                line = QLabel()
                line.setFixedHeight(1)
                line.setStyleSheet("background-color: #2c2d31;")
                self.content_layout.addWidget(line)
        
        self.content_layout.addStretch()
        self.scroll_area.setWidget(self.content_container)
        self.main_layout.addWidget(self.scroll_area)
        
        # Footer
        footer_layout = QHBoxLayout()
        
        self.back_btn = QPushButton("← Back to Dashboard")
        self.back_btn.setObjectName("SecondaryButton")
        self.back_btn.clicked.connect(self.close)
        
        self.export_btn = QPushButton("Mark as Reviewed")
        self.export_btn.setStyleSheet("background-color: #93c5fd; color: #0f172a; border-radius: 6px; font-weight: 600; padding: 10px 18px;")
        self.export_btn.clicked.connect(self.save_transcript)
        
        footer_layout.addWidget(self.back_btn)
        footer_layout.addStretch()
        footer_layout.addWidget(self.export_btn)
        
        self.main_layout.addLayout(footer_layout)
        
        self.setStyleSheet(get_stylesheet())

    def save_transcript(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Transcript", f"Transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "Text Files (*.txt)"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    for entry in self.transcript_data:
                        speaker = entry.get("speaker", "Unknown")
                        text = entry.get("text", "")
                        ts = entry.get("timestamp", "")
                        f.write(f"[{ts}] {speaker}: {text}\n")
            except Exception as e:
                print(f"Error saving transcript: {e}")

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()
