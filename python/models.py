from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

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