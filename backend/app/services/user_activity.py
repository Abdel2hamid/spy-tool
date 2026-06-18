"""
Lightweight user activity logger.

Usage:
    from app.services.user_activity import log_user_action
    log_user_action(db, user_id=ctx.user.id, action="app.import", detail="Spotify")
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import UserActivityLog

logger = logging.getLogger(__name__)


def log_user_action(
    db: Session,
    user_id: int,
    action: str,
    detail: str = None,
    metadata: dict = None,
):
    """Fire-and-forget activity log entry. Never raises."""
    try:
        entry = UserActivityLog(
            user_id=user_id,
            action=action,
            detail=detail,
            metadata_=metadata,
        )
        db.add(entry)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to log user activity: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
