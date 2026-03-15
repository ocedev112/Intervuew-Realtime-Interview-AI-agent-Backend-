from .models import Interview, Organization, Applicant, User, Report,InterviewType
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


def fetch_details_organization(org_id: str):
    db = sessionLocal()
    try:
        interviews = (
            db.query(Interview)
            .filter(Interview.organization_id == org_id)
            .all()
        )

        def serialize(obj):
            data = {
                c.name: getattr(obj, c.name)
                for c in obj.__table__.columns
                if not isinstance(getattr(obj, c.name), bytes)
            }
            data.pop("base_question", None)
            data.pop("full_question", None)
            return data

        result = []
        for interview in interviews:
            applicants = (
                db.query(Applicant)
                .filter(Applicant.interview_id == interview.id)
                .all()
            )
            interview_data = serialize(interview)
            interview_data["status"] = interview.status  # ← hybrid property
            result.append({
                "interview": interview_data,
                "applicants": [
                    {
                        "applicant": serialize(applicant),
                        "report": serialize(applicant.report) if applicant.report else None
                    }
                    for applicant in applicants
                ]
            })

        return result

    except Exception as e:
        db.rollback()
        raise

    finally:
        db.close()



def fetch_all_candidates_organization(org_id: str):
    db = sessionLocal()
    try:
        applicants = (
            db.query(Applicant)
            .join(Interview, Applicant.interview_id == Interview.id)
            .filter(Interview.organization_id == org_id)
            .all()
        )

        def serialize_applicant(applicant):
            report = applicant.report
            interview = applicant.interview

            
            if not applicant.started_session: 
              status = "Pending"
            elif report and report.cheating_detected:
              status = "Declined"
            elif report and report.score is not None:
              status = "Recommended" if report.score >= 60 else "Declined"
            else:
              status = "Pending"

            return {
                "id": applicant.id,
                "name": applicant.name,
                "interview_id": applicant.interview_id,
                "role": interview.role,
                "interview_date": applicant.interview_date.isoformat() if applicant.interview_date else None,
                "score": report.score if report else None,
                "cheating_detected": report.cheating_detected if report else None,
                "status": status,
                "started_session": applicant.started_session,
                "ended_session": applicant.ended_session,
            }

        return [serialize_applicant(a) for a in applicants]

    except Exception as e:
        db.rollback()
        raise

    finally:
        db.close()


def fetch_candidate_detail(applicant_id: str):
    db = sessionLocal()
    try:
        applicant = (
            db.query(Applicant)
            .filter(Applicant.id == applicant_id)
            .first()
        )

        if not applicant:
            return None

        report = applicant.report
        interview = applicant.interview

        if not applicant.started_session:
            status = "Pending"
        elif report and report.cheating_detected:
            status = "Declined"
        elif report and report.score is not None:
            status = "Recommended" if report.score >= 60 else "Declined"
        else:
            status = "Pending"

        alerts = []
        if report and report.proctoring_report:
            raw = report.proctoring_report
            if isinstance(raw, str):
                import json
                raw = json.loads(raw)
           
            alerts = raw if isinstance(raw, list) else []

        return {
            "id": applicant.id,
            "name": applicant.name,
            "interview_id": applicant.interview_id,
            "role": interview.role,
            "interview_date": applicant.interview_date.isoformat() if applicant.interview_date else None,
            "started_session": applicant.started_session,
            "ended_session": applicant.ended_session,
            "score": report.score if report else None,
            "cheating_detected": report.cheating_detected if report else None,
            "proctoring_alerts": alerts,
            "status": status,
        }

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
            .filter(Interview.type == InterviewType.organization)
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


def fetch_interview_report(interview_id: str, user_id: str):
    db = sessionLocal()
    try:
        applicant = (
            db.query(Applicant)
            .join(Interview, Applicant.interview_id == Interview.id)
            .filter(
                Applicant.interview_id == interview_id,
                Applicant.user_id == user_id,
            )
            .first()
        )

        if not applicant:
            return None

        interview = applicant.interview
        report = applicant.report

        alerts = []
        if report and report.proctoring_report:
            raw = report.proctoring_report
            if isinstance(raw, str):
                import json
                raw = json.loads(raw)
            alerts = raw if isinstance(raw, list) else []

        return {
            "role": interview.role,
            "duration": interview.duration,
            "interview_date": applicant.interview_date.isoformat() if applicant.interview_date else None,
            "started_session": applicant.started_session,
            "ended_session": applicant.ended_session,
            "score": report.score if report else None,
            "cheating_detected": report.cheating_detected if report else None,
            "proctoring_alerts": alerts,
        }

    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()

def fetch_prep_interviews(user_id: str):
    db = sessionLocal()
    try:
        results = (
            db.query(Applicant, Interview)
            .join(Interview, Applicant.interview_id == Interview.id)
            .filter(Applicant.user_id == user_id)
            .filter(Interview.type == InterviewType.user)
            .all()
        )

        def serialize_interview(interview):
            data = {c.name: getattr(interview, c.name) for c in interview.__table__.columns}
            data.pop("base_question", None)
            return data

        if not results:
            return []

        return [
            {
                "applicant_id": applicant.id,
                "interview": serialize_interview(interview),
                "score": applicant.report.score if applicant.report else None,
                "started_session": applicant.started_session,
                "ended_session": applicant.ended_session,
                "interview_date": applicant.interview_date.isoformat() if applicant.interview_date else None,
            }
            for applicant, interview in results
        ]
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


def record_score(interview_id: str, applicant_id: str, score: int):
    db = sessionLocal()
    try:
        applicant = db.query(Report).filter(Report.applicant_id == applicant_id).first()
        if applicant is None:
           applicant = Report(score=score, interview_id=interview_id, applicant_id=applicant_id)
           db.add(applicant)  
        else:
            applicant.score = score
        db.commit()
        db.refresh(applicant)
    finally:
        db.close()

def record_proctoring_report(interview_id: str, applicant_id: str, proctoring_report: list, cheating_detected: bool):
    db = sessionLocal()
    try:
        applicant = db.query(Report).filter(Report.applicant_id == applicant_id).first()
        if applicant is None: 
            applicant = Applicant(proctoring_report=proctoring_report, cheating_detected=cheating_detected, applicant_id=applicant_id, interview_id=interview_id)
            db.add(applicant)
        else:
            applicant.cheating_detected = cheating_detected
            applicant.proctoring_report = proctoring_report
        db.commit()
        db.refresh(applicant)
    finally: 
        db.close()
        
    
def toggle_interview_status(interview_id: str, action: str):
    db = sessionLocal()
    try:
        interview = (
            db.query(Interview)
            .filter(Interview.id == interview_id)
            .first()
        )
        if not interview:
            return None

        if action == "close":
            interview._status = "closed"
        elif action == "open":
            interview._status = "active"

        db.commit()
        return {"status": interview._status}

    except Exception as e:
        db.rollback()
        raise

    finally:
        db.close()

def open_interview(interview_id: str):
    db = sessionLocal()
    try:
        interview = (
            db.query(Interview)
            .filter(Interview.id == interview_id)
            .first()
        )
        if not interview:
            return None

        interview.end_date = datetime.utcnow()
        interview.status = "active"
        db.commit()
        return {"success": True}

    except Exception as e:
        db.rollback()
        raise

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
      print(interview.status)
      return interview.start_date, interview.end_date, interview.duration, interview.status
   finally:
      db.close()

def get_applicant_start_session(applicant_id: str):
    db = sessionLocal()
    try:
       applicant =  db.query(Applicant).filter(Applicant.id == applicant_id).first()
       print("started_session", applicant.started_session)
       return applicant.started_session
    finally:
        db.close()

def close_session_applicant(applicant_id: str):
    db = sessionLocal()
    try:
        applicant = db.query(Applicant).filter(Applicant.id == applicant_id).first()
        applicant.ended_session = True
        db.commit()
    finally:
        db.close()
    

    
def start_interview_for_applicant(applicant_id: str):
    db = sessionLocal()
    try:
        applicant = db.query(Applicant).filter(Applicant.id == applicant_id).first()
        applicant.started_session = True
        applicant.interview_date = datetime.utcnow()
        db.commit()
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



