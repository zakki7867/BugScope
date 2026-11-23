"""BugScope REST API module."""

from app.api.investigations import router as investigations_router
from app.api.repositories import router as repositories_router
from app.api.hypotheses import router as hypotheses_router
from app.api.evidence import router as evidence_router
from app.api.experiments import router as experiments_router
from app.api.patches import router as patches_router
from app.api.validation import router as validation_router
from app.api.reports import router as reports_router
from app.api.evaluation import router as evaluation_router

__all__ = [
    "investigations_router",
    "repositories_router",
    "hypotheses_router",
    "evidence_router",
    "experiments_router",
    "patches_router",
    "validation_router",
    "reports_router",
    "evaluation_router",
]
