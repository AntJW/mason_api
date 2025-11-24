## Local Development

### Firebase Emulator 
<!-- Specifying FIREBASE_AUTH_EMULATOR_HOST enables this api to connect to the flutter app repo's auth emulator. -->
export FIREBASE_AUTH_EMULATOR_HOST="127.0.0.1:9099" && firebase emulators:start

Note: Use `.env.local` and `.secret.local` to define environment variables and secrets for local development. Those local files are automatically used when calling `firebase emulators:start`.

#### REST Client
[REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) allows you to send HTTP request and view the response in Visual Studio Code directly. This is great for testing api endpoints/functions without having to go through a UI. Start by downloading the REST Client Visual Code plugin. Then create a `test.http` (or any file name with extention .http), and start sending requests. 

Example test.http: 

```bash
GET http://127.0.0.1:5001/mason-b4c0a/us-central1/api/hello-world
content-type: application/json

{}
```

## Services

### Ollama API

The in app AI chat assistent utilizes an open source model served via [Ollama](https://ollama.com/). The model is deployed to Cloud Run, and accessible from the app via a simple URL. The service configuration is located in [deployment/ollama-cf.Dockerfile](./deployment/ollama-cf.Dockerfile). 

Reference Guide: [GPU support for services](https://cloud.google.com/run/docs/configuring/services/gpu).


```bash
# Build Docker container first

PROJECT_ID=mason-b4c0a
REPOSITORY=docker-repo
SERVICE_NAME=ollama-api
IMAGE_URL=us-central1-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$SERVICE_NAME

cd services/$SERVICE_NAME

gcloud builds submit --tag $IMAGE_URL --machine-type e2-highcpu-32 --project $PROJECT_ID

# Deploy to Cloud Run

gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_URL \
    -- project $PROJECT_ID \
    --region us-central1 \
    --gpu 1 \
    --gpu-type nvidia-l4 \
    --no-gpu-zonal-redundancy \
    --concurrency 1 \
    --cpu 8 \
    --set-env-vars OLLAMA_NUM_PARALLEL=1 \
    --max-instances 3 \
    --memory 32Gi \
    --no-cpu-throttling \
    --allow-unauthenticated \
    --port 11434 \
    --timeout=600

# TODO: Remove --allow-unauthenticated once auth is updated and ready for production. 
```
```bash
# Example requests

CR_SERVICE_URL=https://ollama-cr-806142703984.us-central1.run.app

curl $CR_SERVICE_URL/api/generate \
  -d '{
    "model": "gemma3:4b",
    "prompt": "Why is the sky blue?"
  }'


curl $CR_SERVICE_URL/api/chat \
  -d '{
    "model": "gemma3:4b",
    "messages": [{
      "role": "user",
      "content": "Why is the sky blue?"
    }],
    "stream": true
  }'
```

### Transcribe API

```bash
# Build Docker container first

export PROJECT_ID=mason-b4c0a &&
export REPOSITORY=docker-repo &&
export SERVICE_NAME=transcribe-api &&
export IMAGE_URL=us-central1-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$SERVICE_NAME

cd services/$SERVICE_NAME

gcloud builds submit --tag $IMAGE_URL --machine-type e2-highcpu-32 --project $PROJECT_ID

gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_URL \
    --project $PROJECT_ID \
    --region us-central1 \
    --gpu 1 \
    --gpu-type nvidia-l4 \
    --no-gpu-zonal-redundancy \
    --concurrency 1 \
    --cpu 8 \
    --set-env-vars OLLAMA_NUM_PARALLEL=1 \
    --max-instances 3 \
    --memory 32Gi \
    --no-cpu-throttling \
    --allow-unauthenticated \
    --port 8080 \
    --timeout=600
```

```bash
curl -X POST \
  -F "file=@//Users/anthonywhite/Downloads/interview-hazel.m4a" \
  https://api.example.com/transcribe
```