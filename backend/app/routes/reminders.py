from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.reminder import Reminder
from app.schemas.reminder import ReminderCreate, ReminderResponse, ReminderUpdate
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/reminders", tags=["CareBridge AI — Care Reminders"])


@router.post("", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
def create_reminder(
    payload: ReminderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Creates a care reminder for appointments or medicine schedules."""
    reminder = Reminder(
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        due_at=payload.due_at,
        is_completed=False,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.get("", response_model=List[ReminderResponse])
def list_reminders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists all active and completed reminders for the authenticated user."""
    return (
        db.query(Reminder)
        .filter(Reminder.user_id == current_user.id)
        .order_by(Reminder.due_at.asc())
        .all()
    )


@router.patch("/{reminder_id}", response_model=ReminderResponse)
def update_reminder(
    reminder_id: int,
    payload: ReminderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates a reminder (e.g. marking it completed)."""
    reminder = (
        db.query(Reminder)
        .filter(Reminder.id == reminder_id, Reminder.user_id == current_user.id)
        .first()
    )
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")

    if payload.title is not None:
        reminder.title = payload.title
    if payload.description is not None:
        reminder.description = payload.description
    if payload.due_at is not None:
        reminder.due_at = payload.due_at
    if payload.is_completed is not None:
        reminder.is_completed = payload.is_completed
        if payload.is_completed:
            reminder.completed_at = datetime.now(timezone.utc)
        else:
            reminder.completed_at = None

    db.commit()
    db.refresh(reminder)
    return reminder


@router.patch("/{reminder_id}/complete", response_model=ReminderResponse)
def complete_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Marks a reminder as completed (frontend compatibility alias)."""
    reminder = (
        db.query(Reminder)
        .filter(Reminder.id == reminder_id, Reminder.user_id == current_user.id)
        .first()
    )
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")

    reminder.is_completed = True
    reminder.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(reminder)
    return reminder
