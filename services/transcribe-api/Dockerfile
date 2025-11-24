FROM nvidia/cuda:13.0.2-cudnn-devel-ubuntu24.04

# Install system deps including FFmpeg and all required libraries
RUN apt-get update && apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswresample-dev \
    libswscale-dev \
    git curl wget \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Create and activate virtual environment
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Copy Python files
COPY app.py requirements.txt ./

# Install Python deps
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Run FastAPI - use PORT env var with 8080 as fallback
CMD python3 -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}
