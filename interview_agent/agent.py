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
 
    terms = [t.strip() for t in job_requirements.replace(',', ' ').split() if len(t) > 3]
    
    seen_ids = set()
    all_results = []

    for term in terms:  
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
    The number of questions would be determined by the interview duration provided:
      30-40minutes: 15 - 25 questions
      20-30minutes: 10 - 15 questions
      10-20minutes: 5 - 10 questions
    Pick lower range of questions if the experience is higher but increase difficulty of questions, and 
    vice vera.
    Then select and rephrase all questions that cover most of the job requirements.
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
    The number of interview questions is based on the interview duraton:
     30-40 minuties - 15 questions
     20-30 minutes - 10 questions
     10-30 minutes - 5 questions
    Pick lower range of questions if the experience is higher but increase difficulty of questions, and 
    vice vera.
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


