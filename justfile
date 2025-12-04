set dotenv-load := true
set dotenv-path := "./services/.secret.local"

default:
  just --list

functions:
    export FIREBASE_AUTH_EMULATOR_HOST="127.0.0.1:9099" && firebase emulators:start

embeddings-api:
    export PROJECT_ID=mason-b4c0a && \
    export REPOSITORY=docker-repo && \
    export SERVICE_NAME=embeddings-api && \
    export IMAGE_URL=us-central1-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$SERVICE_NAME && \
    docker run -p 11434:11434 $IMAGE_URL

vector-db:
    export PROJECT_ID=mason-b4c0a && \
    export REPOSITORY=docker-repo && \
    export SERVICE_NAME=vector-db && \
    export IMAGE_URL=us-central1-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$SERVICE_NAME && \
    docker run -p 6333:6333 $IMAGE_URL

deploy-transcribe-api:
    export PROJECT_ID=mason-b4c0a && \
    export REPOSITORY=docker-repo && \
    export SERVICE_NAME=transcribe-api && \
    export IMAGE_URL=us-central1-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$SERVICE_NAME && \
    gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_URL \
    --project $PROJECT_ID \
    --region us-central1 \
    --gpu 1 \
    --gpu-type nvidia-l4 \
    --no-gpu-zonal-redundancy \
    --concurrency 1 \
    --cpu 4 \
    --set-env-vars OLLAMA_NUM_PARALLEL=1 \
    --max-instances 3 \
    --memory 16Gi \
    --no-cpu-throttling \
    --allow-unauthenticated \
    --port 8080 \
    --timeout=600 \
    --set-env-vars HUGGINGFACE_TOKEN=$HUGGINGFACE_TOKEN

deploy-llm-api:
    export PROJECT_ID=mason-b4c0a && \
    export REPOSITORY=docker-repo && \
    export SERVICE_NAME=llm-api && \
    export IMAGE_URL=us-central1-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$SERVICE_NAME && \
    gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_URL \
    --project $PROJECT_ID \
    --region us-central1 \
    --gpu 1 \
    --gpu-type nvidia-l4 \
    --no-gpu-zonal-redundancy \
    --concurrency 1 \
    --cpu 4 \
    --set-env-vars OLLAMA_NUM_PARALLEL=1 \
    --max-instances 3 \
    --memory 16Gi \
    --no-cpu-throttling \
    --allow-unauthenticated \
    --port 11434 \
    --timeout=600

serve-all:
    tmux kill-session -t dev_session 2>/dev/null || true
    tmux new-session -d -s dev_session "just functions"
    tmux split-window -v -t dev_session "just embeddings-api"
    tmux split-window -v -t dev_session "just vector-db"
    tmux select-layout -t dev_session tiled
    tmux attach-session -t dev_session
