from app.routes.auth import router as auth_router
from app.routes.ai import router as ai_router
from app.routes.documents import router as documents_router
from app.routes.appointments import router as appointments_router
from app.routes.health import router as health_router
from app.routes.reports import router as reports_router
from app.routes.health_records import (
    router as health_records_router,
    health_alias_router,
)
from app.routes.reminders import router as reminders_router

__all__ = [
    "auth_router",
    "ai_router",
    "documents_router",
    "appointments_router",
    "health_router",
    "reports_router",
    "health_records_router",
    "health_alias_router",
    "reminders_router",
]
