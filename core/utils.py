import os
from pathlib import Path

def get_app_data_dir() -> Path:
    """Return the persistent AppData directory for the application, using LOCALAPPDATA environment variable on Windows."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        app_data = Path(local_app_data) / "AI_Meetings_Assistant"
    else:
        # Fallback for testing or non-Windows OS
        app_data = Path.home() / "AppData" / "Local" / "AI_Meetings_Assistant"
    
    app_data.mkdir(parents=True, exist_ok=True)
    return app_data

def load_env_file():
    """Load the environment variables from the .env file situated next to the executable (if frozen) or in the project root."""
    import sys
    from dotenv import load_dotenv
    if getattr(sys, 'frozen', False):
        env_path = Path(sys.executable).parent / ".env"
    else:
        env_path = Path(__file__).resolve().parent.parent / ".env"
    
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()

