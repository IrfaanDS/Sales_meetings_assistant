import sys
import os
import logging
import traceback
import platform
from pathlib import Path
from logging.handlers import RotatingFileHandler

log_dir = Path.home() / "AppData" / "Local" / "AI_Meetings_Assistant"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = str(log_dir / "MASTER_DEBUG_LOG.txt")

handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.DEBUG)

def log_msg(msg):
    logging.info(msg)
    try:
        if sys.stdout is not None:
            print(msg)
    except Exception:
        pass

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

log_msg("--- STARTING APPLICATION ---")
log_msg(f"OS: {platform.system()} {platform.version()}")
log_msg(f"Python: {sys.version}")
log_msg(f"Executable: {sys.executable}")
log_msg(f"Frozen: {getattr(sys, 'frozen', False)}")
log_msg(f"Log file: {log_file}")

try:
    from PyQt6.QtWidgets import QApplication
    from app.welcome_window import WelcomeWindow
    log_msg("Imports successful.")
except Exception as e:
    log_msg(f"CRITICAL IMPORT ERROR: {e}")
    logging.error(traceback.format_exc())
    input("Press Enter to exit...")
    sys.exit(1)

import threading
import uvicorn

def run_fastapi():
    try:
        from app.api import app as fastapi_app
        log_msg("Starting FastAPI server on port 8765...")
        uvicorn.run(fastapi_app, host="127.0.0.1", port=8765, log_level="warning")
    except Exception as e:
        log_msg(f"FASTAPI SERVER CRASHED: {e}")
        logging.error(traceback.format_exc())

def main():
    try:
        threading.Thread(target=run_fastapi, daemon=True).start()
        
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(True)
        window = WelcomeWindow()
        window.show()
        log_msg("Entering main event loop.")
        sys.exit(app.exec())
    except Exception as e:
        log_msg(f"CRITICAL RUNTIME ERROR: {e}")
        logging.error(traceback.format_exc())
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()
