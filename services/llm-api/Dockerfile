FROM docker.io/ollama/ollama:latest AS ollama

FROM nvidia/cuda:12.4.0-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ollama /usr/bin/ollama /usr/bin/ollama
COPY --from=ollama /usr/lib/ollama/ /usr/lib/ollama/

# Environment variable setup
ENV OLLAMA_HOST=0.0.0.0

# Never unload model weights from the GPU.
ENV OLLAMA_KEEP_ALIVE=-1

# Store model weight files in /models
ENV OLLAMA_MODELS=/models

# Reduce log verbosity.
ENV OLLAMA_DEBUG=false

ENV MODEL=gemma3:4b

# Expose port for the service
EXPOSE 11434

RUN ollama serve & sleep 5 && ollama pull $MODEL

ENTRYPOINT ["ollama", "serve"]
