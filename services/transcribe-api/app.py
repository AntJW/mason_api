# app.py
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import whisper
from pyannote.audio import Pipeline
import tempfile
import json
import torch
import os

# Global variables for models
whisper_model = None
pyannote_pipeline = None
models_loading = False
models_loaded = False


async def load_models_background():
    """Load models in the background after server starts"""
    global whisper_model, pyannote_pipeline, models_loading, models_loaded
    models_loading = True
    try:
        print("Loading Whisper model...")
        whisper_model = whisper.load_model(
            "turbo", device="cuda")  # GPU by default

        print("Loading PyAnnote pipeline...")
        # Model is pre-cached in Docker image, token not needed at runtime
        pyannote_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-community-1")

        # send pipeline to GPU (when available)
        pyannote_pipeline.to(torch.device("cuda"))
        print("Models loaded successfully!")
        models_loaded = True
    except Exception as e:
        print(f"Error loading models: {e}")
    finally:
        models_loading = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Start server immediately, load models in background
    asyncio.create_task(load_models_background())

    yield  # App runs here (server starts listening immediately)

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
        "models_loaded": models_loaded,
        "models_loading": models_loading
    }


@app.post("/transcribe")
async def transcribe_audio(file: UploadFile):
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
            tmp.write(await file.read())
            audio_path = tmp.name

        # 1. Whisper transcription
        transcription_result = whisper_model.transcribe(audio_path, fp16=True)

        # 2. PyAnnote speaker diarization
        diarization = pyannote_pipeline(audio_path)
        speaker_segments = []
        # Access annotation attribute for newer pyannote.audio API
        for turn, speaker in diarization.speaker_diarization:
            speaker_segments.append({
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker
            })

        # Combine results
        result = {
            "transcript": transcription_result,
            "speakers": speaker_segments
        }

        return result
    except Exception as e:
        return {"error": str(e)}, 500
