def get_stylesheet():
    return """
    /* Ultra-Modern SaaS Design System */
    
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }

    QMainWindow, QDialog, QWidget#MainWidget {
        background-color: transparent;
        color: #e2e8f0;
    }

    /* Main Container Backgrounds */
    #WelcomeMainWidget, #SummaryMainWidget, #AssistantMainWidget {
        background-color: #131417;
        border-radius: 12px;
        border: 1px solid #2c2d31;
    }

    /* Semi-Transparent Overlays */
    QFrame#FrostedPanel {
        background-color: rgba(0, 0, 0, 0.85);
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }

    /* Header Styling */
    QLabel#HeaderTitle {
        font-size: 18px;
        font-weight: 700;
        color: #ffffff;
        letter-spacing: -0.02em;
    }

    QLabel#Timestamp {
        font-size: 12px;
        font-weight: 500;
        color: #94a3b8;
    }
    
    QLabel#SectionHeader {
        font-size: 11px;
        font-weight: 700;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Card System */
    QFrame#Card {
        background-color: #131417;
        border: 1px solid #2c2d31;
        border-radius: 8px;
    }

    QFrame#Card:hover {
        background-color: #1e1f24;
        border: 1px solid #3b4048;
    }

    /* Premium Buttons */
    QPushButton {
        font-size: 13px;
        font-weight: 600;
        border-radius: 6px;
        padding: 8px 16px;
        outline: none;
    }

    QPushButton#PrimaryButton {
        background-color: #3b82f6;
        color: #ffffff;
        border: none;
    }

    QPushButton#PrimaryButton:hover {
        background-color: #2563eb;
    }

    QPushButton#PrimaryButton:pressed {
        background-color: #1d4ed8;
    }

    QPushButton#PrimaryButton:disabled {
        background-color: #1e293b;
        color: #64748b;
    }

    QPushButton#SecondaryButton {
        background-color: transparent;
        color: #e2e8f0;
        border: 1px solid #334155;
    }

    QPushButton#SecondaryButton:hover {
        background-color: #1e293b;
        border: 1px solid #475569;
    }

    QPushButton#EndButton {
        background-color: transparent;
        color: #f87171;
        border: 1px solid #450a0a;
    }

    QPushButton#EndButton:hover {
        background-color: #450a0a;
        border: 1px solid #7f1d1d;
    }

    /* Input & Text */
    QLineEdit {
        background-color: #1e1f24;
        color: #e2e8f0;
        border: 1px solid #2c2d31;
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 13px;
    }

    QLineEdit:focus {
        border: 1px solid #3b82f6;
    }

    QScrollArea {
        border: none;
        background-color: transparent;
    }

    QScrollArea > QWidget > QWidget {
        background-color: transparent;
    }

    QScrollArea QWidget {
        background-color: transparent;
    }

    /* Custom Scrollbar */
    QScrollBar:vertical {
        background: transparent;
        width: 6px;
        margin: 0px;
    }

    QScrollBar::handle:vertical {
        background: #334155;
        border-radius: 3px;
        min-height: 20px;
    }

    QScrollBar::handle:vertical:hover {
        background: #475569;
    }

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }

    /* Transcription Area */
    QLabel#TranscriptionLabel {
        color: #e2e8f0;
        font-size: 13px;
        line-height: 1.5;
    }

    /* Script Overlay Area */
    QLabel#ScriptLabel {
        color: #ffffff;
        font-size: 15px;
        font-weight: 500;
    }

    /* Checkbox Modernized */
    QCheckBox {
        color: #94a3b8;
        font-size: 12px;
        spacing: 8px;
    }

    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        background-color: #1e1f24;
        border: 1px solid #334155;
        border-radius: 4px;
    }

    QCheckBox::indicator:checked {
        background-color: #3b82f6;
        border: 1px solid #3b82f6;
        image: url(check.png); /* Placeholder if needed, but qt draws its own sometimes */
    }
    """
