# AI Sales Meeting Assistant

A professional, real-time AI copilot designed to help sales teams transcribe, analyze, and summarize their meetings. Built with PyQt6 and powered by state-of-the-art LLMs.

## 🚀 Features

- **Real-time Transcription**: High-accuracy live audio transcription using Deepgram.
- **AI Insights & Detection**: Detects customer intent, objections, and key moments during the call using Groq and Google Gemini.
- **Post-Meeting Summaries**: Generates comprehensive meeting summaries, including sentiment analysis and next steps.
- **PDF Export**: Export your meeting summaries to professionally formatted PDF documents.
- **Meeting Dashboard**: View and manage historical meeting transcripts and summaries.
- **Vector Search**: Local vector database (Qdrant) for indexing meeting data, enabling intelligent search and RAG capabilities.
- **Modern UI**: Sleek, dark-themed dashboard built with PyQt6.

## 🛠️ Tech Stack

- **GUI Framework**: PyQt6
- **Speech-to-Text**: Deepgram
- **Language Models**: Google Gemini (1.5 Flash / 2.5 Flash), Groq
- **Vector Database**: Qdrant
- **Styling**: Custom CSS (Modern Dark Mode)

## 📋 Prerequisites

- Python 3.10+
- [Deepgram API Key](https://deepgram.com/)
- [Google AI (Gemini) API Key](https://ai.google.dev/)
- [Groq API Key](https://groq.com/)

## 🔧 Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd Sales_meetings_assistant_pyinstaller
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Create a `.env` file in the root directory and add your API keys:
   ```env
   DEEPGRAM_API_KEY=your_deepgram_key
   GOOGLE_API_KEY=your_gemini_key
   GROQ_API_KEY=your_groq_key
   ```

## 🏃 Running the Application

To start the assistant:
```bash
python main.py
```

## 📦 Packaging (PyInstaller)

To build a standalone executable:
```bash
.\venv\Scripts\python.exe -m PyInstaller build.spec
```
The executable will be located in the `dist/` directory.

## 📁 Project Structure

- `app/`: GUI windows, dialogs, and styling.
- `core/`: AI engines (Summary, RAG, Transcription).
- `qdrant_db/`: Local vector database storage.
- `transcripts/`: Saved meeting transcript files.
- `main.py`: Application entry point.
- `build.spec`: PyInstaller configuration.

## 📄 License

[MIT License](LICENSE)
