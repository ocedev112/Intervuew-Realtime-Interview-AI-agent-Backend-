# Intervuew — AI-Powered Real-Time Interview Platform

Intervuew is a full-stack AI interview platform that conducts live, voice-based technical interviews using Google's Gemini Live API. It supports two user types: **organizations** that create job roles and evaluate candidates, and **applicants** who practice or sit for real interviews with an AI interviewer that speaks, listens, and responds in real time.

**Live Demo:** [https://intervuew-front-end-gcvl.vercel.app](https://intervuew-front-end-gcvl.vercel.app)  
**Demo Video:** [https://www.youtube.com/watch?v=THTdrildrVc](https://www.youtube.com/watch?v=THTdrildrVc)  
**Backend API:** [https://interview-agent-435239562393.us-central1.run.app/docs](https://interview-agent-435239562393.us-central1.run.app/docs)

---

## Features

- **Live AI Interview** — Real-time voice interview powered by Gemini 2.5 Flash Native Audio. The AI asks questions, listens to answers, follows up intelligently, and adapts to the candidate's responses.
- **Resume-Based Questions** — Applicants upload their CV and the system generates personalised questions tailored to their experience and the job requirements.
- **RAG-Powered Question Bank** — Interview questions are enriched using a vector database (Qdrant) seeded from a curated bank of software engineering interview content.
- **AI Proctoring** — Video frames are captured during the interview and analysed by Gemini for suspicious behaviour such as reading from notes or receiving external assistance.
- **Automated Scoring** — After the interview ends, the full transcript is evaluated by an AI agent and a score is recorded automatically.
- **Organisation Dashboard** — Organisations can create job roles, manage applicants, view candidate scores, and toggle interview availability.
- **Applicant Dashboard** — Applicants can view applied roles, track prep sessions, and review scores from completed interviews.
- **Prep Mode** — Users can create private practice interviews for any role without needing an organisation account.

---

## Architecture

```
Frontend (React + Vite)          Backend (FastAPI on Cloud Run)
Vercel                           Google Cloud Run
      │                                    │
      │ HTTPS REST API                     │
      ├──────────────────────────────────► │
      │                                    ├── Google ADK Agents
      │ WSS WebSocket (audio/video)        ├── Gemini 2.5 Flash Live API
      ├──────────────────────────────────► │
      │                                    ├── Cloud SQL (PostgreSQL)
      │                                    ├── Qdrant Cloud (Vector DB)
      │                                    └── Google Secret Manager
```

**Tech Stack:**

| Layer         | Technology                                |
| ------------- | ----------------------------------------- |
| Frontend      | React, TypeScript, Vite, MUI              |
| Backend       | FastAPI, Python 3.12                      |
| AI            | Google ADK, Gemini 2.5 Flash, Gemini Live |
| Vector DB     | Qdrant Cloud                              |
| Relational DB | PostgreSQL (Cloud SQL)                    |
| Embeddings    | sentence-transformers (all-MiniLM-L6-v2)  |
| Deployment    | Google Cloud Run, Vercel                  |
| Secrets       | Google Secret Manager                     |
| Container     | Docker                                    |

---

## Testing the Product (Evaluator Guide)

Follow these steps in order to experience the full interview flow.

### Step 1 — Create an Organisation Account

1. Go to [https://intervuew-front-end-gcvl.vercel.app](https://intervuew-front-end-gcvl.vercel.app)
2. Select **Organisation** and click **Create Account**
3. Enter a company name, email, and password
4. You will be redirected to the Organisation Dashboard

### Step 2 — Create a Job Role

1. From the Organisation Dashboard, click the **Job Roles** tab in the sidebar
2. Click **Create Role**
3. Fill in the role title (e.g. "Frontend Engineer"), description, required languages, domains, and soft skills
4. Set a start date, end date, and interview duration (10 minutes recommended)
5. Click **Create** — the system will generate interview questions using the AI agent and vector database. This may take 15–30 seconds.
6. Once created, open the role and **copy the interview link** shown on the role detail page

### Step 3 — Register as an Applicant

1. **Open a new browser or incognito window** (so you are not logged in as the organisation)
2. Go to the copied interview link
3. You will be prompted to create an applicant account — enter your name, email, and password
4. Upload a CV/resume in PDF format
5. The system will generate personalised questions based on your resume
6. You will see a confirmation that you have been registered for the interview

### Step 4 — Start the Interview

1. Log in as the applicant at [https://intervuew-front-end-gcvl.vercel.app/login](https://intervuew-front-end-gcvl.vercel.app/login)
2. Go to your **Dashboard**
3. Under **Applied Roles**, you will see the job role you registered for
4. Click on it — you will be asked to allow microphone and camera access. **Allow both.**
5. Click **Start Interview**
6. The AI interviewer will greet you and begin asking questions in real time
7. Speak your answers naturally — the AI listens, transcribes, and responds
8. The interview ends automatically when all questions are asked or the time limit is reached

### Step 5 — View Results (Organisation)

1. Log back in as the Organisation account
2. Go to **Candidates** in the sidebar
3. You will see the applicant listed with their score once the AI has finished evaluating the transcript
4. Click on the candidate to view their full report and proctoring analysis

---

## Running Locally

### Prerequisites

- Python 3.12
- Node.js 18+
- A Google AI Studio API key ([aistudio.google.com](https://aistudio.google.com))
- A Qdrant Cloud cluster ([cloud.qdrant.io](https://cloud.qdrant.io))

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/ocedev112/Real-time-interview-Agent
cd Real-time-interview-Agent

# Create and activate virtual environment
py -3.12 -m venv .venv312
.venv312\Scripts\activate   # Windows
source .venv312/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Fill in your values (see Environment Variables section below)

# Seed the vector database (run once)
python interview_agent/Interview_information/RAG.py

# Start the API
uvicorn interview_agent.api.app:app --reload
```

The API will be available at `http://localhost:8000` and the Swagger docs at `http://localhost:8000/docs`.

### Frontend Setup

```bash
# Navigate to the frontend repo
git clone https://github.com/ocedev112/Intervuew-Front-end---
cd Intervuew-Front-end---/Intervuew

# Install dependencies
npm install

# Create .env file
echo "VITE_BACKEND_API_ENDPOINT=http://localhost:8000" > .env

# Start the dev server
npm run dev
```

### Environment Variables

Create a `.env` file in the backend root with the following:

```env
GOOGLE_API_KEY=your-gemini-api-key
GOOGLE_GENAI_USE_VERTEXAI=false
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your-qdrant-api-key
DATABASE_URL=sqlite:///orm.db         # SQLite for local dev
ALLOWED_ORIGIN=http://localhost:5173,http://localhost:5174
ENVIRONMENT=development
SENTENCE_TRANSFORMERS_HOME=./model_cache
```

---

## Deployment

The project is deployed using Docker and Google Cloud Run. A single script automates the full build and deploy pipeline:

```bash
bash deploy.sh
```

This script:

1. Builds the Docker image using `gcloud builds submit`
2. Pushes the image to Google Container Registry
3. Deploys the new revision to Cloud Run with all secrets and configuration

See `Dockerfile` and `deploy.sh` in the repository root for the infrastructure-as-code implementation.

---

## API Reference

Full interactive API documentation is available at:  
[https://interview-agent-435239562393.us-central1.run.app/docs](https://interview-agent-435239562393.us-central1.run.app/docs)

Key endpoints:

| Method | Endpoint                                                          | Description                      |
| ------ | ----------------------------------------------------------------- | -------------------------------- |
| POST   | `/User/create`                                                    | Register a new applicant         |
| POST   | `/User/login`                                                     | Log in as applicant              |
| POST   | `/Organization/create`                                            | Register a new organisation      |
| POST   | `/Organization/login`                                             | Log in as organisation           |
| POST   | `/Interview/create`                                               | Create a new interview (org)     |
| POST   | `/Applicant/create/`                                              | Register applicant for interview |
| GET    | `/Interview/full/{id}`                                            | Get interview details            |
| GET    | `/User/{id}/applicant/interviews`                                 | Get applicant's interviews       |
| WS     | `/interview/start/{interview_id}/{applicant_id}`                  | Live audio interview WebSocket   |
| WS     | `/interview/visual_interview/start/{interview_id}/{applicant_id}` | Live video proctoring WebSocket  |

---

## Repository Structure

```
Real-time-interview-Agent/
├── interview_agent/
│   ├── api/
│   │   └── app.py              # FastAPI application and all endpoints
│   ├── database/
│   │   ├── db.py               # Database connection
│   │   ├── models.py           # SQLAlchemy models
│   │   └── process.py          # Database operations
│   ├── Interview_information/
│   │   ├── RAG.py              # Web scraping and vector DB seeding
│   │   └── vectorCollection.py # Qdrant client and embedding logic
│   └── agent.py                # Google ADK agents (question, resume, evaluator)
├── Dockerfile                  # Container definition
├── deploy.sh                   # Automated deployment script
├── requirements.txt            # Python dependencies
└── .dockerignore
```

---

## Notes for Evaluators

- The AI interview uses **Gemini 2.5 Flash Native Audio** which requires microphone access. Please allow it when prompted.
- Interview duration is set to **10 minutes** for testing purposes.
- The AI proctoring analysis runs asynchronously after the interview ends — scores and reports may take 1–2 minutes to appear in the organisation dashboard.
- The first cold start after inactivity may take up to 30 seconds as the Cloud Run instance warms up.
