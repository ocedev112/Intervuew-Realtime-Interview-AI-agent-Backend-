from .models import Interview, Organization, Applicant, User, InterviewType
from .db import sessionLocal
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class jobRequirements(BaseModel):
   role: str
   languages: list[dict[str, int]]
   domains: list[dict[str, int]]
   softskills: list[str]

def convert_requirements_tostr(job_requirements: jobRequirements) -> str:
    
    result = f"Role: {job_requirements.role}\n"
    
    if job_requirements.languages:
        result += "Languages:\n"
        for lang in job_requirements.languages:
            for name, years in lang.items():
                result += f"  - {name}: {years} years\n"
    
    if job_requirements.domains:
        result += "Domains:\n"
        for domain in job_requirements.domains:
            for name, years in domain.items():
                result += f"  - {name}: {years} years\n"
    
    if job_requirements.softskills:
        result += "Softskills:\n"
        for skill in job_requirements.softskills:
            result += f"  - {skill}\n"
    
    return result


def create_UserDB(name: str, email: str,password: str)  ->User:
   db = sessionLocal()
   try:
      user = User(name=name, email=email, password=password)
      db.add(user)
      db.commit()
      db.refresh(user)
      return user
   except Exception as e:
      db.rollback()
      raise
   finally:
      db.close()


def fetch_applicantId_interview(user_id: str):
    db = sessionLocal()
    try:
        results = (
            db.query(Applicant, Interview)
            .join(Interview, Applicant.interview_id == Interview.id)
            .filter(Applicant.user_id == user_id)
            .all()
        )
        def serialize_interview(interview):
            data = {c.name: getattr(interview, c.name) for c in interview.__table__.columns}
            data.pop("base_question", None)  
            return data
        if not results:
            return []
        return [{"applicant_id": applicant.id, "interview": serialize_interview(interview)}for applicant, interview in results]
    finally:
        db.close()


def fetch_interview(interview_id: str):
   db = sessionLocal()
   try:
      data = db.query(Interview).filter(Interview.id == interview_id).first()
      interview = {i.name: getattr(data, i.name) for i in data.__table__.columns}
      interview.pop("base_question", None)
      return interview
   finally:
      db.close()

def fetch_applicant(applicant_id: str):
    db = sessionLocal()
    try:
        data = db.query(Applicant).filter(Applicant.id == applicant_id).first()
        if not data:
            return None
        
        applicant = {}
        for a in data.__table__.columns:
            value = getattr(data, a.name)
            if isinstance(value, bytes):
                continue  
            applicant[a.name] = value
        
        applicant.pop("full_question", None)
        return applicant
    finally:
        db.close()

def create_organizationDB(name: str, email: str, password: str) -> Organization:
    db = sessionLocal()
    try:
       org = Organization(name=name, email=email, password=password)
       db.add(org)
       db.commit()
       db.refresh(org)
       return org
    finally:
       db.close()





def create_InterviewDB(role: str, type: str, description: str, job_requirements: jobRequirements, start_date: datetime, end_date: datetime, duration: int, base_question: str, organization_id: Optional[str] = None, user_id: Optional[str] = None) -> Interview:
    db = sessionLocal()
    try:
       stringJobRequiremnts = convert_requirements_tostr(job_requirements)
       if type == InterviewType.organization:
          if organization_id is None:
             raise Exception("must use either user or organization") 
          interview = Interview( role=role, type=type, description=description, job_requirements=stringJobRequiremnts, organization_id=organization_id, start_date=start_date, end_date=end_date, duration=duration, base_question=base_question)
       elif type == InterviewType.user:
          if user_id is None:
             raise Exception("must use either user or organization")
          interview = Interview( role=role,type=type, description=description, job_requirements=stringJobRequiremnts, user_id=user_id, start_date=start_date, end_date=end_date, duration=duration, base_question=base_question)
       db.add(interview)
       db.commit()
       db.refresh(interview)
       return interview
    except Exception as e:
       db.rollback()
       raise
    finally:
       db.close()
    
def get_interview_questions(interview_id: str):
   db = sessionLocal()
   try:
      interview = db.query(Interview).filter(Interview.id == interview_id).first()
      return interview.base_question, interview.duration
   except Exception as e:
      db.rollback()
      raise
   finally:
      db.close()

def get_interview_timer(interview_id: str):
   db = sessionLocal()
   try:
      interview = db.query(Interview).filter(Interview.id == interview_id).first()
      return interview.start_date, interview.end_date, interview.duration
   finally:
      db.close()

def get_applicant_questions(applicant_id: str):
    db = sessionLocal()
    try:
        applicant = db.query(Applicant).filter(Applicant.id == applicant_id).first()
        if not applicant:
            return None  
        return applicant.full_question
    except Exception as e:
       db.rollback()
       raise
    finally:
        db.close()

def create_ApplicantDB(name: str, resume: bytes, full_question: str, interview_id: int, user_id: str):
   db = sessionLocal()
   try:
      applicant = Applicant(name=name, resume=resume, full_question=full_question, interview_id=interview_id, user_id=user_id)
      db.add(applicant)
      db.commit()
      db.refresh(applicant)
   except Exception as e:
      db.rollback()
      raise
   finally:
      db.close()



