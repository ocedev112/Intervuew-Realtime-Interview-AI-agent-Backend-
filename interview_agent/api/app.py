#api

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bcrypt
import base64
import asyncio
import shutil
import json
import re
analysis_queue = asyncio.Queue()
from google.adk.runners import Runner, InMemoryRunner
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.sessions import InMemorySessionService
from google.genai import types
from google.genai.types import Content, Part,  FunctionCallingConfig, Modality
from google.adk.agents.llm_agent import Agent
from google.adk.apps.app import App
from google.adk.tools import FunctionTool
from google.adk.apps.app import EventsCompactionConfig
from fastapi import FastAPI, Depends, UploadFile, File, WebSocket, HTTPException, Form, Response, Request
from fastapi.websockets import WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import pymupdf
from pydantic import BaseModel, field_validator, ValidationError
from typing import Optional

from database.process import create_UserDB,create_InterviewDB, create_organizationDB, jobRequirements, convert_requirements_tostr
from database.process import get_interview_questions, create_ApplicantDB, get_applicant_questions, get_interview_timer, fetch_applicantId_interview
from database.process import fetch_interview, fetch_applicant, fetch_details_organization, record_score, record_proctoring_report
from database.process import start_interview_for_applicant, fetch_all_candidates_organization, fetch_candidate_detail, toggle_interview_status, fetch_prep_interviews, fetch_interview_report
from database.process import get_applicant_start_session, close_session_applicant
from database.db import sessionLocal
from database.models import  Organization, User, InterviewType, Interview

from interview_agent.agent import question_agent, resume_agent, evaluator_agent
from google.adk.agents.context_cache_config import ContextCacheConfig
from datetime import datetime
from google import genai
import base64

client = genai.Client(
   api_key=os.environ["GOOGLE_API_KEY"]
)




class UserRequest(BaseModel):
    name: str
    email: str
    password: str


class UserLoginRequest(BaseModel):
    email: str
    password: str


class OrganizationRequest(BaseModel):
    name: str
    email: str
    password: str

class OrganizationLoginRequest(BaseModel):
    email: str
    password: str

class InterviewRequest(BaseModel):
    role: str
    description: str
    job_requirements: jobRequirements
    start_date: datetime
    end_date: datetime
    duration: int
    organization_id: Optional[str] = None
    user_id: Optional[str] = None

    @field_validator('duration')
    @classmethod
    def validate_duration(cls, v: int) -> int:
        if not 10 <= v <= 40:
            raise ValueError('Duration must be between 10 and 40 minutes')
        return v

    @field_validator('end_date')
    @classmethod
    def validate_dates(cls, v: datetime, info) -> datetime:
        start_date = info.data.get('start_date')
        if start_date and isinstance(start_date, datetime) and v <= start_date:
            raise ValueError('End date must be after start date')
        return v



class ApplicantRequest(BaseModel):
    name: str
    user_id: str



app =FastAPI()
session_service = InMemorySessionService()

active_sessions = set()
active_vision_sessions = set()


async def create_interview_base_questions(message: str, duration: int):
    runner = Runner(agent=question_agent, app_name="interview", session_service=session_service)
    prompt = f"""
       With this interview duration: {duration} minutes.
         Generate questions using job_requirements: {message}
    """
    session = await session_service.create_session(app_name="interview", user_id="create_base_question")
    for event in runner.run(
        user_id="create_base_question",
        session_id=session.id,
        new_message=Content(parts=[Part(text=prompt)]),
        run_config=RunConfig(
            streaming_mode= StreamingMode.NONE,
            max_llm_calls=3
        )

    ):
        if event.is_final_response():
            return event.content.parts[0].text

async def create_interview_full_questions(message: str, duration: int):
    runner = Runner(agent=resume_agent, app_name="interview", session_service=session_service)
    prompt = f"""
      Generate questions using  this resume: {message} with this number of minutes {duration}
    """
    session = await session_service.create_session(app_name="interview", user_id="full_question")
  
    for event in runner.run(
        user_id="full_question",
        session_id=session.id,
        new_message=Content(parts=[Part(text=prompt)]),
        run_config=RunConfig(
            streaming_mode= StreamingMode.NONE,
            max_llm_calls=2
        )

    ):
       
        if event.is_final_response():
            return event.content.parts[0].text



app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)  

@app.post("/User/create")
async def create_user(request: UserRequest, response: Response):
  try:
    hashed = bcrypt.hashpw(request.password.encode('utf-8'),  bcrypt.gensalt())
    hashed_password_string = hashed.decode('utf-8')
    user = create_UserDB(request.name, request.email, hashed_password_string)
    response.set_cookie(
        key="org_id",
        value=str(user.id),
        httponly=True,
        secure=False,  
        samesite="lax",
        max_age=60*60*24*7  
    )
    return {"status": "ok", "id": user.id}
  except Exception as e:
      print(e)
      raise HTTPException(status_code=500, detail=str(e))


@app.get("/User")
async def get_username(request: Request):
   db= sessionLocal()
   try:
       user_id = request.cookies.get("user_id")
       if not user_id:
          raise HTTPException(status_code=401, detail="Not authenticated")
       user = db.query(User).filter(User.id == user_id).first()
       return {"name": user.name}
   except Exception as e:
       print(e)
       raise HTTPException(status_code=500,detail=str(e))
   finally:
       db.close()

@app.get("/User/{user_id}/applicant/interviews")
async def get_user_applicant(user_id: str):
   try:
       results  = fetch_applicantId_interview(user_id)
       return results
   except Exception as e:
      print(e)
      raise HTTPException(status_code=500, detail=str(e))
   

@app.get("/User/{user_id}/prep/interviews")
async def get_prep_interviews(user_id: str):
    try:
        results = fetch_prep_interviews(user_id)
        return results
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/User/login")
async def login_user(request: UserLoginRequest, response: Response):
    db = sessionLocal()
    try:
        
        user = db.query(User).filter(User.email == request.email).first()
        
        if user is not None:
            check_password = bcrypt.checkpw(request.password.encode('utf-8'), user.password.encode('utf-8'))
            if not user or not check_password:
                raise HTTPException(status_code=401, detail="Invalid credentials")            
            if check_password:
                response.set_cookie(
                    key="user_id",
                    value=user.id,
                    httponly=True,
                    secure=False,  
                    samesite="lax",
                    max_age=60*60*24*7  
                )
                return {"status": "ok", "id": str(user.id)}
            
        raise HTTPException(status_code=401, detail="Invalid credentials")
    except HTTPException:
        raise
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/User/report/{interview_id}")
async def get_interview_report(interview_id: str, request: Request):
    try:
        # get user_id from session/cookie same way your other user endpoints do
        user_id = request.cookies.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        result = fetch_interview_report(interview_id, user_id)
        if not result:
            raise HTTPException(status_code=404, detail="Report not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/User/me")
async def get_me(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    db = sessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"id": user.id, "name": user.name, "email": user.email}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/Organization")
async def get_username(request: Request):
   db= sessionLocal()
   try:
       org_id = request.cookies.get("org_id")
       if not org_id:
          raise HTTPException(status_code=401, detail="Not authenticated")
       org = db.query(Organization).filter(Organization.id == org_id).first()
       return {"name": org.name}
   except Exception as e:
       print(e)
       raise HTTPException(status_code=500,detail=str(e))
   finally:
       db.close()


@app.get("/Organization/me")
async def get_org_me(request: Request):
    org_id = request.cookies.get("org_id")
    if not org_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    db = sessionLocal()
    try:
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        return {"id": str(org.id), "name": org.name, "email": org.email}
    finally:
        db.close()


@app.post("/Organization/create") 
async def create_organization(request: OrganizationRequest, response: Response):
  try:
    hashed = bcrypt.hashpw(request.password.encode('utf-8'),  bcrypt.gensalt())
    hashed_password_string = hashed.decode('utf-8')
    org = create_organizationDB(request.name, request.email, hashed_password_string)
    response.set_cookie(
        key="user_id",
        value=org.id,
        httponly=True,
        secure=False,  
        samesite="lax",
        max_age=60*60*24*7  
    )
    return {"status": "ok", "id" : org.id}
  except Exception as e:
      print(e)
      raise HTTPException(status_code=500, detail=str(e))
  

@app.get("/Organization/interview/candidate/report/{org_id}")
async def get_interview_details(org_id: str):
    try:
         response  = fetch_details_organization(org_id)
         return response
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/Organization/candidates/{org_id}")
async def get_all_candidates(org_id: str):
    try:
        response = fetch_all_candidates_organization(org_id)
        return response
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/Organization/candidates/detail/{applicant_id}")
async def get_candidate_detail(applicant_id: str):
    try:
        result = fetch_candidate_detail(applicant_id)
        if not result:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
    
@app.patch("/Organization/interview/{interview_id}/status")
async def toggle_interview_status_route(interview_id: str, action: str):
    try:
        result = toggle_interview_status(interview_id, action)
        if not result:
            raise HTTPException(status_code=404, detail="Interview not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/Organization/login")
async def login_Orgainization(request: OrganizationLoginRequest, response: Response):
    db = sessionLocal()
    try:
        org = db.query(Organization).filter(Organization.email == request.email).first()
        if org  is not None:
            checkpassword = bcrypt.checkpw(request.password.encode('utf-8'), org.password.encode('utf-8') ) 
            if checkpassword:
                response.set_cookie(
                    key="org_id",
                    value=org.id,
                    httponly=True,
                    secure=False,  
                    samesite="lax",
                    max_age=60*60*24*7  
                )
                
                return {"status": "ok", "id": org.id}
        raise HTTPException(status_code=401, detail="Invalid credentials")
    except HTTPException:
        raise
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
    


@app.post("/Interview/create")
async def create_interview(request: InterviewRequest):
    try:
        print(f"Received request: {request.model_dump()}")
      
        stringJobRequirements = convert_requirements_tostr(request.job_requirements)
        
       
        base_question = await create_interview_base_questions(
            stringJobRequirements, 
            request.duration
        )
        print(f"3. base questions: {base_question}")
        
        #This is a hard-coded duration because of api limits  for free-tier and session_resumption issue, will upgrade later
        request.duration = 10
      
        if request.organization_id is not None:
            interview_type = InterviewType.organization
            interview_id = create_InterviewDB(
                request.role, 
                interview_type,
                request.description, 
                request.job_requirements, 
                request.start_date, 
                request.end_date, 
                request.duration, 
                base_question, 
                organization_id=request.organization_id,
                user_id=None
            )
        else: 
            interview_type = InterviewType.user
            interview = create_InterviewDB(
                request.role, 
                interview_type,
                request.description, 
                request.job_requirements, 
                request.start_date, 
                request.end_date, 
                request.duration, 
                base_question, 
                organization_id=None,
                user_id=request.user_id
            )

            interview_id = interview.id
        
        return {
            "status": "ok",
            "interview_id": interview_id,
            "type": interview_type.value  
        }
    except ValidationError as e:
        print(f"Validation error: {e}")
        raise
    except HTTPException:
        raise  
    except Exception as e:
        print(f"Error creating interview: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    



@app.get("/Interview/{interview_id}")
async def get_interview(interview_id: str):
   try:
      interview = fetch_interview(interview_id)
      return interview
   except Exception as e:
      print(e)
      raise HTTPException(status_code=500, detail=str(e))


@app.get("/Interview/full/{interview_id}")
async def get_interview_public(interview_id: str):
    try:
        db = sessionLocal()
        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            raise HTTPException(status_code=404, detail="Interview not found")
        return {
            "role": interview.role,
            "type": interview.type,
            "description": interview.description,
            "start_date": interview.start_date.isoformat(),
            "end_date": interview.end_date.isoformat(),
            "duration": interview.duration,
            "job_requirements": interview.job_requirements,
            "status": interview.status,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


   
@app.get("/Applicant/{applicant_id}")
async def get_applicant(applicant_id: str):
    try:
        applicant = fetch_applicant(applicant_id)
        if not applicant:
            raise HTTPException(status_code=404, detail="Applicant not found")
        return applicant
    except HTTPException:
        raise
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
   
@app.post("/Applicant/create/")
async def sign_up_for_interview(request: Request, interview_id: str, applicant: str = Form(...),  file: UploadFile = File(...)):
  try: 
    applicant_data = json.loads(applicant)
    applicant_req = ApplicantRequest(**applicant_data)
    pdf_bytes = await file.read()

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

    resume = " ".join(page.get_text() for page in doc)
    base_questions, duration = get_interview_questions(interview_id)
    domain_questions =  await create_interview_full_questions(resume, duration)
    full_question = domain_questions + base_questions
    create_ApplicantDB(applicant_req.name, pdf_bytes, full_question, interview_id, applicant_req.user_id)
    return {"status": "ok"}
  except Exception as e:
     print(e)
     raise HTTPException(status_code=500, detail=str(e))

@app.post("/Prepper/create/{interview_id}/{applicant_id}")
async def create_prepper(
    interview_id: str, 
    applicant_id: str,
    name: str = Form(...),
    request: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        interview_request = InterviewRequest(**json.loads(request))

        # --- Create Interview ---
        stringJobRequirements = convert_requirements_tostr(interview_request.job_requirements)
        base_questions = await create_interview_base_questions(stringJobRequirements, interview_request.duration)

        interview_request.duration = 10  # hard-coded due to api limits

        if interview_request.organization_id is not None:
            interview_type = InterviewType.organization
            new_interview = create_InterviewDB(
                interview_request.role,
                interview_type,
                interview_request.description,
                interview_request.job_requirements,
                interview_request.start_date,
                interview_request.end_date,
                interview_request.duration,
                base_questions,
                organization_id=interview_request.organization_id,
                user_id=None
            )
        else:
            interview_type = InterviewType.user
            new_interview = create_InterviewDB(
                interview_request.role,
                interview_type,
                interview_request.description,
                interview_request.job_requirements,
                interview_request.start_date,
                interview_request.end_date,
                interview_request.duration,
                base_questions,
                organization_id=None,
                user_id=applicant_id
            )

        # --- Create Applicant ---
        pdf_bytes = await file.read()
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        resume = " ".join(page.get_text() for page in doc)

        domain_questions = await create_interview_full_questions(resume, interview_request.duration)
        full_questions = domain_questions + base_questions

        create_ApplicantDB(name, pdf_bytes, full_questions, new_interview.id, applicant_id)

        return {
            "status": "ok",
            "interview_id": new_interview.id,
            "applicant_id": applicant_id,
            "type": interview_type.value
        }
    except ValidationError as e:
        print(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=e.errors())
    except HTTPException:
        raise
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))




async def evaluate_responses(message: str):
    runner = Runner(agent=evaluator_agent, app_name="evaluator_agent", session_service=session_service)
    prompt = f"""
      this are the interview questions and responses to the questions: {message}. evaluate interview
    """
    session = await session_service.create_session(app_name="evaluator_agent", user_id="evaluate_response")
    for event in runner.run(
        user_id="evaluate_response",
        session_id=session.id,
        new_message=Content(parts=[Part(text=prompt)]),
        run_config=RunConfig(
            streaming_mode= StreamingMode.NONE,
            max_llm_calls=3
        )

    ):
        if event.is_final_response():
            raw = event.content.parts[0].text
            return json.loads(raw)["score"]  


def convert_transcript_to_text(transcription_log: list) -> str:
    lines = []
    for entry in transcription_log:
        role = entry.get("role")  
        text = entry.get("text") 
        
        if role == "candidate":
            lines.append(f"Candidate: {text}")
        elif role == "agent":
            lines.append(f"Interviewer: {text}")
    
    return "\n".join(lines)


async def run_interview(websocket, applicant_id, interview_id, interview_app):
    runner = InMemoryRunner(app=interview_app)

    session = await runner.session_service.create_session(
        app_name="interview_app", user_id=applicant_id
    )
  
    transcript_log = []
    live_request_queue = LiveRequestQueue()
    resumption_handle = None

    start_interview_for_applicant(applicant_id)

    async def receive_audio():
        try:
            header_text = await websocket.receive_text()
            _ = json.loads(header_text)
            while True:
                data = await websocket.receive_bytes()
                live_request_queue.send_realtime(
                    types.Blob(data=data, mime_type="audio/pcm;rate=16000")
                )
        except WebSocketDisconnect:
            live_request_queue.close()
        except Exception as e:
            print(f"receive error: {e}")
            live_request_queue.close()

    async def send_audio():
        nonlocal resumption_handle

        await websocket.send_text(json.dumps({"mime_type": "audio/pcm"}))

        live_request_queue.send_content(
            types.Content(parts=[types.Part(text="Begin the interview.")], role="user")
        )

        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=[Modality.AUDIO],
            max_llm_calls=500,
            save_live_blob=True,
            session_resumption=types.SessionResumptionConfig(
                handle=resumption_handle
            ),
            context_window_compression=types.ContextWindowCompressionConfig(
                trigger_tokens=50000,
                sliding_window=types.SlidingWindow(target_tokens=20000),
            )
        )

        try:
            async for event in runner.run_live(
                session=session,
                live_request_queue=live_request_queue,
                run_config=run_config
            ):


                # save resumption handle
                if event.live_session_resumption_update:
                    update = event.live_session_resumption_update
                    if update.resumable and update.new_handle:
                        resumption_handle = update.new_handle

                # transcription
                if event.input_transcription and event.input_transcription.finished:
                    message = {
                        "role": "candidate",
                        "text": event.input_transcription.text,
                        "timestamp": datetime.now().isoformat()
                    }
                    transcript_log.append(message)
                    print(message)
                    await websocket.send_text(json.dumps(message))

                if event.output_transcription and event.output_transcription.finished:
                    message = {
                        "role": "agent",
                        "text": event.output_transcription.text,
                        "timestamp": datetime.now().isoformat()
                    }
                    transcript_log.append(message)
                    print(message)
                    await websocket.send_text(json.dumps(message))

                # send audio to client
                part = (event.content and event.content.parts and event.content.parts[0])
                if part:
                    is_audio = part.inline_data and part.inline_data.mime_type.startswith("audio/pcm")
                    if is_audio and part.inline_data.data:
                        await websocket.send_bytes(part.inline_data.data)

                # turn complete
                if event.turn_complete or event.interrupted:
                    await websocket.send_text(json.dumps({
                        "turn_complete": event.turn_complete,
                        "interrupted": event.interrupted,
                    }))

        except WebSocketDisconnect:
            pass
        except Exception as e:
            import traceback
            print(f"send_audio error: {e}")
            traceback.print_exc()
        finally:
            try:
                print("evaluating response")
                transcription = convert_transcript_to_text(transcript_log)
                score = await evaluate_responses(transcription)
                record_score(interview_id, applicant_id, score)
            except Exception as e:
                print(e)


    await asyncio.gather(receive_audio(), send_audio(), return_exceptions=True)


@app.websocket("/interview/start/{interview_id}/{applicant_id}")
async def audio_interview(websocket: WebSocket, interview_id: str, applicant_id: str):
    await websocket.accept()

    start_time, end_time, duration, status = get_interview_timer(interview_id)
    started_session = get_applicant_start_session(applicant_id)

    if datetime.now() < start_time:
        await websocket.close(code=1008, reason="Interview has not started")
        return

    if datetime.now() > end_time:
        await websocket.close(code=1008, reason="Interview has ended")
        return
    
    if status != "active":
        await websocket.close(code=1008, reason="Interview status is closed")
        return
    
    if started_session:
        await websocket.close(code=1008, reason="you have started a meeting session before")

    if applicant_id in active_sessions:
        await websocket.close(code=1008, reason="Session already active")
        return



    questions = get_applicant_questions(applicant_id)
    questions = questions.strip()
    question_list = [q.strip() for q in questions.split("\n") if q.strip()][:50]
    formatted = "\n".join(f"{i+1}. {q}" for i, q in enumerate(question_list))




    interview_agent = Agent(
       name="interview_live",
       model="gemini-2.5-flash-native-audio-latest",
       instruction=f"""
        You are a professional Software Engineering interview agent.
        Do NOT output reasoning or internal monologue.
        Respond only with direct spoken answers.
        Ask one question at a time and wait for a response before continuing.
        Start with a greeting then ask question 1.
        Always wait for user to respond before asking the next question, if they haven't responded for a long time. 
        say "i'm still waiting"
        Do NOT answer the user's questions.
        DO NOT ASK the same question twice.
        When ALL questions are asked from each section say "The interview is now complete."
        Questions:
        {formatted}
      """,
    )

    interview_app = App(
        name="interview_app",
        root_agent=interview_agent,
        context_cache_config=ContextCacheConfig(
            min_tokens=2048,
            ttl_seconds=600,
            cache_intervals=5,
        ),
    )

    active_sessions.add(applicant_id)
    try:
        await asyncio.wait_for(
            run_interview(websocket, applicant_id, interview_id, interview_app),
            timeout=duration * 60
        )
    except asyncio.TimeoutError:
        await websocket.send_text(json.dumps({"ended": True, "reason": "time_limit_reached"}))
        await websocket.close()
    finally:
        active_sessions.discard(applicant_id)
        close_session_applicant(applicant_id)

async def analyze_interview(interview_id: str, applicant_id: str):
    print("converting to path")
    frames_dir = f"/tmp/{interview_id}_{applicant_id}_frames"
    if not os.path.exists(frames_dir):
        print(f"No frames found for {interview_id}")
        return

    print("sorting files")
    frame_files = sorted(os.listdir(frames_dir))
    if not frame_files:
        print(f"Empty frames dir for {interview_id}")
        return

    print("uploading frames directly")
    step = max(1, len(frame_files) // 20)  # max 20 frames
    sampled = frame_files[::step][:20]

    contents = []
    for f in sampled:
        with open(f"{frames_dir}/{f}", "rb") as img:
            contents.append(types.Part.from_bytes(
                data=img.read(),
                mime_type="image/jpeg"
            ))
    print(f"prepared {len(contents)} frames")

    contents.append(types.Part(text=(
        "Detect proctoring violations. "
        "JSON only: {\"alerts\": [{\"frame\": int, \"reason\": str}], \"cheating_detected\": bool}"
    )))

    model = "gemini-2.5-flash"
    cache = None

    print("checking token count")
    token_response = await client.aio.models.count_tokens(
        model=model,
        contents=contents
    )
    print(f"token count: {token_response.total_tokens}")

    if token_response.total_tokens >= 32768:
        print("creating cache")
        cache = client.caches.create(
            model=model,
            config=types.CreateCachedContentConfig(
                display_name=f"{interview_id}_proctoring",
                system_instruction="""
               You are analyzing video frames from a live oral interview for proctoring violations.
               Each frame represents one second of footage.

               NORMAL BEHAVIOR — do NOT flag these under any circumstances:
                - Brief glances away from camera while thinking or recalling
                - Natural head movements, blinking, shifting posture
                - Speaking, pausing, or thinking aloud
                - Occasional eye movement in any direction
                - Minor lighting changes or camera angle shifts
                - Looking down, up, or sideways for a few seconds

            FLAG AS A VIOLATION only when ALL of the following are true:
             - The behavior is sustained for at least 40 consecutive seconds
             - The behavior is unambiguous and clearly visible across multiple frames
             - The behavior cannot be explained by normal thinking or speaking

           VIOLATIONS (only when meeting the above threshold):
           - Eyes clearly fixed on an off-screen source for 20+ seconds
           - A second person visibly present and appearing to assist
           - Candidate visibly reading from notes, phone, or screen for 20+ seconds
           - Audible coaching voice from off-camera
           - Candidate leaving the frame entirely for 20+ seconds

          STRICT RULE: If you are not completely certain, set cheating_detected to false.
          A single frame, brief movement, or ambiguous behavior is NEVER sufficient evidence.
          Most interviews will have cheating_detected: false — this is expected and correct.

         Return JSON only: {"alerts": [{"frame": int, "reason": str}], "cheating_detected": bool}.""",
                contents=contents,
                ttl="300s"
            )
        )
        print(f"cache created: {cache.name}")
        generate_config = types.GenerateContentConfig(cached_content=cache.name)
        generate_contents = [types.Part(text=(
            "Detect proctoring violations. "
            "JSON only: {\"alerts\": [{\"frame\": int, \"reason\": str}], \"cheating_detected\": bool}"
        ))]
    else:
        print("token count too low for caching, sending directly")
        generate_config = None
        generate_contents = contents

    print("calling generate_content")
    try:
        response = await client.aio.models.generate_content(
            model=model,
            config=generate_config,
            contents=generate_contents
        )
    except Exception as e:
        print(f"analyze error: {e}")
        return
    finally:
        if cache:
            try:
                client.caches.delete(name=cache.name)
            except Exception:
                pass
        shutil.rmtree(frames_dir, ignore_errors=True)

    print("got response")
    if not response.text:
        print(f"Empty response for {interview_id}")
        return

    result = json.loads(re.sub(r"```json|```", "", response.text).strip())
    result = json.loads(re.sub(r"```json|```", "", response.text).strip())



    print(f"Analysis done for {interview_id}: {result}")
    proctoring_report = result["alerts"]
    cheating_detected = result["cheating_detected"]

    record_proctoring_report(interview_id, applicant_id, proctoring_report, cheating_detected)
    return result

 
 
async def analysis_worker():
    while True:
        job = await analysis_queue.get()
        try:
            await analyze_interview(job["interview_id"], job["applicant_id"])
        except Exception as e:
            print(f"analysis_worker error: {e}")
        finally:
            analysis_queue.task_done()
 
 
@app.on_event("startup")
async def startup():
    asyncio.create_task(analysis_worker())
 
 
async def run_visual_interview(websocket: WebSocket, interview_id: str, applicant_id: str):
    frames_dir = f"/tmp/{interview_id}_{applicant_id}_frames"
    os.makedirs(frames_dir, exist_ok=True)
    frame_count = 0
 
    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            if "realtime_input" in data:
                for chunk in data["realtime_input"].get("media_chunks", []):
                    if chunk["mime_type"] == "image/jpeg":
                        frame_bytes = base64.b64decode(chunk["data"])
                        frame_path = f"{frames_dir}/frame_{frame_count:06d}.jpg"
                        with open(frame_path, "wb") as f:
                            f.write(frame_bytes)
                        frame_count += 1
    except (WebSocketDisconnect, Exception) as e:
        print(f"run_visual_interview ended: {e}")
    finally:
        if frame_count > 0:
            analysis_queue.put_nowait({
                "interview_id": interview_id,
                "applicant_id": applicant_id
            })
            print(f"Queued analysis for {interview_id}, {frame_count} frames")
 
 
@app.websocket("/interview/visual_interview/start/{interview_id}/{applicant_id}")
async def visual_interview(websocket: WebSocket, interview_id: str, applicant_id: str):
    await websocket.accept()

    start_time, end_time, duration, status = get_interview_timer(interview_id)
 
    if datetime.now() < start_time:
        await websocket.close(code=1008, reason="Interview has not started")
        return
 
    if datetime.now() > end_time:
        await websocket.close(code=1008, reason="Interview has ended")
        return
    if status != "active":
        await websocket.close(code=1008, reason="Interview status is closed" )
        return
    
    if applicant_id in active_vision_sessions:
        await websocket.close(code=1008, reason="Session already active")
        return
    
    active_vision_sessions.add(applicant_id)
    try:
        await asyncio.wait_for(
            run_visual_interview(websocket, interview_id, applicant_id),
            timeout=duration * 60
        )
    except asyncio.TimeoutError:
        try:
            await websocket.send_text(json.dumps({"ended": True, "reason": "time_limit_reached"}))
            await websocket.close()
        except RuntimeError:
            pass
    finally:
       active_vision_sessions.discard(applicant_id)
       close_session_applicant(applicant_id)




    
