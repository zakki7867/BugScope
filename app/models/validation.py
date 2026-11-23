"""Validation result database model."""

from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database.session import Base


class ValidationResult(Base):
    """Represents a 3-phase patch validation execution."""

    __tablename__ = "validation_results"

    id = Column(String(64), primary_key=True, index=True)
    investigation_id = Column(String(64), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    patch_id = Column(String(64), ForeignKey("patches.id", ondelete="CASCADE"), nullable=True, index=True)
    pre_patch_reproduced = Column(Boolean, default=False)
    post_patch_passed = Column(Boolean, default=False)
    regression_suite_passed = Column(Boolean, default=False)
    status = Column(String(64), default="SKIPPED")
    details = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    investigation = relationship("Investigation", back_populates="validations")
    patch = relationship("Patch", back_populates="validations")
