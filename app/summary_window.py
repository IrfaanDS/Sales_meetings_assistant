import os
import logging
import webbrowser
from urllib.parse import quote
from datetime import datetime
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QScrollArea, QPushButton, QFileDialog, QMessageBox, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, QMarginsF
from PyQt6.QtGui import QTextDocument, QPageLayout
from PyQt6.QtPrintSupport import QPrinter
from .styles import get_stylesheet

class SentimentBar(QWidget):
    def __init__(self, sentiment_text, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 10, 0, 10)
        
        header_layout = QHBoxLayout()
        icon = QLabel("🧠")
        icon.setStyleSheet("color: #ffb867; font-size: 18px;")
        
        title = QLabel("Sentiment Analysis")
        title.setObjectName("SectionHeader")
        title.setStyleSheet("color: #ffb867;")
        
        header_layout.addWidget(icon)
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        self.layout.addLayout(header_layout)
        
        # Sentiment bar representation
        bar_container = QWidget()
        bar_container.setFixedHeight(30)
        bar_layout = QVBoxLayout(bar_container)
        bar_layout.setContentsMargins(0, 10, 0, 0)
        
        self.bar = QFrame()
        self.bar.setFixedHeight(8)
        self.bar.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                        stop:0 #ffb4ab, stop:0.5 #474746, stop:1 #a5c8ff);
            border-radius: 4px;
        """)
        bar_layout.addWidget(self.bar)
        
        # Indicator based on sentiment text
        self.indicator = QFrame(bar_container)
        self.indicator.setFixedSize(12, 12)
        self.indicator.setStyleSheet("""
            background-color: #a5c8ff;
            border: 2px solid white;
            border-radius: 6px;
        """)
        
        # Position indicator based on sentiment
        pos = 0.5 # Neutral default
        text = sentiment_text.lower()
        if "positive" in text or "optimistic" in text or "great" in text:
            pos = 0.8
        elif "negative" in text or "challenging" in text or "skeptical" in text:
            pos = 0.2
            self.indicator.setStyleSheet("background-color: #ffb4ab; border: 2px solid white; border-radius: 6px;")
        
        # We'll need to position it in resizeEvent or just use fixed width
        self.pos_ratio = pos
        
        self.layout.addWidget(bar_container)
        
        labels_layout = QHBoxLayout()
        labels_layout.addWidget(QLabel("Skeptical"))
        labels_layout.addStretch()
        labels_layout.addWidget(QLabel("Neutral"))
        labels_layout.addStretch()
        labels_layout.addWidget(QLabel("Optimistic"))
        for i in range(labels_layout.count()):
            widget = labels_layout.itemAt(i).widget()
            if widget:
                widget.setStyleSheet("color: #8b919e; font-size: 11px; font-family: 'JetBrains Mono';")
        
        self.layout.addLayout(labels_layout)
        
        desc = QLabel(sentiment_text)
        desc.setWordWrap(True)
        desc.setObjectName("TranscriptionLabel")
        self.layout.addWidget(desc)

    def paintEvent(self, event):
        super().paintEvent(event)
        # Move indicator
        width = self.bar.width()
        x = int(width * self.pos_ratio) - 6
        self.indicator.move(x, 8)

class SummarySectionNew(QFrame):
    def __init__(self, icon_name, title, content, color="#a5c8ff", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        header_layout = QHBoxLayout()
        icon_map = {
            "description": "📄",
            "checklist": "✅",
            "warning": "⚠️",
            "near_me": "🚀"
        }
        icon_char = icon_map.get(icon_name, "•")
        
        icon = QLabel(icon_char)
        icon.setStyleSheet(f"color: {color}; font-size: 18px;")
        
        title_lbl = QLabel(title.upper())
        title_lbl.setObjectName("SectionHeader")
        title_lbl.setStyleSheet(f"color: {color};")
        
        header_layout.addWidget(icon)
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        if isinstance(content, list):
            if title.lower() == "action items":
                content_text = "\n\n".join([f"◻️  {item}" for item in content])
            else:
                content_text = "\n\n".join([f"•  {item}" for item in content])
        else:
            content_text = str(content)
            
        content_lbl = QLabel(content_text)
        content_lbl.setWordWrap(True)
        content_lbl.setObjectName("TranscriptionLabel")
        layout.addWidget(content_lbl)

class SummaryWindow(QMainWindow):
    closed = pyqtSignal()

    def __init__(self, summary_data, engine, parent=None):
        super().__init__(parent)
        self.summary_data = summary_data
        self.engine = engine
        
        self.setWindowTitle("Meeting Summary")
        self.setMinimumSize(600, 500)
        self.resize(800, 800)
        self.setWindowFlags(Qt.WindowType.Window)
        
        self.central_widget = QFrame()
        self.central_widget.setObjectName("SummaryMainWidget")
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = QWidget()
        header.setFixedHeight(80)
        header.setStyleSheet("background-color: transparent; border-bottom: 1px solid #2c2d31;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)
        
        title_vbox = QVBoxLayout()
        title_lbl = QLabel("Post-Meeting Summary")
        title_lbl.setObjectName("HeaderTitle")
        
        meta_hbox = QHBoxLayout()
        date_lbl = QLabel(datetime.now().strftime("%b %d, %Y"))
        date_lbl.setObjectName("Timestamp")
        meta_hbox.addWidget(date_lbl)
        meta_hbox.addStretch()
        
        title_vbox.addWidget(title_lbl)
        title_vbox.addLayout(meta_hbox)
        
        header_layout.addLayout(title_vbox)
        header_layout.addStretch()
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet("background-color: transparent; color: #ffffff; font-size: 24px; border: none;")
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)
        
        self.main_layout.addWidget(header)
        
        # Content
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        content_container = QWidget()
        self.content_layout = QVBoxLayout(content_container)
        self.content_layout.setContentsMargins(24, 20, 24, 20)
        self.content_layout.setSpacing(20)
        
        # Sections
        self.content_layout.addWidget(SummarySectionNew("description", "Executive Summary", self.summary_data.get("executive_summary", "N/A")))
        
        sentiment_text = self.summary_data.get("sentiment_analysis", "Neutral")
        sentiment_card = QFrame()
        sentiment_card.setObjectName("Card")
        sentiment_vbox = QVBoxLayout(sentiment_card)
        sentiment_vbox.addWidget(SentimentBar(sentiment_text))
        self.content_layout.addWidget(sentiment_card)
        
        self.content_layout.addWidget(SummarySectionNew("checklist", "Action Items", self.summary_data.get("action_items", []), color="#a5c8ff"))
        self.content_layout.addWidget(SummarySectionNew("warning", "Client Objections", self.summary_data.get("client_objections", []), color="#ffb4ab"))
        self.content_layout.addWidget(SummarySectionNew("near_me", "Next Steps", self.summary_data.get("next_steps", []), color="#e0e2eb"))
        
        self.content_layout.addStretch()
        self.scroll_area.setWidget(content_container)
        self.main_layout.addWidget(self.scroll_area)
        
        # Footer
        footer = QWidget()
        footer.setStyleSheet("background-color: rgba(30, 30, 30, 0.8); border-top: 1px solid rgba(255, 255, 255, 0.08);")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 15, 24, 15)
        footer_layout.setSpacing(15)
        
        self.pdf_btn = QPushButton("📄 Export to PDF")
        self.pdf_btn.setFixedHeight(44)
        self.pdf_btn.setStyleSheet("background-color: #93c5fd; color: #0f172a; border-radius: 6px; font-weight: 600;")
        self.pdf_btn.clicked.connect(self.export_pdf)
        
        self.email_btn = QPushButton("✉️ Email Summary")
        self.email_btn.setFixedHeight(44)
        self.email_btn.setStyleSheet("background-color: #16a34a; color: #ffffff; border-radius: 6px; font-weight: 600;")
        self.email_btn.clicked.connect(self.email_summary)
        
        footer_layout.addWidget(self.pdf_btn)
        footer_layout.addWidget(self.email_btn)
        
        self.main_layout.addWidget(footer)
        
        self.setStyleSheet(get_stylesheet())

    def export_pdf(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Summary PDF", "Meeting_Summary.pdf", "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        try:
            # Construct HTML content for the PDF
            html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    h1 {{ color: #1e3a8a; text-align: center; border-bottom: 2px solid #1e3a8a; padding-bottom: 10px; }}
                    h2 {{ color: #1e40af; border-bottom: 1px solid #ddd; margin-top: 20px; }}
                    .section {{ margin-bottom: 20px; }}
                    .date {{ text-align: center; color: #666; font-size: 12px; margin-bottom: 30px; }}
                    ul {{ list-style-type: none; padding-left: 0; }}
                    li {{ margin-bottom: 8px; padding-left: 20px; position: relative; }}
                    li:before {{ content: "•"; position: absolute; left: 0; color: #1e40af; }}
                    .sentiment {{ background: #f3f4f6; padding: 15px; border-radius: 8px; font-style: italic; }}
                </style>
            </head>
            <body>
                <h1>Sales Meeting Summary</h1>
                <div class="date">Generated on: {datetime.now().strftime('%B %d, %Y - %H:%M')}</div>
                
                <div class="section">
                    <h2>1. Executive Summary</h2>
                    <p>{self.summary_data.get('executive_summary', 'N/A')}</p>
                </div>

                <div class="section">
                    <h2>2. Action Items</h2>
                    <ul>
                        {''.join([f"<li>{item}</li>" for item in self.summary_data.get('action_items', [])]) if self.summary_data.get('action_items') else "<li>No specific action items identified.</li>"}
                    </ul>
                </div>

                <div class="section">
                    <h2>3. Client Objections</h2>
                    <ul>
                        {''.join([f"<li>{item}</li>" for item in self.summary_data.get('client_objections', [])]) if self.summary_data.get('client_objections') else "<li>No client objections raised.</li>"}
                    </ul>
                </div>

                <div class="section">
                    <h2>4. Next Steps</h2>
                    <ul>
                        {''.join([f"<li>{item}</li>" for item in self.summary_data.get('next_steps', [])]) if self.summary_data.get('next_steps') else "<li>No next steps defined.</li>"}
                    </ul>
                </div>

                <div class="section">
                    <h2>5. Sentiment Analysis</h2>
                    <div class="sentiment">{self.summary_data.get('sentiment_analysis', 'Neutral')}</div>
                </div>
            </body>
            </html>
            """

            doc = QTextDocument()
            doc.setHtml(html)

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(file_path)
            # Fix: PyQt6 requires QMarginsF object and QPageLayout unit
            printer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)

            doc.print(printer)
            QMessageBox.information(self, "Success", f"Summary exported successfully to:\n{file_path}")

        except Exception as e:
            logging.error(f"Error exporting PDF: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to export PDF: {str(e)}")

    def email_summary(self):
        subject = quote("Meeting Summary")
        body_text = "MEETING SUMMARY\n\n"
        sections = [
            ("EXECUTIVE SUMMARY", "executive_summary"),
            ("ACTION ITEMS", "action_items"),
            ("CLIENT OBJECTIONS", "client_objections"),
            ("NEXT STEPS", "next_steps"),
            ("SENTIMENT ANALYSIS", "sentiment_analysis")
        ]
        
        for title, key in sections:
            content = self.summary_data.get(key, "")
            if content:
                body_text += f"--- {title} ---\n"
                if isinstance(content, list):
                    body_text += "\n".join([f"• {item}" for item in content])
                else:
                    body_text += str(content)
                body_text += "\n\n"
        
        body = quote(body_text)
        mailto_url = f"mailto:?subject={subject}&body={body}"
        try:
            webbrowser.open(mailto_url)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open email client: {str(e)}")

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()
