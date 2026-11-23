"""Experiment database model."""

from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database.session import Base


class Experiment(Base):
    """Represents a controlled experiment executed to confirm or reject a hypothesis."""

    __tablename__ = "experiments"

    id = Column(String(64), primary_key=True, index=True)
    investigation_id = Column(String(64), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    hypothesis_id = Column(String(64), ForeignKey("hypotheses.id", ondelete="CASCADE"), nullable=False, index=True)
    experiment_type = Column(String(64), default="BEHAVIOR_REPRODUCTION")
    code_change = Column(Text, nullable=True)
    test_command = Column(Text, nullable=False, default="pytest")
    expected_outcome = Column(Text, nullable=True)
    actual_outcome = Column(Text, nullable=True)
    exit_code = Column(Integer, default=0)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    success = Column(Boolean, default=False)
    conclusion = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    investigation = relationship("Investigation", back_populates="experiments")
    hypothesis = relationship("Hypothesis", back_populates="experiments")
