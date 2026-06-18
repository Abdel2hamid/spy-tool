"""
Admin Console Router
====================
CRUD endpoints for superadmin management of users, workspaces,
subscriptions, usage, scheduled jobs, and system health.

All endpoints require a user with is_superadmin=True.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_superadmin
from app.models.models import (
    App, User, Workspace, Membership, Subscription, WorkspaceUsage,
    Favorite, MyApp,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin-console", tags=["admin-console"])


# ═══════════════════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class DashboardStats(BaseModel):
    total_users: int
    active_users: int
    total_workspaces: int
    total_apps: int
    total_keywords: int
    total_reviews: int
    plans: dict  # {plan_code: count}
    usage_this_month: dict  # {app_imports: total, ...}

class UserItem(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    is_superadmin: bool
    created_at: Optional[str]
    workspace_name: Optional[str]
    plan_code: Optional[str]
    role: Optional[str]

class UserListResponse(BaseModel):
    users: List[UserItem]
    total: int

class WorkspaceItem(BaseModel):
    id: int
    name: str
    slug: str
    created_at: Optional[str]
    owner_email: Optional[str]
    member_count: int
    plan_code: Optional[str]
    plan_status: Optional[str]
    usage: Optional[dict]

class WorkspaceListResponse(BaseModel):
    workspaces: List[WorkspaceItem]
    total: int

class JobItem(BaseModel):
    job_id: str
    next_run: Optional[str]
    trigger: Optional[str]

class SystemHealth(BaseModel):
    db_size_mb: float
    total_tables: int
    app_count: int
    keyword_count: int
    review_count: int
    pending_queue: int
    uptime_info: str


# ═══════════════════════════════════════════════════════════════════════════════
# Dashboard Overview
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard", response_model=DashboardStats)
def admin_dashboard(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_superadmin),
):
    """High-level stats for the admin dashboard."""
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    total_workspaces = db.query(func.count(Workspace.id)).scalar() or 0
    total_apps = db.query(func.count(App.id)).scalar() or 0

    # Keywords count
    try:
        total_keywords = db.execute(text("SELECT COUNT(*) FROM keywords")).scalar() or 0
    except Exception:
        total_keywords = 0

    # Reviews count
    try:
        total_reviews = db.execute(text("SELECT COUNT(*) FROM reviews")).scalar() or 0
    except Exception:
        total_reviews = 0

    # Plan breakdown
    plan_rows = (
        db.query(Subscription.plan_code, func.count(Subscription.id))
        .group_by(Subscription.plan_code)
        .all()
    )
    plans = {row[0]: row[1] for row in plan_rows}

    # This month usage totals
    month_str = datetime.now(timezone.utc).strftime("%Y-%m")
    usage_rows = (
        db.query(
            func.sum(WorkspaceUsage.app_imports),
            func.sum(WorkspaceUsage.keyword_refreshes),
            func.sum(WorkspaceUsage.ai_requests),
            func.sum(WorkspaceUsage.exports),
        )
        .filter(WorkspaceUsage.month == month_str)
        .first()
    )
    usage = {
        "app_imports": usage_rows[0] or 0 if usage_rows else 0,
        "keyword_refreshes": usage_rows[1] or 0 if usage_rows else 0,
        "ai_requests": usage_rows[2] or 0 if usage_rows else 0,
        "exports": usage_rows[3] or 0 if usage_rows else 0,
    }

    return DashboardStats(
        total_users=total_users,
        active_users=active_users,
        total_workspaces=total_workspaces,
        total_apps=total_apps,
        total_keywords=total_keywords,
        total_reviews=total_reviews,
        plans=plans,
        usage_this_month=usage,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# User Management
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/users", response_model=UserListResponse)
def list_users(
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_superadmin),
):
    """List all users with workspace/plan info."""
    q = (
        db.query(User, Workspace, Membership, Subscription)
        .outerjoin(Membership, Membership.user_id == User.id)
        .outerjoin(Workspace, Workspace.id == Membership.workspace_id)
        .outerjoin(Subscription, Subscription.workspace_id == Workspace.id)
    )
    if search:
        q = q.filter(
            User.email.ilike(f"%{search}%")
            | User.full_name.ilike(f"%{search}%")
        )

    total = q.with_entities(func.count(User.id)).scalar() or 0
    rows = q.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    users = []
    for user, ws, mem, sub in rows:
        users.append(UserItem(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_superadmin=user.is_superadmin,
            created_at=user.created_at.isoformat() if user.created_at else None,
            workspace_name=ws.name if ws else None,
            plan_code=sub.plan_code if sub else None,
            role=mem.role if mem else None,
        ))

    return UserListResponse(users=users, total=total)


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    body: dict,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_superadmin),
):
    """Update user fields: is_active, is_superadmin, full_name."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if "is_active" in body:
        user.is_active = bool(body["is_active"])
    if "is_superadmin" in body:
        user.is_superadmin = bool(body["is_superadmin"])
    if "full_name" in body:
        user.full_name = body["full_name"]

    db.commit()
    return {"ok": True, "user_id": user.id}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Delete a user (cannot delete self)."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Workspace Management
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/workspaces", response_model=WorkspaceListResponse)
def list_workspaces(
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_superadmin),
):
    """List all workspaces with owner, plan, and usage info."""
    q = db.query(Workspace)
    if search:
        q = q.filter(Workspace.name.ilike(f"%{search}%") | Workspace.slug.ilike(f"%{search}%"))

    total = q.count()
    workspaces = q.order_by(Workspace.created_at.desc()).offset(skip).limit(limit).all()

    month_str = datetime.now(timezone.utc).strftime("%Y-%m")
    items = []
    for ws in workspaces:
        # Owner
        owner_mem = (
            db.query(Membership)
            .filter(Membership.workspace_id == ws.id, Membership.role == "owner")
            .first()
        )
        owner_email = None
        if owner_mem:
            owner = db.query(User).filter(User.id == owner_mem.user_id).first()
            owner_email = owner.email if owner else None

        member_count = (
            db.query(func.count(Membership.id))
            .filter(Membership.workspace_id == ws.id)
            .scalar() or 0
        )

        sub = db.query(Subscription).filter(Subscription.workspace_id == ws.id).first()

        usage = db.query(WorkspaceUsage).filter(
            WorkspaceUsage.workspace_id == ws.id,
            WorkspaceUsage.month == month_str,
        ).first()

        items.append(WorkspaceItem(
            id=ws.id,
            name=ws.name,
            slug=ws.slug,
            created_at=ws.created_at.isoformat() if ws.created_at else None,
            owner_email=owner_email,
            member_count=member_count,
            plan_code=sub.plan_code if sub else None,
            plan_status=sub.status if sub else None,
            usage={
                "app_imports": usage.app_imports if usage else 0,
                "keyword_refreshes": usage.keyword_refreshes if usage else 0,
                "ai_requests": usage.ai_requests if usage else 0,
                "exports": usage.exports if usage else 0,
            },
        ))

    return WorkspaceListResponse(workspaces=items, total=total)


# ═══════════════════════════════════════════════════════════════════════════════
# Subscription Management
# ═══════════════════════════════════════════════════════════════════════════════

@router.patch("/subscriptions/{workspace_id}")
def update_subscription(
    workspace_id: int,
    body: dict,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_superadmin),
):
    """Change plan, status, or extend trial for a workspace."""
    sub = db.query(Subscription).filter(Subscription.workspace_id == workspace_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if "plan_code" in body:
        sub.plan_code = body["plan_code"]
    if "status" in body:
        sub.status = body["status"]
    if "trial_ends_at" in body:
        sub.trial_ends_at = datetime.fromisoformat(body["trial_ends_at"]) if body["trial_ends_at"] else None

    db.commit()
    return {"ok": True, "workspace_id": workspace_id, "plan_code": sub.plan_code, "status": sub.status}


# ═══════════════════════════════════════════════════════════════════════════════
# Jobs / Scheduler
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/jobs")
def list_jobs(
    _admin: User = Depends(get_superadmin),
):
    """List all scheduled jobs."""
    try:
        from app.workers.scheduler import scheduler
        jobs = scheduler.get_jobs()
        return {
            "jobs": [
                {
                    "job_id": j.id,
                    "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
                    "trigger": str(j.trigger),
                }
                for j in jobs
            ],
            "total": len(jobs),
        }
    except Exception as e:
        return {"jobs": [], "total": 0, "error": str(e)}


@router.post("/jobs/{job_id}/trigger")
def trigger_job(
    job_id: str,
    _admin: User = Depends(get_superadmin),
):
    """Trigger a scheduled job immediately."""
    try:
        from app.workers.scheduler import scheduler
        job = scheduler.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        job.modify(next_run_time=datetime.now(timezone.utc))
        return {"ok": True, "job_id": job_id, "status": "triggered"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# System Health
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/system", response_model=SystemHealth)
def system_health(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_superadmin),
):
    """System health overview."""
    # DB size
    try:
        row = db.execute(text(
            "SELECT pg_database_size(current_database()) / 1024.0 / 1024.0"
        )).scalar()
        db_size_mb = round(float(row or 0), 1)
    except Exception:
        db_size_mb = 0.0

    # Table count
    try:
        total_tables = db.execute(text(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
        )).scalar() or 0
    except Exception:
        total_tables = 0

    app_count = db.query(func.count(App.id)).scalar() or 0

    try:
        keyword_count = db.execute(text("SELECT COUNT(*) FROM keywords")).scalar() or 0
    except Exception:
        keyword_count = 0

    try:
        review_count = db.execute(text("SELECT COUNT(*) FROM reviews")).scalar() or 0
    except Exception:
        review_count = 0

    try:
        pending_queue = db.execute(text(
            "SELECT COUNT(*) FROM keyword_queue WHERE status = 'pending'"
        )).scalar() or 0
    except Exception:
        pending_queue = 0

    return SystemHealth(
        db_size_mb=db_size_mb,
        total_tables=total_tables,
        app_count=app_count,
        keyword_count=keyword_count,
        review_count=review_count,
        pending_queue=pending_queue,
        uptime_info="Running",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Quick Actions
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/promote/{user_id}")
def promote_to_superadmin(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_superadmin),
):
    """Promote a user to superadmin."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_superadmin = True
    db.commit()
    return {"ok": True, "user_id": user.id, "email": user.email}
