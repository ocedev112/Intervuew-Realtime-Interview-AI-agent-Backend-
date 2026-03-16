#!/bin/bash
set -e

PROJECT_ID="gen-lang-client-0618891297"
IMAGE="gcr.io/$PROJECT_ID/interview-agent"
REGION="us-central1"
SERVICE="interview-agent"
SQL_INSTANCE="$PROJECT_ID:$REGION:interview-db"

echo "Building and pushing image..."
gcloud builds submit --tag $IMAGE .

echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE \
  --image $IMAGE \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --min-instances 1 \
  --timeout 3600 \
  --add-cloudsql-instances $SQL_INSTANCE \
  --set-secrets="DATABASE_URL=DATABASE_URL:latest,QDRANT_URL=QDRANT_URL:latest,QDRANT_API_KEY=QDRANT_API_KEY:latest,GOOGLE_API_KEY=GOOGLE_API_KEY:latest,GOOGLE_GENAI_USE_VERTEXAI=GOOGLE_GENAI_USE_VERTEXAI:latest,ALLOWED_ORIGIN=ALLOWED_ORIGIN:latest,SENTENCE_TRANSFORMERS_HOME=SENTENCE_TRANSFORMERS_HOME:latest,ENVIRONMENT=ENVIRONMENT:latest"

echo "Deployment complete!"
gcloud run services describe $SERVICE --region $REGION --format="value(status.url)"