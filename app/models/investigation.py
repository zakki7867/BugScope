"""Investigation database model."""

from datetime import datetime
from sqlalchemy import Column, String, Text, Float, DateTime
from sqlalchemy.orm import relationship
from app.database.session import Base


class Investigation(Base):
    """Represents a debugging investigation session in BugScope."""

    __tablename__ = "investigations"

    id = Column(String(64), primary_key=True, index=True)
    repository_name = Column(String(256), nullable=False, default="unknown")
    repository_path = Column(String(512), nullable=False, default="")
    error_type = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)
    stack_trace = Column(Text, nullable=True)
    status = Column(String(64), nullable=False, default="PENDING", index=True)
    verdict = Column(String(64), nullable=False, default="INVESTIGATING")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    summary = Column(Text, nullable=True)
    root_cause_summary = Column(Text, nullable=True)
    total_duration_seconds = Column(Float, default=0.0)
    total_cost_usd = Column(Float, default=0.0)
    report_json = Column(Text, nullable=True)

    # Relationships
    hypotheses = relationship("Hypothesis", back_populates="investigation", cascade="all, delete-orphan", order_by="Hypothesis.rank")
    evidence = relationship("Evidence", back_populates="investigation", cascade="all, delete-orphan")
    experiments = relationship("Experiment", back_populates="investigation", cascade="all, delete-orphan")
    patches = relationship("Patch", back_populates="investigation", cascade="all, delete-orphan")
    validations = relationship("ValidationResult", back_populates="investigation", cascade="all, delete-orphan")
    traces = relationship("TraceLog", back_populates="investigation", cascade="all, delete-orphan")
