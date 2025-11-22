FROM docker.io/ollama/ollama:latest AS ollama

FROM cgr.dev/chainguard/wolfi-base

RUN apk add --no-cache libstdc++

COPY --from=ollama /usr/bin/ollama /usr/bin/ollama
COPY --from=ollama /usr/lib/ollama/libggml-cpu-* /usr/lib/ollama/
COPY --from=ollama /usr/lib/ollama/libggml-base.so /usr/lib/ollama/libggml-base.so

# Environment variable setup
ENV OLLAMA_HOST 0.0.0.0

# Never unload model weights from the GPU.
ENV OLLAMA_KEEP_ALIVE -1

# Store model weight files in /models
ENV OLLAMA_MODELS /models

# Reduce log verbosity.
ENV OLLAMA_DEBUG false

ENV MODEL gpt-oss:20b

# Expose port for the service
EXPOSE 11434

RUN ollama serve & sleep 5 && ollama pull $MODEL

ENTRYPOINT ["ollama", "serve"]
