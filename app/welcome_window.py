import os
import logging
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QFileDialog, QSystemTrayIcon, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QTimer, pyqtSlot
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebChannel import QWebChannel

from app.assistant_window import AssistantWindow
from app.transcript_window import TranscriptWindow
from core.rag_engine import RAGIndexThread
from core.vector_store import get_vector_store
from app.api import set_app_state, get_app_state
from core.update_manager import check_for_updates
from core.version import VERSION


class WebBridge(QWidget):
    """Bridge for receiving button click events from the React UI via JavaScript."""
    upload_doc_signal = pyqtSignal()
    upload_bio_signal = pyqtSignal()
    start_session_signal = pyqtSignal(bool)  # bool = is_stealth
    delete_signal = pyqtSignal(list)  # list of doc names

    def __init__(self, parent=None):
        super().__init__(parent)


class WelcomeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Sales Meeting Assistant")
        self.setMinimumSize(700, 500)
        self.resize(1100, 750)
        
        # Initialize Vector Store
        try:
            self.store = get_vector_store()
        except Exception as e:
            logging.error(f"Error connecting to Qdrant: {e}")
            self.store = None

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # WebEngine View — renders the React Dashboard
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("http://localhost:8765/"))
        self.main_layout.addWidget(self.browser)
        
        # Inject document & meeting data into the API state
        self._sync_data_to_api()
        
        # Poll for button clicks from the React UI
        self._setup_js_polling()
        
        from core.summary_engine import MeetingSummaryEngine
        self.summary_engine = MeetingSummaryEngine()
        self.summary_thread = None
        self.selected_docs = []
        self.center_on_screen()

        # Check for updates after 3 seconds
        QTimer.singleShot(3000, self._perform_update_check)

    def _sync_data_to_api(self):
        """Push current documents and meetings into the FastAPI state."""
        # Documents
        docs = []
        if self.store:
            doc_names = self.store.list_documents()
            for name in doc_names:
                docs.append({"name": name, "type": "Knowledge Base"})
        set_app_state("documents", docs)
        
        # Meetings (sessions directories)
        meetings = []
        app_data = Path.home() / "AppData" / "Local" / "AI_Meetings_Assistant"
        sessions_dir = app_data / "sessions"
        if sessions_dir.exists():
            # Get all subdirectories starting with 'Session_'
            dirs = [d for d in os.listdir(sessions_dir) if os.path.isdir(sessions_dir / d) and d.startswith("Session_")]
            # Sort descending by name (which has timestamp)
            dirs.sort(reverse=True)
            for d in dirs:
                session_path = sessions_dir / d
                mtime = os.path.getmtime(session_path)
                date_str = datetime.fromtimestamp(mtime).strftime("%b %d, %H:%M")
                has_summary = (session_path / "summary.json").exists()
                meetings.append({
                    "id": d,
                    "filename": d.replace("Session_", "Session "), 
                    "date": date_str,
                    "hasSummary": has_summary
                })
        set_app_state("meetings", meetings)
        set_app_state("current_view", "dashboard")

    def _setup_js_polling(self):
        """
        Poll the React UI for user actions by evaluating JavaScript.
        The React buttons write to window.__qt_action when clicked.
        """
        self.action_timer = QTimer(self)
        self.action_timer.timeout.connect(self._poll_for_actions)
        self.action_timer.start(200)
    
    def _poll_for_actions(self):
        """Check if any button in React has been clicked."""
        js = """
        (function() {
            var action = window.__qt_action || null;
            window.__qt_action = null;
            return JSON.stringify(action);
        })()
        """
        self.browser.page().runJavaScript(js, self._handle_action)

    def _handle_action(self, result):
        """Process actions dispatched from the React UI."""
        if not result or result == "null":
            return
        try:
            import json
            action = json.loads(result)
            if not action:
                return
            
            action_type = action.get("type", "") if isinstance(action, dict) else str(action)
            
            if action_type == "upload_doc":
                self.upload_document()
            elif action_type == "upload_bio":
                self.upload_host_profile()
            elif action_type == "start_session":
                is_stealth = action.get("stealth", False) if isinstance(action, dict) else False
                docs = action.get("docs", []) if isinstance(action, dict) else []
                self.start_session(is_stealth, docs)
            elif action_type == "delete":
                docs = action.get("docs", []) if isinstance(action, dict) else []
                self.delete_selected(docs)
            elif action_type == "generate_summary":
                session_id = action.get("session_id", "") if isinstance(action, dict) else ""
                if session_id:
                    self.generate_session_summary(session_id)
        except Exception as e:
            logging.error(f"Error handling action: {e}")

    def upload_document(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Product Document", "", "Documents (*.pdf *.txt)")
        if file_path:
            self.index_thread = RAGIndexThread(file_path, metadata={"source_type": "product"})
            self.index_thread.finished.connect(self.on_index_finished)
            self.index_thread.error.connect(self.on_index_error)
            self.index_thread.start()

    def upload_host_profile(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Personal Profile (CV/Bio)", "", "Documents (*.pdf *.txt)")
        if file_path:
            self.index_thread = RAGIndexThread(file_path, metadata={"source_type": "host_profile"})
            self.index_thread.finished.connect(self.on_index_finished)
            self.index_thread.error.connect(self.on_index_error)
            self.index_thread.start()

    def on_index_finished(self, assistant):
        self._sync_data_to_api()
        # Force the React UI to refresh
        self.browser.page().runJavaScript("window.location.reload()")

    def on_index_error(self, err_msg):
        logging.error(f"Indexing error: {err_msg}")

    def delete_selected(self, docs=None):
        if not docs:
            return
        for doc in docs:
            try:
                self.store.delete_document(doc)
            except Exception as e:
                logging.error(f"Delete error: {e}")
        self._sync_data_to_api()
        self.browser.page().runJavaScript("window.location.reload()")

    def start_session(self, is_stealth=False, docs=None):
        logging.info(f"Attempting to start session with docs: {docs}")
        if not self.store:
            logging.error("Store not initialized.")
            QMessageBox.critical(self, "Error", "Database not connected. Please restart the app.")
            return

        try:
            from core.rag_engine import SalesAssistant
            selected_docs = docs if docs else []
            logging.info(f"Creating SalesAssistant with docs: {selected_docs}")
            rag_assistant = SalesAssistant(self.store, selected_docs=selected_docs)
            
            logging.info(f"Initializing AssistantWindow (Stealth: {is_stealth})")
            
            self.assistant_window = AssistantWindow(rag_assistant, is_stealth=is_stealth)
            self.assistant_window.session_ended.connect(self.on_session_ended)
            self.assistant_window.show()
            
            self.hide()
            logging.info("Session started successfully.")
        except Exception as e:
            logging.error(f"Failed to start session: {e}", exc_info=True)
            QMessageBox.critical(self, "Session Error", f"Failed to start meeting assistant:\n{str(e)}")

    def on_session_ended(self, transcript_data=None):
        self.show()
        self._sync_data_to_api()
        self.browser.page().runJavaScript("window.location.reload()")

    def generate_session_summary(self, session_id):
        app_data = Path.home() / "AppData" / "Local" / "AI_Meetings_Assistant"
        session_dir = app_data / "sessions" / session_id
        transcript_file = session_dir / "transcript.txt"
        
        if not transcript_file.exists():
            QMessageBox.critical(self, "Error", "Transcript not found for this session.")
            return
            
        with open(transcript_file, "r", encoding="utf-8") as f:
            transcript_text = f.read()
            
        from app.dialogs import ProcessingDialog
        self.processing_dialog = ProcessingDialog(f"Generating Summary for {session_id}...", self)
        self.processing_dialog.show()
        
        from core.summary_engine import SummaryThread
        self.summary_thread = SummaryThread(self.summary_engine, transcript_text)
        self.summary_thread.finished.connect(lambda data: self._on_summary_generated_for_session(session_id, data))
        self.summary_thread.error.connect(self._on_summary_error)
        self.summary_thread.start()
        
    def _on_summary_generated_for_session(self, session_id, summary_data):
        if hasattr(self, 'processing_dialog'):
            self.processing_dialog.close()
            
        if "error" in summary_data:
            QMessageBox.warning(self, "Summary Error", summary_data["error"])
            return
            
        try:
            import json
            app_data = Path.home() / "AppData" / "Local" / "AI_Meetings_Assistant"
            summary_file = app_data / "sessions" / session_id / "summary.json"
            with open(summary_file, "w", encoding="utf-8") as f:
                json.dump(summary_data, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save generated summary: {e}")
            
        # Refresh UI
        self._sync_data_to_api()
        self.browser.page().runJavaScript("window.location.reload()")
        
    def _on_summary_error(self, error_msg):
        if hasattr(self, 'processing_dialog'):
            self.processing_dialog.close()
        QMessageBox.critical(self, "Error", f"Failed to generate summary: {error_msg}")

    def _perform_update_check(self):
        """Checks for updates in the background and notifies the user."""
        import threading
        def run_check():
            has_update, latest_v, download_url = check_for_updates()
            if has_update:
                from PyQt6.QtCore import QMetaObject, Q_ARG
                # Use thread-safe signal invocation to show the dialog
                QMetaObject.invokeMethod(self, "show_update_notification", 
                                       Qt.ConnectionType.QueuedConnection,
                                       Q_ARG(str, latest_v), 
                                       Q_ARG(str, download_url))
        
        threading.Thread(target=run_check, daemon=True).start()

    @pyqtSlot(str, str)
    def show_update_notification(self, latest_version, download_url):
        """Professional update notification dialog."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Update Available")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(f"A new version of AI Sales Assistant is available!")
        msg.setInformativeText(f"Current Version: v{VERSION}\nLatest Version: v{latest_version}\n\nWould you like to download the latest update?")
        
        download_btn = msg.addButton("Download Now", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        
        msg.exec()
        
        if msg.clickedButton() == download_btn:
            import webbrowser
            webbrowser.open(download_url)

    def center_on_screen(self):
        screen = self.screen().availableGeometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)
        
    def closeEvent(self, event):
        from core.vector_store import close_vector_store
        close_vector_store()
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()
