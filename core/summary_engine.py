import os
import logging
import json
import asyncio
from datetime import datetime
from pathlib import Path
import google.generativeai as genai
from fpdf import FPDF
from dotenv import load_dotenv

load_dotenv()

class MeetingSummaryEngine:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            self.model = None
            logging.error("GOOGLE_API_KEY not found in environment.")

    def _clean_text(self, text):
        """Sanitize text for FPDF latin-1 encoding."""
        if not text: return ""
        return str(text).encode('latin-1', 'replace').decode('latin-1').replace('?', ' ')

    async def generate_summary(self, transcript: str) -> dict:
        """
        Generates a structured meeting summary using Gemini.
        Returns a dictionary with the summary components.
        """
        if not self.model:
            return {"error": "LLM model not initialized (missing API key)"}

        if not transcript.strip():
            return {"error": "Transcript is empty"}

        prompt = f"""
        Analyze the following sales meeting transcript and provide a structured summary.
        Transcript:
        \"\"\"
        {transcript}
        \"\"\"

        Please provide the following sections in your response:
        1. Executive Summary: A concise overview of the meeting goals and outcome (2-3 sentences).
        2. Action Items: A list of specific tasks mentioned, with the assigned owner if identifiable.
        3. Client Objections: Any concerns, pushbacks, or objections raised by the client.
        4. Next Steps: Clear chronological steps to be taken after this meeting.
        5. Sentiment Analysis: A brief assessment of the overall meeting tone (e.g., Positive, Neutral, or Challenging) and why.

        Format your response as a JSON object with the following keys:
        "executive_summary", "action_items", "client_objections", "next_steps", "sentiment_analysis"
        
        The values for "action_items", "client_objections", and "next_steps" should be lists of strings.
        The values for "executive_summary" and "sentiment_analysis" should be strings.
        
        Respond ONLY with the raw JSON object.
        """

        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=1024,
                    response_mime_type="application/json"
                )
            )
            
            summary_data = json.loads(response.text)
            return summary_data
        except Exception as e:
            logging.error(f"Error generating summary: {e}")
            return {"error": f"Failed to generate summary: {str(e)}"}

    def export_to_pdf(self, summary_data: dict, output_path: str) -> str:
        """
        Exports the summary data to a PDF file.
        Returns the path to the generated PDF.
        """
        try:
            pdf = FPDF()
            pdf.add_page()
            
            # Title
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, "Sales Meeting Summary", ln=True, align='C')
            pdf.set_font("Arial", '', 10)
            pdf.cell(0, 10, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='C')
            pdf.ln(10)

            # Executive Summary
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, "1. Executive Summary", ln=True)
            pdf.set_font("Arial", '', 10)
            pdf.multi_cell(0, 5, self._clean_text(summary_data.get("executive_summary", "N/A")))
            pdf.ln(5)

            # Action Items
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, "2. Action Items", ln=True)
            pdf.set_font("Arial", '', 10)
            action_items = summary_data.get("action_items", [])
            if action_items:
                for item in action_items:
                    pdf.multi_cell(0, 5, f"- {self._clean_text(item)}")
            else:
                pdf.cell(0, 5, "No specific action items identified.", ln=True)
            pdf.ln(5)

            # Client Objections
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, "3. Client Objections", ln=True)
            pdf.set_font("Arial", '', 10)
            objections = summary_data.get("client_objections", [])
            if objections:
                for obj in objections:
                    pdf.multi_cell(0, 5, f"- {self._clean_text(obj)}")
            else:
                pdf.cell(0, 5, "No client objections raised.", ln=True)
            pdf.ln(5)

            # Next Steps
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, "4. Next Steps", ln=True)
            pdf.set_font("Arial", '', 10)
            next_steps = summary_data.get("next_steps", [])
            if next_steps:
                for step in next_steps:
                    pdf.multi_cell(0, 5, f"- {self._clean_text(step)}")
            else:
                pdf.cell(0, 5, "No next steps defined.", ln=True)
            pdf.ln(5)

            # Sentiment Analysis
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, "5. Sentiment Analysis", ln=True)
            pdf.set_font("Arial", '', 10)
            pdf.multi_cell(0, 5, self._clean_text(summary_data.get("sentiment_analysis", "N/A")))
            
            pdf.output(output_path)
            return output_path
        except Exception as e:
            logging.error(f"Error exporting PDF: {e}")
            return ""

from PyQt6.QtCore import QThread, pyqtSignal

class SummaryThread(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, engine: MeetingSummaryEngine, transcript: str):
        super().__init__()
        self.engine = engine
        self.transcript = transcript

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            summary = loop.run_until_complete(self.engine.generate_summary(self.transcript))
            self.finished.emit(summary)
            loop.close()
        except Exception as e:
            logging.error(f"SummaryThread error: {e}", exc_info=True)
            self.error.emit(str(e))
