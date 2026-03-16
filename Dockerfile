FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libxml2-dev libxslt-dev gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV SENTENCE_TRANSFORMERS_HOME=/app/model_cache
ENV HF_HOME=/app/model_cache
ENV HF_HUB_OFFLINE=0

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2', cache_folder='/app/model_cache')"

RUN python -c "import os; [print(os.path.join(r,f)) for r,d,files in os.walk('/app/model_cache') for f in files]"

ENV HF_HUB_OFFLINE=1
ENV MODEL_CACHE_PATH=all-MiniLM-L6-v2

COPY interview_agent/ ./interview_agent/

EXPOSE 8080
CMD ["uvicorn", "interview_agent.api.app:app", "--host", "0.0.0.0", "--port", "8080"]


