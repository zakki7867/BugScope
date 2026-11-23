"""Trace log database model."""

from datetime import datetime
from sqlalchemy import Column, String, Text, Float, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database.session import Base


class TraceLog(Base):
    """Represents an execution trace log entry for a LangGraph workflow node."""

    __tablename__ = "traces"

    id = Column(String(64), primary_key=True, index=True)
    investigation_id = Column(String(64), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    node = Column(String(64), nullable=False)
    input_summary = Column(Text, nullable=False, default="")
    output_summary = Column(Text, nullable=False, default="")
    duration_ms = Column(Float, default=0.0)
    tokens_in = Column(Integer, default=0)
    tokens_out = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    investigation = relationship("Investigation", back_populates="traces")
