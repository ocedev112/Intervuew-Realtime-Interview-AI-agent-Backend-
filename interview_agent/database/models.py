import uuid
from sqlalchemy import Column, Integer, String,ForeignKey, LargeBinary, Interval, DateTime
from datetime import datetime
from sqlalchemy.orm import relationship
from .db import Base, engine



class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default= lambda: str(uuid.uuid4()))
    name = Column(String(50))
    email = Column(String(50))
    password = Column(String)
    applicants = relationship('Applicant', back_populates="user")



class Organization(Base):
    __tablename__ = "organizations"
    id = Column(String, primary_key=True, default= lambda: str(uuid.uuid4()))
    name=Column(String(50))
    email=Column(String(50))
    password = Column(String)
    interviews = relationship('Interview', back_populates="organization")

  

    
class Interview(Base):
    __tablename__ = "interviews"
    id = Column(String, primary_key=True, default= lambda: str(uuid.uuid4()))
    name = Column(String(50))
    role = Column(String(50))
    job_requirements=Column(String)
    organization_id = Column(String, ForeignKey('organizations.id'))
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    duration = Column(Integer)
    base_question = Column(String)
    organization =relationship('Organization', back_populates="interviews")
    applicants = relationship('Applicant', back_populates="interview" )

class Applicant(Base):
    __tablename__="applicants"
    id = Column(String, primary_key=True, default= lambda: str(uuid.uuid4()))
    name=Column(String(50))
    resume=Column(LargeBinary)
    full_question = Column(String)
    interview_id = Column(String,ForeignKey('interviews.id'))
    user_id = Column(String, ForeignKey('users.id'))
    user = relationship('User', back_populates="applicants")
    interview = relationship('Interview', back_populates='applicants')


Base.metadata.create_all(engine)