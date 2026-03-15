import uuid
from sqlalchemy import Column, SmallInteger, String, ForeignKey, LargeBinary, DateTime, JSON, Boolean, Enum, CheckConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy import case, func
from .db import Base, engine
import enum


class InterviewType(str, enum.Enum):
    user = "prepper"
    organization = "organization"









class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(50), nullable=False)
    email = Column(String(50), nullable=False, unique=True)
    password = Column(String, nullable=False)
    applicants = relationship('Applicant', back_populates="user")
    interviews = relationship('Interview', back_populates="user")


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(50), nullable=False)
    email = Column(String(50), nullable=False, unique=True)
    password = Column(String, nullable=False)
    interviews = relationship('Interview', back_populates="organization")


class Interview(Base):
    __tablename__ = "interviews"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    role = Column(String(50), nullable=False)
    type = Column(Enum(InterviewType), nullable=False)
    description = Column(String, nullable=False)
    job_requirements = Column(String, nullable=False)
    user_id = Column(String, ForeignKey('users.id'), nullable=True)
    organization_id = Column(String, ForeignKey('organizations.id'), nullable=True)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    duration = Column(SmallInteger, nullable=False)
    base_question = Column(String, nullable=False)
    organization = relationship('Organization', back_populates="interviews")
    user = relationship('User', back_populates="interviews")
    applicants = relationship('Applicant', back_populates="interview")
    __table_args__ = (
        CheckConstraint("duration >=10 AND duration <=40", name="duration_interval"),
    )
    _status = Column("status", String, default="active")
    @hybrid_property
    def status(self):
      if self._status == "closed":
        return "closed"
      if datetime.utcnow() > self.end_date:
        return "closed"
      return "active"

    @status.expression
    def status(cls):
      return case(
        (cls._status == "closed", "closed"),
        (cls.end_date < func.now(), "closed"),
        else_="active"
      )



class Applicant(Base):
    __tablename__ = "applicants"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(50), nullable=False)
    resume = Column(LargeBinary, nullable=False)
    full_question = Column(String, nullable=False)
    interview_id = Column(String, ForeignKey('interviews.id'), nullable=False)
    started_session = Column(Boolean, nullable=True)
    ended_session = Column(Boolean, nullable=True )
    interview_date = Column(DateTime, nullable=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    user = relationship('User', back_populates="applicants")
    interview = relationship('Interview', back_populates="applicants")
    report = relationship('Report', back_populates="applicant", uselist=False)


class Report(Base):
    __tablename__ = "reports"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    score = Column(SmallInteger, nullable=True)
    proctoring_report = Column(JSON, nullable=True)
    cheating_detected = Column(Boolean, nullable=True)
    applicant_id = Column(String, ForeignKey('applicants.id'), nullable=False)
    interview_id = Column(String, ForeignKey('interviews.id'), nullable=False)
    applicant = relationship('Applicant', back_populates="report")
    __table_args__ = (
       CheckConstraint('score >= 0 AND score <= 100', name='score_range'),
    )


Base.metadata.create_all(engine)