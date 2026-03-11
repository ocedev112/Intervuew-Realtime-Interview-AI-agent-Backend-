

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
from google.adk.apps.app import EventsCompactionConfig
from fastapi import FastAPI, Depends, UploadFile, File, WebSocket, HTTPException, Form
from fastapi.websockets import WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import pymupdf
from pydantic import BaseModel
from database.process import create_UserDB,create_InterviewDB, create_organizationDB, jobRequirements, convert_requirements_tostr
from database.process import get_interview_questions, create_ApplicantDB, get_applicant_questions, get_interview_timer, fetch_applicantId_interview
from database.process import fetch_interview, fetch_applicant
from interview_agent.agent import question_agent, resume_agent, visionApp
from datetime import datetime
from google import genai
import base64

client = genai.Client(
    vertexai=True,
    project=os.environ["GOOGLE_CLOUD_PROJECT"],
    location=os.environ["GOOGLE_CLOUD_LOCATION"]
)




class UserRequest(BaseModel):
    name: str
    email: str
    password: str


class OrganizationRequest(BaseModel):
    name: str
    email: str
    password: str

class InterviewRequest(BaseModel): 
    name: str
    role: str
    job_requirements: jobRequirements
    organization_id: str
    start_date: datetime
    end_date: datetime
    duration: int



class ApplicantRequest(BaseModel):
    name: str
    user_id: str



app =FastAPI()
session_service = InMemorySessionService()




async def create_interview_base_questions(message: str):
    runner = Runner(agent=question_agent, app_name="interview", session_service=session_service)
    prompt = f"""
      Generate questions using job_requirements: {message}
    """
    print("creating base questions")
    session = await session_service.create_session(app_name="interview", user_id="create_base_question")
    print(f"session: {session}")
    for event in runner.run(
        user_id="create_base_question",
        session_id=session.id,
        new_message=Content(parts=[Part(text=prompt)]),
        run_config=RunConfig(
            streaming_mode= StreamingMode.NONE,
            max_llm_calls=3
        )

    ):
        print(f"4. event: {event}")
        if event.is_final_response():
            return event.content.parts[0].text

async def create_interview_full_questions(message: str):
    runner = Runner(agent=resume_agent, app_name="interview", session_service=session_service)
    prompt = f"""
      Generate questions using  this resume: {message}
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
    allow_origins=["http://localhost:5173"],  # your React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)  

@app.post("/User/create")
async def create_user(request: UserRequest):
  try:
    hashed = bcrypt.hashpw(request.password.encode('utf-8'),  bcrypt.gensalt())
    hashed_password_string = hashed.decode('utf-8')
    create_UserDB(request.name, request.email, hashed_password_string)
    return {"status": "ok"}
  except Exception as e:
      print(e)
      raise HTTPException(status_code=500, detail=str(e))
  

@app.get("/User/{user_id}/applicant/interviews")
async def get_user_applicant(user_id: str):
   try:
       results  = fetch_applicantId_interview(user_id)
       return results
   except Exception as e:
      print(e)
      raise HTTPException(status_code=500, detail=str(e))



@app.post("/Organization/create") 
async def create_organization(request: OrganizationRequest):
  try:
    hashed = bcrypt.hashpw(request.password.encode('utf-8'),  bcrypt.gensalt())
    hashed_password_string = hashed.decode('utf-8')
    create_organizationDB(request.name, request.email, hashed_password_string)
    return {"status": "ok"}
  except Exception as e:
      print(e)
      raise HTTPException(status_code=500, detail=str(e))

@app.post("/Interview/create")
async def create_interview(request: InterviewRequest):
  try:
    stringJobRequirements = convert_requirements_tostr(request.job_requirements)
    base_question = await create_interview_base_questions(stringJobRequirements)
    print(f"3. base questions: {base_question}")
    create_InterviewDB(request.name, request.role, request.job_requirements, request.organization_id, request.start_date, request.end_date, request.duration, base_question)
    return {"status": "ok"}
  except Exception as e:
     print(e)
     raise HTTPException(status_code=500, detail=str(e))

@app.get("/Interview/{interview_id}")
async def get_interview(interview_id: str):
   try:
      interview = fetch_interview(interview_id)
      return interview
   except Exception as e:
      print(e)
      raise HTTPException(status_code=500, detail=str(e))
   
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
async def sign_up_for_interview(interview_id: str, applicant: str = Form(...),  file: UploadFile = File(...)):
  try: 
    applicant_data = json.loads(applicant)
    applicant_req = ApplicantRequest(**applicant_data)
    pdf_bytes = await file.read()

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

    resume = " ".join(page.get_text() for page in doc)
    base_questions = get_interview_questions(interview_id)
    domain_questions =  await create_interview_full_questions(resume)
    full_question = domain_questions + base_questions
    create_ApplicantDB(applicant_req.name, pdf_bytes, full_question, interview_id, applicant_req.user_id)
    return {"status": "ok"}
  except Exception as e:
     print(e)
     raise HTTPException(status_code=500, detail=str(e))





async def run_interview(websocket, applicant_id, interview_app):
    runner = InMemoryRunner(app=interview_app)

    session = await runner.session_service.create_session(
        app_name="interview_live", user_id=applicant_id
    )
  
    transcript_log = []
    live_request_queue = LiveRequestQueue()

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
       
        print("send_audio started")
        await websocket.send_text(json.dumps({"mime_type": "audio/pcm"}))


        print("sent mime_type header")
        live_request_queue.send_content(
            types.Content(parts=[types.Part(text="Begin the interview.")], role="user")
        )
        print("sent begin interview content")
        run_config = RunConfig(
           streaming_mode=StreamingMode.BIDI,
           response_modalities=[Modality.AUDIO],
           max_llm_calls=500,
           session_resumption=types.SessionResumptionConfig(
               transparent=True
           ), 
           context_window_compression= types.ContextWindowCompressionConfig(
              trigger_tokens=50000,
               sliding_window=types.SlidingWindow( target_tokens=25000 ),
             )

        )

        try:
            async for event in runner.run_live(
                session=session,
                live_request_queue=live_request_queue,
                run_config=run_config
                ):

                    if event.input_transcription and event.input_transcription.finished:
                        transcript_log.append({
                            "role": "candidate",
                            "text": event.input_transcription.text,
                            "timestamp": datetime.now().isoformat()
                        })

                    if event.output_transcription and event.output_transcription.finished:
                        transcript_log.append({
                            "role": "agent",
                            "text": event.output_transcription.text,
                            "timestamp": datetime.now().isoformat()
                        })

                    part = (event.content and event.content.parts and event.content.parts[0])
                    if part:
                        is_audio = part.inline_data and part.inline_data.mime_type.startswith("audio/pcm")
                        if is_audio and part.inline_data.data:
                            await websocket.send_bytes(part.inline_data.data)

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

                  

    await asyncio.gather(receive_audio(), send_audio(), return_exceptions=True)


@app.get("/check_models")
async def check_models():
    models = []
    for model in client.models.list():
        models.append(model.name)
    return {"models": models}






@app.websocket("/interview/start/{interview_id}/{applicant_id}")
async def audio_interview(websocket: WebSocket, interview_id: str, applicant_id: str):
  await websocket.accept()

  start_time, end_time, duration = get_interview_timer(interview_id)

  if(datetime.now() < start_time):
      await websocket.close(code=1008, reason="Interview has not started")
      return
  
  if (datetime.now() > end_time):
     await websocket.close(code=1008, reason="Interview has not started")
     return
  
  questions = get_applicant_questions(applicant_id)
  interview_agent = Agent(
    name="interview_live",
    model="gemini-live-2.5-flash-native-audio",
    instruction=f"""
        You are a professional Software Engineering interview agent.
        Do NOT output any reasoning, thoughts, or internal monologue.
        Respond only with direct spoken answers.
        Ask one question at a time and wait for a response before continuing.
        Start with 2 resume-based questions, then proceed through remaining sections.
        When all questions are done say "The interview is now complete."
        Questions: {questions}.
        Do NOT answer the users questions.
        DO NOT ASK the same question twice
        Begin by greeting the candidate and asking the first resume-based question.
    """,
    )
  
  interview_app = App(
       name="interview_app",
       root_agent=interview_agent,
       events_compaction_config= EventsCompactionConfig(
         compaction_interval=10,
         overlap_size=5
      ),
    )
  try:
     await asyncio.wait_for(run_interview(websocket,applicant_id, interview_app), timeout=duration*60)
  except asyncio.TimeoutError:
     await websocket.send_text(json.dumps({"ended": True, "reason": "time_limit_reached"}))
     await websocket.close()


async def analyze_interview(interview_id: str, applicant_id: str):
    frames_dir = f"/tmp/{interview_id}_{applicant_id}_frames"
    if not os.path.exists(frames_dir):
        print(f"No frames found for {interview_id}")
        return

    frame_files = sorted(os.listdir(frames_dir))
    if not frame_files:
        print(f"Empty frames dir for {interview_id}")
        return

    import imageio
    video_path = f"/tmp/{interview_id}_{applicant_id}.mp4"

    # stream frames one at a time into mp4
    with imageio.get_writer(video_path, fps=1) as writer:
        for f in frame_files:
            frame = imageio.v3.imread(f"{frames_dir}/{f}")
            writer.append_data(frame)

    # upload via File API
    with open(video_path, "rb") as f:
        video_file = client.files.upload(
            file=f,
            config={"mime_type": "video/mp4", "display_name": f"{interview_id}_proctoring"}
        )
    os.remove(video_path)

    print(f"video_file.uri: {video_file.uri}")
    print(f"video_file.state: {video_file.state}")
    print(f"video_file.name: {video_file.name}")

    # wait for processing
    while video_file.state.name == "PROCESSING":
        await asyncio.sleep(5)
        video_file = client.files.get(name=video_file.name)

    if video_file.state.name == "FAILED":
        print(f"Video processing failed for {interview_id}")
        return

    # retry loop
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Part(file_data=types.FileData(
                        file_uri=video_file.uri,
                        mime_type="video/mp4"
                    )),
                    types.Part(text="""Analyze this interview recording for proctoring violations.
Look for: candidate looking away frequently, another person visible, phone usage, reading from notes, candidate leaving frame.
Respond as JSON only: {"alerts": [{"timestamp_seconds": int, "reason": str}], "summary": str}""")
                ]
            )
            break
        except Exception as e:
            if "429" in str(e):
                match = re.search(r"retryDelay.*?(\d+)s", str(e))
                wait = int(match.group(1)) + 2 if match else 60
                print(f"Rate limited, retrying in {wait}s (attempt {attempt + 1})")
                await asyncio.sleep(wait)
            else:
                print(f"analyze frame error: {e}")
                return
    else:
        print(f"Max retries exceeded for {interview_id}")
        return
    
    if not response.text:
       print(f"Empty response for {interview_id}, candidates: {response.candidates}")
       return
    print(response.text)
    result = json.loads(re.sub(r"```json|```", "", response.text).strip())
    print(result)


    client.files.delete(name=video_file.name)
    shutil.rmtree(frames_dir, ignore_errors=True)
    print(f"Analysis done for {interview_id}")



async def analysis_worker():
    while True:
        job = await analysis_queue.get()
        await analyze_interview(job["interview_id"], job["applicant_id"])
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
    start_time, end_time, duration = get_interview_timer(interview_id)
    
    if(datetime.now() < start_time):
       await websocket.close(code=1008, reason="Interview has not started")
       return
  
    if (datetime.now() > end_time):
       await websocket.close(code=1008, reason="Interview has not started")
       return
    
    try:
       await asyncio.wait_for(run_visual_interview(websocket, interview_id, applicant_id), timeout=duration*60)
    except asyncio.TimeoutError:
       await websocket.send_text(json.dumps({"ended": True, "reason": "time_limit_reached"}))
       await websocket.close()
    




    
