# ARIA: AI Sales Meeting Assistant

ARIA is a professional, real-time AI Sales Copilot designed to empower sales teams by providing live narration-ready scripts, automated intent detection, and comprehensive post-meeting intelligence. Built with a high-performance PyQt6/React hybrid architecture.

## 🚀 Key Features

- **Live AI Scripting**: Generates word-for-word speaking scripts for the host based on real-time client dialogue.
- **Intent Gatekeeper**: Automatically detects high-intent technical questions or objections to trigger intelligent RAG responses.
- **Professional Dashboard**: A modern React-powered interface for managing documents, session history, and summaries.
- **Local RAG Engine**: Private, secure vector search using Qdrant for indexing product documentation and host profiles.
- **Automated Summaries**: Generates structured meeting intelligence including sentiment analysis and actionable next steps.
- **Enterprise UI Overlay**: A beautiful, glassy HUD that stays on top of your meeting (Zoom/Teams/etc.) with adjustable opacity and stealth modes.
- **Auto-Update System**: Built-in update manager that checks for new releases directly from GitHub.

## 🛠️ Tech Stack

- **Frontend**: React 18, Tailwind CSS, Vite (embedded via `QWebEngineView`)
- **Backend**: Python 3.11, FastAPI, Uvicorn
- **GUI Framework**: PyQt6
- **Speech-to-Text**: Deepgram (High-fidelity streaming)
- **AI/LLM**: Google Gemini 1.5/2.0 Flash, Groq (Llama 3.1)
- **Vector DB**: Qdrant (Local persistent storage)

## 🔧 Installation & Setup

### 1. Prerequisites
- Python 3.11+
- Node.js 20+
- API Keys: [Deepgram](https://deepgram.com/), [Google AI](https://ai.google.dev/), [Groq](https://groq.com/)

### 2. Environment Configuration
Create a `.env` file in the root directory:
```env
DEEPGRAM_API_KEY=your_key
GOOGLE_API_KEY=your_key
GROQ_API_KEY=your_key
```

### 3. Backend Setup
```bash
python -m venv venv
source venv/Scripts/activate  # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Frontend Setup
```bash
cd web
npm install
npm run build
cd ..
```

## 📦 Building & Distribution

### Local Build (Windows)
To create a standalone executable for distribution:
1. **Download model cache**: `python scripts/download_model.py`
2. **Build with PyInstaller**: `pyinstaller build.spec`

### CI/CD Pipeline
The project includes a GitHub Actions workflow (`.github/workflows/release.yml`) that automates the build process.
- **Trigger**: Push a tag starting with `v` (e.g., `git tag v1.0.0` & `git push origin v1.0.0`).
- **Output**: A compiled `.zip` containing the portable application is automatically uploaded to a new GitHub Release.

## 📁 Project Structure

- `app/`: PyQt6 GUI windows and visual components.
- `web/`: React dashboard source code (Vite).
- `core/`: Core engines for RAG, Summarization, and Audio processing.
- `scripts/`: Utility scripts for build automation and model management.
- `build.spec`: Optimized PyInstaller configuration for Windows distribution.

## 📄 License
[MIT License](LICENSE)
