from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from .styles import get_stylesheet

class EndSessionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(400, 260)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QLabel()
        self.container.setObjectName("SummaryMainWidget")
        self.container.setStyleSheet("""
            #SummaryMainWidget {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 12px;
            }
        """)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(20, 20, 20, 20)
        container_layout.setSpacing(15)
        
        title = QLabel("Meeting Finished")
        title.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 600;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(title)
        
        subtitle = QLabel("How would you like to proceed?")
        subtitle.setStyleSheet("color: #71717a; font-size: 14px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(subtitle)
        
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(12)
        
        self.summary_btn = QPushButton("Generate Summary")
        self.summary_btn.setObjectName("PrimaryButton")
        self.summary_btn.setMinimumHeight(45)
        
        self.transcript_btn = QPushButton("View Transcript")
        self.transcript_btn.setObjectName("SecondaryButton")
        self.transcript_btn.setMinimumHeight(45)
        
        self.dashboard_btn = QPushButton("Go back to dashboard")
        self.dashboard_btn.setObjectName("SecondaryButton")
        self.dashboard_btn.setMinimumHeight(45)
        
        btn_layout.addWidget(self.summary_btn)
        btn_layout.addWidget(self.transcript_btn)
        btn_layout.addWidget(self.dashboard_btn)
        
        container_layout.addLayout(btn_layout)
        
        self.layout.addWidget(self.container)
        self.setStyleSheet(get_stylesheet())
        
        self.summary_btn.clicked.connect(lambda: self.done(1))
        self.transcript_btn.clicked.connect(lambda: self.done(2))
        self.dashboard_btn.clicked.connect(lambda: self.done(3))

    def get_choice(self):
        result = self.exec()
        if result == 1: return "summary"
        if result == 2: return "transcript"
        if result == 3: return "dashboard"
        return None

class ProcessingDialog(QDialog):
    def __init__(self, message="Generating Summary...", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(300, 150)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QLabel()
        self.container.setStyleSheet("""
            background-color: #18181b;
            border: 1px solid #27272a;
            border-radius: 12px;
        """)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(20, 20, 20, 20)
        container_layout.setSpacing(15)
        
        # Simple spinner-like emoji or icon
        self.icon = QLabel("⏳")
        self.icon.setStyleSheet("font-size: 24px;")
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self.icon)
        
        self.label = QLabel(message)
        self.label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 500;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self.label)
        
        layout.addWidget(self.container)
        
        # Optional: Add a small pulse animation to the icon
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(500)
        self._step = 0

    def _animate(self):
        icons = ["⏳", "⌛"]
        self.icon.setText(icons[self._step % 2])
        self._step += 1

from PyQt6.QtCore import QTimer
