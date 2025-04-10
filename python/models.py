from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    name = Column(String)

    def __repr__(self):
        return f"<Project(id={self.id}, name={self.name})>"


class Run(Base):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    projectId = Column(Integer, ForeignKey("projects.id"))
    organizationId = Column(String, ForeignKey("organization.id"))
    status = Column(String)
    updatedAt = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project = relationship("Project", backref="runs")
    organization = relationship("Organization", backref="runs")

    def __repr__(self):
        return (
            f"<Run(id={self.id}, name={self.name}, projectId={self.projectId}, "
            f"organizationId={self.organizationId}, status={self.status}, "
            f"updatedAt={self.updatedAt})>"
        )


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    runId = Column(Integer, ForeignKey("runs.id"))
    organizationId = Column(String)
    createdAt = Column(DateTime(timezone=True), server_default=func.now())
    type = Column(String)
    content = Column(String)

    run = relationship("Run", backref="notifications")

    def __repr__(self):
        return (
            f"<Notification(id={self.id}, runId={self.runId}, "
            f"organizationId={self.organizationId}, type={self.type}, "
            f"content={self.content})>"
        )

class User(Base):
    __tablename__ = "user"
    
    id = Column(String, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True)
    emailVerified = Column(Boolean)
    image = Column(String)
    createdAt = Column(DateTime)
    updatedAt = Column(DateTime)
    twoFactorEnabled = Column(Boolean)
    role = Column(String)
    banned = Column(Boolean)
    banReason = Column(String)
    banExpires = Column(DateTime)
    finishedOnboarding = Column(Boolean)

    members = relationship("Member", back_populates="user")

class Organization(Base):
    __tablename__ = "organization"
    
    id = Column(String, primary_key=True)
    name = Column(String)
    slug = Column(String, unique=True)
    logo = Column(String)
    createdAt = Column(DateTime)
    # metadata = Column(String)

    members = relationship("Member", back_populates="organization")

class Member(Base):
    __tablename__ = "member"
    
    id = Column(String, primary_key=True)
    organizationId = Column(String, ForeignKey("organization.id"))
    userId = Column(String, ForeignKey("user.id"))
    role = Column(String)
    createdAt = Column(DateTime)

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="members") 