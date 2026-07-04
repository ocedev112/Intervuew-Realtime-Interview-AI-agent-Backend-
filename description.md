Intervuew is a full-stack AI interview platform that conducts live, voice-based technical interviews using Google's Gemini Live API. It supports two user types: **organizations** that create job roles and evaluate candidates, and **applicants** who practice or sit for real interviews with an AI interviewer that speaks, listens, and responds in real time.

## Features

- **Live AI Interview** — Real-time voice interview powered by Gemini 2.5 Flash Native Audio. The AI asks questions, listens to answers, follows up intelligently, and adapts to the candidate's responses.
- **Resume-Based Questions** — Applicants upload their CV and the system generates personalised questions tailored to their experience and the job requirements.
- **RAG-Powered Question Bank** — Interview questions are enriched using a vector database (Qdrant) seeded from a curated bank of software engineering interview content.
- **AI Proctoring** — Video frames are captured during the interview and analysed by Gemini for suspicious behaviour such as reading from notes or receiving external assistance.
- **Automated Scoring** — After the interview ends, the full transcript is evaluated by an AI agent and a score is recorded automatically.
- **Organisation Dashboard** — Organisations can create job roles, manage applicants, view candidate scores, and toggle interview availability.
- **Applicant Dashboard** — Applicants can view applied roles, track prep sessions, and review scores from completed interviews.
- **Prep Mode** — Users can create private practice interviews for any role without needing an organisation account.
