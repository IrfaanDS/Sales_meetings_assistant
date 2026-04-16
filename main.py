import sys
from PyQt6.QtWidgets import QApplication
from app.welcome_window import WelcomeWindow

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Create the welcome window
    window = WelcomeWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
