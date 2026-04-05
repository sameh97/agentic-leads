"""Run with: uvicorn main:app --reload --port 8000"""
from dotenv import load_dotenv
load_dotenv()

from app.api.server import app  # noqa — re-export for uvicorn