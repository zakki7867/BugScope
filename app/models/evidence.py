"""Evidence item database model."""

from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database.session import Base


class Evidence(Base):
    """Represents a verifiable piece of code evidence attached to a hypothesis."""

    __tablename__ = "evidence"

    id = Column(String(64), primary_key=True, index=True)
    investigation_id = Column(String(64), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    hypothesis_id = Column(String(64), ForeignKey("hypotheses.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(512), nullable=False)
    line_start = Column(Integer, nullable=False)
    line_end = Column(Integer, nullable=False)
    code_quote = Column(Text, nullable=False)
    stance = Column(String(32), nullable=False, default="SUPPORTS")
    reason = Column(Text, nullable=False)
    is_verified = Column(Boolean, default=False)
    verification_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    investigation = relationship("Investigation", back_populates="evidence")
    hypothesis = relationship("Hypothesis", back_populates="evidence")
