"""Patch database model."""

from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database.session import Base


class Patch(Base):
    """Represents a minimal code patch generated for a bug fix."""

    __tablename__ = "patches"

    id = Column(String(64), primary_key=True, index=True)
    investigation_id = Column(String(64), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    hypothesis_id = Column(String(64), ForeignKey("hypotheses.id", ondelete="SET NULL"), nullable=True, index=True)
    diff = Column(Text, nullable=False)
    explanation = Column(Text, nullable=False)
    modified_files = Column(Text, default="[]")
    is_minimal = Column(Boolean, default=True)
    needs_human_decision = Column(Boolean, default=False)
    human_decision_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    investigation = relationship("Investigation", back_populates="patches")
    hypothesis = relationship("Hypothesis", back_populates="patches")
    validations = relationship("ValidationResult", back_populates="patch", cascade="all, delete-orphan")
