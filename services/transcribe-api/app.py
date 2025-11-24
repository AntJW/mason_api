# app.py
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import whisper
from pyannote.audio import Pipeline
import tempfile
import json
import torch
import os

# Global variables for models
whisper_model = None
pyannote_pipeline = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    global whisper_model, pyannote_pipeline
    print("Loading Whisper model...")
    whisper_model = whisper.load_model(
        "turbo", device="cuda")  # GPU by default

    print("Loading PyAnnote pipeline...")
    # Use HuggingFace API token or local model
    pyannote_pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1", token=os.getenv("HUGGINGFACE_TOKEN"))

    # send pipeline to GPU (when available)
    pyannote_pipeline.to(torch.device("cuda"))
    print("Models loaded successfully!")

    yield  # App runs here

    # Shutdown (optional cleanup code can go here)
    print("Shutting down...")


app = FastAPI(lifespan=lifespan)

# Enable CORS if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run"""
    return {
        "status": "healthy",
        "models_loaded": whisper_model is not None and pyannote_pipeline is not None
    }


@app.post("/transcribe")
async def transcribe_audio(file: UploadFile):
    if whisper_model is None or pyannote_pipeline is None:
        return {"error": "Models are still loading"}, 503

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
        tmp.write(await file.read())
        audio_path = tmp.name

    # 1. Whisper transcription
    transcription_result = whisper_model.transcribe(audio_path, fp16=True)
    transcript_text = transcription_result['text']

    # 2. PyAnnote speaker diarization
    diarization = pyannote_pipeline(audio_path)
    speaker_segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        speaker_segments.append({
            "start": turn.start,
            "end": turn.end,
            "speaker": speaker
        })

    # Combine results
    result = {
        "transcript": transcript_text,
        "speakers": speaker_segments
    }

    return result
