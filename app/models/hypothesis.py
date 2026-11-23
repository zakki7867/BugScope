"""Hypothesis database model."""

from datetime import datetime
from sqlalchemy import Column, String, Text, Float, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database.session import Base


class Hypothesis(Base):
    """Represents a potential root-cause hypothesis formulated during investigation."""

    __tablename__ = "hypotheses"

    id = Column(String(64), primary_key=True, index=True)
    investigation_id = Column(String(64), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    rank = Column(Integer, default=1)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=False)
    likelihood_score = Column(Float, default=0.0)
    is_upstream = Column(Boolean, default=False)
    status = Column(String(64), default="CANDIDATE")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    investigation = relationship("Investigation", back_populates="hypotheses")
    evidence = relationship("Evidence", back_populates="hypothesis", cascade="all, delete-orphan")
    experiments = relationship("Experiment", back_populates="hypothesis", cascade="all, delete-orphan")
    patches = relationship("Patch", back_populates="hypothesis")
