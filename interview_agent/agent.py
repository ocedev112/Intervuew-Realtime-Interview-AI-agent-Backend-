from dotenv import load_dotenv
import os
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

load_dotenv()

from google.adk.agents.llm_agent import Agent
from google.adk.tools import FunctionTool
from google.genai.types import GenerateContentConfig, ToolConfig, FunctionCallingConfig
from google.adk.apps.app import App
from google.adk.apps.app import EventsCompactionConfig
from sentence_transformers import SentenceTransformer
from .Interview_information.vectorCollection import COLLECTION, client, get_encoder


encoder = get_encoder()

def create_base_interview_questions(job_requirements: str, n: int = 5):
    """
    Generate base questions with the job requirements
    """
    # search for each requirement separately for better coverage
    terms = [t.strip() for t in job_requirements.replace(',', ' ').split() if len(t) > 3]
    
    seen_ids = set()
    all_results = []

    for term in terms[:5]:  
        vector = encoder.encode(term).tolist()
        results = client.query_points(
            collection_name=COLLECTION,
            query=vector,
            limit=n,
            score_threshold=0.3  
        ).points
        
        for r in results:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                all_results.append(r)

    questions = " ".join(
        f"{r.payload['title']}: {r.payload['content'][:300]}"  
        for r in all_results
    )

    return {"status": "success", "questions": questions}





question_agent = Agent(
    model= 'gemini-2.5-flash',
    name='question_agent',
    description="""You are a Software Engineering, interview agent 
    designed for creating interview questions based on job requirement provided. T
    """,
    instruction= """
    Use the create_base_interview_questions tool ONCE to fetch questions using the job_requirements.
    Then select and rephrase up to 40 questions that cover most of the job requirements.
    Focus on pragmatic and conceptual questions — do not ask candidates to write code, 
    instead ask how they would approach or think about programming problems.
    Return only the questions grouped by their job requirement section. Format like this:
    Python:
      1. question
      2. question
    Artificial Intelligence:
      1. question
      2. question
    No explanations, no extra text. Only section headers and numbered questions.
     """,
    tools=[FunctionTool(create_base_interview_questions)],
    generate_content_config=GenerateContentConfig(
        max_output_tokens=14000
    )
)

resume_agent = Agent(
    model= 'gemini-2.5-flash',
    name='question_agent',
    description="""You are a Software Engineering, interview agent 
    designed for creating interview questions based on resume
    """,
    instruction="""
    Generate a list of questions based on the resume provided.
    Return a list of 5 to 15 questions with the header "Resume-Based Questions" at the top.
    Each question on its own numbered line.

   Rephrase these template questions based on the specific resume content:

   Experience-Based:
   - In your time at [company name], what problem were you primarily solving?
   - What was your main role and contributions at [company name]?
   - What major problem have you solved that cut costs or increased efficiency?

  Project-Based (for each notable project):
  - What technologies did you use in [project name] and why?
  - What was your role in this project?
  - What problem were you solving with this project?
  - What was your design and approach to this project?
  - How did you handle errors and maintenance?
  - What was the hardest part of this project?
  - Ask one question specific to the project's domain or technology

  If the project is AI-related, also ask:
  - What models did you use and why?
  - Why did you choose this model over alternatives?
  - How did you evaluate the model's performance?

   Only return the header and numbered questions. No extra text.
   """,
    generate_content_config=GenerateContentConfig(
        max_output_tokens=8000
    )

)
vision_agent = Agent(
    model='gemini-2.5-computer-use-preview-10-202',
    name='vision_agent',
    description="""You are a video analysis agent that 
    for detecting anomalities during a meeting""",
    instruction="""You are video analysis inspector that detects abnormalities or signs of malpractice during
    an interview.
    If see one of the following report:
      - User looking way from the screen(light)
      - User  bringing another device on screen(heavy)
      - User typing on keyboard(heavy)
      - User leaving the screen during the interview(heavy)

    
     .""",

)

visionApp = App(
    name="vision_app",
    root_agent=vision_agent,
    events_compaction_config= EventsCompactionConfig(
        compaction_interval=3,
        overlap_size=1
    ),
)

