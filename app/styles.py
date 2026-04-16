def get_stylesheet():
    return """
    QMainWindow {
        background-color: transparent;
    }
    
    #MainWidget {
        background-color: transparent;
    }

    #Handle {
        background-color: rgba(60, 60, 60, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 6px;
        color: #aaaaaa;
        font-size: 18px;
        font-weight: bold;
        min-width: 24px;
        max-width: 24px;
        min-height: 40px;
        margin-right: 4px;
    }
    
    #Handle:hover {
        background-color: rgba(90, 90, 90, 0.8);
        color: #ffffff;
    }



    #CloseButton {
        background-color: rgba(200, 50, 50, 0.7);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: bold;
        font-family: Arial;
        margin-right: 8px;
    }
    
    #CloseButton:hover {
        background-color: rgba(220, 50, 50, 1.0);
    }

    #TranscriptionLabel {
        color: #ffffff;
        font-family: 'Segoe UI', Roboto, sans-serif;
        font-size: 18px;
        font-weight: 500;
        padding: 5px;
        background-color: transparent;
    }

    #TranscriptionScrollArea {
        background-color: rgba(0, 0, 0, 0.4);
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }

    QScrollArea QWidget {
        background-color: transparent;
    }

    QScrollBar:vertical {
        border: none;
        background: transparent;
        width: 8px;
        margin: 0px;
    }

    QScrollBar::handle:vertical {
        background: rgba(255, 255, 255, 0.2);
        min-height: 20px;
        border-radius: 4px;
    }

    QScrollBar::handle:vertical:hover {
        background: rgba(255, 255, 255, 0.3);
    }

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    
    #ResizeHandle {
        background-color: rgba(60, 60, 60, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 6px;
        color: #aaaaaa;
        font-size: 14px;
        font-weight: bold;
        min-width: 24px;
        max-width: 24px;
        min-height: 24px;
        margin-top: 4px;
    }
    
    #ResizeHandle:hover {
        background-color: rgba(90, 90, 90, 0.8);
        color: #ffffff;
    }
    """
