from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.health_record import HealthRecord
from app.schemas.health_record import HealthRecordCreate, HealthRecordResponse
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/health-records", tags=["CareBridge AI — Health Tracker"])
health_alias_router = APIRouter(prefix="/health/records", tags=["CareBridge AI — Health Tracker"])


def _add_health_measurement(
    payload: HealthRecordCreate,
    current_user: User,
    db: Session,
):
    record = HealthRecord(
        user_id=current_user.id,
        metric_type=payload.metric_type.strip().lower(),
        value=payload.value,
        unit=payload.unit.strip(),
        notes=payload.notes,
        recorded_at=payload.recorded_at or datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _get_health_history(
    metric_type: Optional[str],
    current_user: User,
    db: Session,
):
    query = db.query(HealthRecord).filter(HealthRecord.user_id == current_user.id)
    if metric_type:
        query = query.filter(HealthRecord.metric_type == metric_type.strip().lower())
    return query.order_by(HealthRecord.recorded_at.asc()).all()


# Routes on /health-records
@router.post("", response_model=HealthRecordResponse, status_code=status.HTTP_201_CREATED)
def add_health_measurement(
    payload: HealthRecordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _add_health_measurement(payload, current_user, db)


@router.get("", response_model=List[HealthRecordResponse])
def get_health_history(
    metric_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_health_history(metric_type, current_user, db)


# Alias Routes on /health/records (Frontend compatibility)
@health_alias_router.post("", response_model=HealthRecordResponse, status_code=status.HTTP_201_CREATED)
def add_health_measurement_alias(
    payload: HealthRecordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _add_health_measurement(payload, current_user, db)


@health_alias_router.get("", response_model=List[HealthRecordResponse])
def get_health_history_alias(
    metric_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_health_history(metric_type, current_user, db)
