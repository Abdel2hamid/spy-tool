"""
Admin Console Router
====================
CRUD endpoints for superadmin management of users, workspaces,
subscriptions, usage, scheduled jobs, system health, activity log,
announcements, and impersonation.

All endpoints require a user with is_superadmin=True.
"""
from __future__ import annotations

import csv
import io
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_superadmin
from app.models.models import (
    App, User, Workspace, Membership, Subscription, WorkspaceUsage,
    Favorite, MyApp, AdminActivityLog, AdminSetting, Announcement, UserActivityLog,
)
from app.services.data_quality_metrics import get_data_quality_metrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin-console", tags=["admin-console"])


# ═══════════════════════════════════════════════════════════════════════════════
# Activity log helper
# ═══════════════════════════════════════════════════════════════════════════════

def _log_activity(
    db: Session,
    admin: User,
    action: str,
    target_type: str = None,
    target_id: int = None,
    details: dict = None,
):
    """Record an admin action in the audit log."""
    entry = AdminActivityLog(
        admin_id=admin.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )
    db.add(entry)
    db.commit()


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
    plans: dict
    usage_this_month: dict
    revenue: dict
    trial_funnel: dict
    usage_leaderboard: List[dict]
    billing_log: List[dict]

class UserItem(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    is_superadmin: bool
    created_at: Optional[str]
    workspace_id: Optional[int]
    workspace_name: Optional[str]
    workspace_slug: Optional[str]
    plan_code: Optional[str]
    plan_status: Optional[str]
    trial_ends_at: Optional[str]
    trial_days_left: Optional[int]
    role: Optional[str]
    usage: Optional[dict]

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

class CreateUserRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    plan_code: Optional[str] = None

class ResetPasswordRequest(BaseModel):
    new_password: str

class BulkActionRequest(BaseModel):
    user_ids: List[int]
    action: str  # "deactivate" | "activate" | "delete" | "change_plan"
    plan_code: Optional[str] = None

class AnnouncementCreate(BaseModel):
    title: str
    message: str
    type: str = "info"  # info | warning | success

class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    type: Optional[str] = None
    is_active: Optional[bool] = None

class ActivityItem(BaseModel):
    id: int
    admin_email: Optional[str]
    action: str
    target_type: Optional[str]
    target_id: Optional[int]
    details: Optional[dict]
    created_at: Optional[str]

class TrialItem(BaseModel):
    workspace_id: int
    workspace_name: str
    owner_email: Optional[str]
    plan_code: str
    status: str
    trial_ends_at: Optional[str]
    days_left: Optional[int]


# ═══════════════════════════════════════════════════════════════════════════════
# Dashboard Overview
# ═══════════════════════════════════════════════════════════════════════════════

PLAN_PRICES: dict[str, float] = {
    "starter": 19.99,
    "pro": 49.99,
}


@router.get("/dashboard", response_model=DashboardStats)
def admin_dashboard(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_superadmin),
):
    """High-level stats for the admin dashboard."""
    # Exclude superadmins from user counts — they are not customers
    total_users = db.query(func.count(User.id)).filter(User.is_superadmin == False).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True, User.is_superadmin == False).scalar() or 0
    total_workspaces = db.query(func.count(Workspace.id)).scalar() or 0
    total_apps = db.query(func.count(App.id)).scalar() or 0

    try:
        total_keywords = db.execute(text("SELECT COUNT(*) FROM keywords")).scalar() or 0
    except Exception:
        total_keywords = 0

    try:
        total_reviews = db.execute(text("SELECT COUNT(*) FROM reviews")).scalar() or 0
    except Exception:
        total_reviews = 0

    # --- Plan distribution (one subscription per workspace, exclude superadmin workspaces) ---
    admin_workspace_ids = (
        db.query(Membership.workspace_id)
        .join(User, User.id == Membership.user_id)
        .filter(User.is_superadmin == True)
        .subquery()
    )
    base_sub_filter = Subscription.workspace_id.notin_(admin_workspace_ids)

    plan_rows = (
        db.query(Subscription.plan_code, Subscription.status, func.count(Subscription.id))
        .filter(base_sub_filter)
        .group_by(Subscription.plan_code, Subscription.status)
        .all()
    )
    plans: dict[str, int] = {}
    for code, _status, cnt in plan_rows:
        plans[code] = plans.get(code, 0) + cnt

    # --- Revenue (MRR estimate — only paid plans, exclude lifetime & trial) ---
    now = datetime.now(timezone.utc)
    mrr = 0.0
    mrr_breakdown: dict[str, dict] = {}
    active_subs = (
        db.query(Subscription.plan_code, func.count(Subscription.id))
        .filter(
            base_sub_filter,
            Subscription.status == "active",
            Subscription.plan_code.notin_(["trial", "lifetime"]),
        )
        .group_by(Subscription.plan_code)
        .all()
    )
    for code, cnt in active_subs:
        price = PLAN_PRICES.get(code, 0)
        plan_mrr = price * cnt
        mrr += plan_mrr
        mrr_breakdown[code] = {"count": cnt, "price": price, "mrr": plan_mrr}

    revenue = {
        "mrr": round(mrr, 2),
        "arr": round(mrr * 12, 2),
        "breakdown": mrr_breakdown,
        "total_paying": sum(r["count"] for r in mrr_breakdown.values()),
    }

    # --- Trial conversion funnel (exclude superadmin workspaces) ---
    # Active trials = trialing AND trial hasn't expired yet
    active_trials = db.query(func.count(Subscription.id)).filter(
        base_sub_filter,
        Subscription.status == "trialing",
        Subscription.trial_ends_at >= now,
    ).scalar() or 0
    # Converted = active with a paid plan
    converted = db.query(func.count(Subscription.id)).filter(
        base_sub_filter,
        Subscription.status == "active",
        Subscription.plan_code.notin_(["trial", "lifetime"]),
    ).scalar() or 0
    # Lifetime grants
    lifetime_count = db.query(func.count(Subscription.id)).filter(
        base_sub_filter,
        Subscription.plan_code == "lifetime",
    ).scalar() or 0
    # Expired = trialing but trial_ends_at has passed
    expired_trials = db.query(func.count(Subscription.id)).filter(
        base_sub_filter,
        Subscription.status == "trialing",
        Subscription.trial_ends_at < now,
    ).scalar() or 0
    # Total = all non-admin subscriptions
    total_subs = active_trials + converted + lifetime_count + expired_trials

    trial_funnel = {
        "total_trials": total_subs,
        "active_trials": active_trials,
        "converted": converted,
        "expired": expired_trials,
        "lifetime": lifetime_count,
        "conversion_rate": round(converted / max(total_subs, 1) * 100, 1),
    }

    # --- Usage this month ---
    month_str = now.strftime("%Y-%m")
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

    # --- Usage leaderboard (top 10 heaviest users this month) ---
    leaderboard_rows = (
        db.query(
            User.id,
            User.email,
            User.full_name,
            Subscription.plan_code,
            WorkspaceUsage.app_imports,
            WorkspaceUsage.keyword_refreshes,
            WorkspaceUsage.ai_requests,
            WorkspaceUsage.exports,
        )
        .join(Membership, Membership.user_id == User.id)
        .join(WorkspaceUsage, WorkspaceUsage.workspace_id == Membership.workspace_id)
        .outerjoin(Subscription, Subscription.workspace_id == Membership.workspace_id)
        .filter(WorkspaceUsage.month == month_str)
        .order_by(
            (
                WorkspaceUsage.app_imports
                + WorkspaceUsage.keyword_refreshes
                + WorkspaceUsage.ai_requests
                + WorkspaceUsage.exports
            ).desc()
        )
        .limit(10)
        .all()
    )
    usage_leaderboard = [
        {
            "user_id": r[0],
            "email": r[1],
            "full_name": r[2],
            "plan_code": r[3],
            "app_imports": r[4] or 0,
            "keyword_refreshes": r[5] or 0,
            "ai_requests": r[6] or 0,
            "exports": r[7] or 0,
            "total": (r[4] or 0) + (r[5] or 0) + (r[6] or 0) + (r[7] or 0),
        }
        for r in leaderboard_rows
    ]

    # --- Recent billing log (plan changes, trial extensions from admin activity) ---
    billing_actions = (
        db.query(AdminActivityLog, User)
        .outerjoin(User, User.id == AdminActivityLog.admin_id)
        .filter(
            AdminActivityLog.action.in_([
                "subscription.update", "trial.extend", "user.bulk_change_plan",
                "user.create",
            ])
        )
        .order_by(AdminActivityLog.created_at.desc())
        .limit(15)
        .all()
    )
    billing_log = [
        {
            "id": log.id,
            "admin_email": admin_user.email if admin_user else None,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "details": log.details,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log, admin_user in billing_actions
    ]

    return DashboardStats(
        total_users=total_users,
        active_users=active_users,
        total_workspaces=total_workspaces,
        total_apps=total_apps,
        total_keywords=total_keywords,
        total_reviews=total_reviews,
        plans=plans,
        usage_this_month=usage,
        revenue=revenue,
        trial_funnel=trial_funnel,
        usage_leaderboard=usage_leaderboard,
        billing_log=billing_log,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# User Management
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/users", response_model=UserListResponse)
def list_users(
    search: Optional[str] = None,
    filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_superadmin),
):
    """List all users with workspace/plan/trial/usage info."""
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

    now = datetime.now(timezone.utc)

    if filter == "trialing":
        q = q.filter(Subscription.status == "trialing")
    elif filter == "expired":
        q = q.filter(
            Subscription.status == "trialing",
            Subscription.trial_ends_at < now,
        )
    elif filter == "inactive":
        q = q.filter(User.is_active == False)

    total = q.with_entities(func.count(User.id)).scalar() or 0
    rows = q.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    month_str = now.strftime("%Y-%m")
    users = []
    for user, ws, mem, sub in rows:
        trial_days_left = None
        trial_ends_at_str = None
        if sub and sub.status == "trialing" and sub.trial_ends_at:
            trial_end = sub.trial_ends_at
            if trial_end.tzinfo is None:
                trial_end = trial_end.replace(tzinfo=timezone.utc)
            trial_days_left = max(0, (trial_end - now).days)
            trial_ends_at_str = sub.trial_ends_at.isoformat()

        usage_data = None
        if ws:
            usage = db.query(WorkspaceUsage).filter(
                WorkspaceUsage.workspace_id == ws.id,
                WorkspaceUsage.month == month_str,
            ).first()
            usage_data = {
                "app_imports": usage.app_imports if usage else 0,
                "keyword_refreshes": usage.keyword_refreshes if usage else 0,
                "ai_requests": usage.ai_requests if usage else 0,
                "exports": usage.exports if usage else 0,
            }

        users.append(UserItem(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_superadmin=user.is_superadmin,
            created_at=user.created_at.isoformat() if user.created_at else None,
            workspace_id=ws.id if ws else None,
            workspace_name=ws.name if ws else None,
            workspace_slug=ws.slug if ws else None,
            plan_code=sub.plan_code if sub else None,
            plan_status=sub.status if sub else None,
            trial_ends_at=trial_ends_at_str,
            trial_days_left=trial_days_left,
            role=mem.role if mem else None,
            usage=usage_data,
        ))

    return UserListResponse(users=users, total=total)


@router.post("/users", status_code=201)
def create_user(
    body: CreateUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Admin-create a user with workspace + subscription."""
    from app.services.auth_service import register_user, EmailAlreadyRegistered

    try:
        user, workspace, _token = register_user(
            db, email=body.email, password=body.password, full_name=body.full_name,
        )
    except EmailAlreadyRegistered:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Admin-provisioned users never receive a verification email — without
    # this flag they could never log in (login rejects unverified users).
    user.email_verified = True
    db.commit()

    if body.plan_code:
        sub = db.query(Subscription).filter(Subscription.workspace_id == workspace.id).first()
        if sub:
            sub.plan_code = body.plan_code
            if body.plan_code != "trial":
                sub.status = "active"
            db.commit()

    _log_activity(db, admin, "user.create", "user", user.id, {"email": body.email, "plan": body.plan_code})
    return {"ok": True, "user_id": user.id, "email": user.email}


class AdminUserUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_superadmin: Optional[bool] = None
    full_name: Optional[str] = None


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    body: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Update user fields: is_active, is_superadmin, full_name."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    changes = {}
    if body.is_active is not None:
        user.is_active = body.is_active
        changes["is_active"] = user.is_active
    if body.is_superadmin is not None:
        user.is_superadmin = body.is_superadmin
        changes["is_superadmin"] = user.is_superadmin
    if body.full_name is not None:
        user.full_name = body.full_name
        changes["full_name"] = user.full_name

    db.commit()
    _log_activity(db, admin, "user.update", "user", user_id, {"changes": changes, "email": user.email})
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
    email = user.email
    db.delete(user)
    db.commit()
    _log_activity(db, admin, "user.delete", "user", user_id, {"email": email})
    return {"ok": True}


@router.get("/users/{user_id}/detail")
def get_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_superadmin),
):
    """Full user profile with workspace, subscription, apps, favorites, usage, activity."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(timezone.utc)
    month_str = now.strftime("%Y-%m")

    # Membership + workspace + subscription
    mem = db.query(Membership).filter(Membership.user_id == user.id).first()
    ws = db.query(Workspace).filter(Workspace.id == mem.workspace_id).first() if mem else None
    sub = db.query(Subscription).filter(Subscription.workspace_id == ws.id).first() if ws else None

    trial_days_left = None
    if sub and sub.status == "trialing" and sub.trial_ends_at:
        trial_end = sub.trial_ends_at
        if trial_end.tzinfo is None:
            trial_end = trial_end.replace(tzinfo=timezone.utc)
        trial_days_left = max(0, (trial_end - now).days)

    # Usage this month
    usage_data = None
    if ws:
        usage = db.query(WorkspaceUsage).filter(
            WorkspaceUsage.workspace_id == ws.id,
            WorkspaceUsage.month == month_str,
        ).first()
        usage_data = {
            "app_imports": usage.app_imports if usage else 0,
            "keyword_refreshes": usage.keyword_refreshes if usage else 0,
            "ai_requests": usage.ai_requests if usage else 0,
            "exports": usage.exports if usage else 0,
        }

    # Favorites
    fav_rows = (
        db.query(Favorite, App)
        .join(App, App.id == Favorite.app_id)
        .filter(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc())
        .limit(50)
        .all()
    )
    favorites = [
        {
            "app_id": app.id,
            "name": app.name,
            "icon_url": app.icon_url,
            "developer": app.developer,
            "added_at": fav.created_at.isoformat() if fav.created_at else None,
        }
        for fav, app in fav_rows
    ]

    # My Apps
    myapp_rows = (
        db.query(MyApp, App)
        .join(App, App.id == MyApp.app_id)
        .filter(MyApp.user_id == user.id)
        .order_by(MyApp.created_at.desc())
        .limit(50)
        .all()
    )
    my_apps = [
        {
            "app_id": app.id,
            "name": app.name,
            "icon_url": app.icon_url,
            "developer": app.developer,
            "added_at": ma.created_at.isoformat() if ma.created_at else None,
        }
        for ma, app in myapp_rows
    ]

    # Recent activity (last 50)
    act_rows = (
        db.query(UserActivityLog)
        .filter(UserActivityLog.user_id == user.id)
        .order_by(UserActivityLog.created_at.desc())
        .limit(50)
        .all()
    )
    activity = [
        {
            "id": r.id,
            "action": r.action,
            "detail": r.detail,
            "metadata": r.metadata_,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in act_rows
    ]

    # Last active (most recent activity)
    last_active = None
    if act_rows:
        last_active = act_rows[0].created_at.isoformat() if act_rows[0].created_at else None

    # Admin actions targeting this user
    admin_actions = (
        db.query(AdminActivityLog, User)
        .outerjoin(User, User.id == AdminActivityLog.admin_id)
        .filter(
            AdminActivityLog.target_type == "user",
            AdminActivityLog.target_id == user_id,
        )
        .order_by(AdminActivityLog.created_at.desc())
        .limit(20)
        .all()
    )
    admin_log = [
        {
            "id": log.id,
            "admin_email": admin_u.email if admin_u else None,
            "action": log.action,
            "details": log.details,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log, admin_u in admin_actions
    ]

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_superadmin": user.is_superadmin,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_active": last_active,
        },
        "workspace": {
            "id": ws.id,
            "name": ws.name,
            "slug": ws.slug,
            "role": mem.role if mem else None,
            "created_at": ws.created_at.isoformat() if ws.created_at else None,
        } if ws else None,
        "subscription": {
            "plan_code": sub.plan_code,
            "status": sub.status,
            "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
            "trial_days_left": trial_days_left,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        } if sub else None,
        "usage": usage_data,
        "favorites": favorites,
        "favorite_count": len(favorites),
        "my_apps": my_apps,
        "my_app_count": len(my_apps),
        "activity": activity,
        "activity_count": len(activity),
        "admin_log": admin_log,
    }


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Reset a user's password (admin override — no current password needed)."""
    from app.services.auth_service import hash_password
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    _log_activity(db, admin, "user.reset_password", "user", user_id, {"email": user.email})
    return {"ok": True}


@router.post("/users/{user_id}/impersonate")
def impersonate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Generate a temporary JWT token for a target user (login-as)."""
    from app.services.auth_service import create_access_token
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_superadmin:
        raise HTTPException(status_code=400, detail="Cannot impersonate another superadmin")

    mem = db.query(Membership).filter(Membership.user_id == user.id).first()
    if not mem:
        raise HTTPException(status_code=400, detail="User has no workspace")

    token = create_access_token(
        user.id, mem.workspace_id,
        is_impersonation=True,
        impersonator_id=admin.id,
    )
    _log_activity(db, admin, "user.impersonate", "user", user_id, {"email": user.email})
    return {"ok": True, "token": token, "email": user.email}


@router.post("/users/bulk")
def bulk_user_action(
    body: BulkActionRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Perform bulk action on multiple users."""
    if not body.user_ids:
        raise HTTPException(status_code=400, detail="No user IDs provided")

    users = db.query(User).filter(User.id.in_(body.user_ids)).all()
    affected = 0

    if body.action == "activate":
        for u in users:
            u.is_active = True
            affected += 1
        db.commit()

    elif body.action == "deactivate":
        for u in users:
            if u.id != admin.id:
                u.is_active = False
                affected += 1
        db.commit()

    elif body.action == "delete":
        for u in users:
            if u.id != admin.id:
                db.delete(u)
                affected += 1
        db.commit()

    elif body.action == "change_plan":
        if not body.plan_code:
            raise HTTPException(status_code=400, detail="plan_code required for change_plan")
        for u in users:
            mem = db.query(Membership).filter(Membership.user_id == u.id).first()
            if mem:
                sub = db.query(Subscription).filter(Subscription.workspace_id == mem.workspace_id).first()
                if sub:
                    sub.plan_code = body.plan_code
                    if body.plan_code != "trial":
                        sub.status = "active"
                    affected += 1
        db.commit()

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")

    _log_activity(db, admin, f"user.bulk_{body.action}", "user", None, {
        "user_ids": body.user_ids, "affected": affected, "plan_code": body.plan_code,
    })
    return {"ok": True, "affected": affected}


# ═══════════════════════════════════════════════════════════════════════════════
# User Activity History
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/users/{user_id}/activity")
def get_user_activity(
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_superadmin),
):
    """Get activity history for a specific user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    total = db.query(func.count(UserActivityLog.id)).filter(
        UserActivityLog.user_id == user_id
    ).scalar() or 0

    rows = (
        db.query(UserActivityLog)
        .filter(UserActivityLog.user_id == user_id)
        .order_by(UserActivityLog.created_at.desc())
        .offset(skip).limit(limit)
        .all()
    )

    return {
        "user_id": user_id,
        "email": user.email,
        "full_name": user.full_name,
        "activity": [
            {
                "id": r.id,
                "action": r.action,
                "detail": r.detail,
                "metadata": r.metadata_,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "total": total,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CSV Export
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/export/users")
def export_users_csv(
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Export all users as CSV download."""
    rows = (
        db.query(User, Workspace, Membership, Subscription)
        .outerjoin(Membership, Membership.user_id == User.id)
        .outerjoin(Workspace, Workspace.id == Membership.workspace_id)
        .outerjoin(Subscription, Subscription.workspace_id == Workspace.id)
        .order_by(User.created_at.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Email", "Full Name", "Active", "Superadmin", "Workspace", "Plan", "Role", "Created"])

    for user, ws, mem, sub in rows:
        writer.writerow([
            user.id, user.email, user.full_name or "",
            user.is_active, user.is_superadmin,
            ws.name if ws else "", sub.plan_code if sub else "",
            mem.role if mem else "", user.created_at.isoformat() if user.created_at else "",
        ])

    output.seek(0)
    _log_activity(db, admin, "export.users", details={"count": len(rows)})
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=users_{datetime.now().strftime('%Y%m%d')}.csv"},
    )


@router.get("/export/workspaces")
def export_workspaces_csv(
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Export all workspaces as CSV download."""
    workspaces = db.query(Workspace).order_by(Workspace.created_at.desc()).all()
    month_str = datetime.now(timezone.utc).strftime("%Y-%m")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Slug", "Owner Email", "Members", "Plan", "Status", "App Imports", "KW Refreshes", "AI Reqs", "Created"])

    for ws in workspaces:
        owner_mem = db.query(Membership).filter(Membership.workspace_id == ws.id, Membership.role == "owner").first()
        owner_email = ""
        if owner_mem:
            owner = db.query(User).filter(User.id == owner_mem.user_id).first()
            owner_email = owner.email if owner else ""
        member_count = db.query(func.count(Membership.id)).filter(Membership.workspace_id == ws.id).scalar() or 0
        sub = db.query(Subscription).filter(Subscription.workspace_id == ws.id).first()
        usage = db.query(WorkspaceUsage).filter(WorkspaceUsage.workspace_id == ws.id, WorkspaceUsage.month == month_str).first()

        writer.writerow([
            ws.id, ws.name, ws.slug, owner_email, member_count,
            sub.plan_code if sub else "", sub.status if sub else "",
            usage.app_imports if usage else 0, usage.keyword_refreshes if usage else 0,
            usage.ai_requests if usage else 0,
            ws.created_at.isoformat() if ws.created_at else "",
        ])

    output.seek(0)
    _log_activity(db, admin, "export.workspaces", details={"count": len(workspaces)})
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=workspaces_{datetime.now().strftime('%Y%m%d')}.csv"},
    )


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
# Subscription / Trial Management
# ═══════════════════════════════════════════════════════════════════════════════

class AdminSubscriptionUpdate(BaseModel):
    plan_code: Optional[str] = None
    status: Optional[str] = None
    trial_ends_at: Optional[str] = None

    @field_validator("plan_code")
    @classmethod
    def valid_plan_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("free", "starter", "pro", "trial", "lifetime"):
            raise ValueError("Invalid plan code")
        return v

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("trialing", "active", "past_due", "canceled", "pending_payment"):
            raise ValueError("Invalid status")
        return v


@router.patch("/subscriptions/{workspace_id}")
def update_subscription(
    workspace_id: int,
    body: AdminSubscriptionUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Change plan, status, or extend trial for a workspace."""
    sub = db.query(Subscription).filter(Subscription.workspace_id == workspace_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    changes = {}
    if body.plan_code is not None:
        sub.plan_code = body.plan_code
        changes["plan_code"] = body.plan_code
    if body.status is not None:
        sub.status = body.status
        changes["status"] = body.status
    if body.trial_ends_at is not None:
        sub.trial_ends_at = datetime.fromisoformat(body.trial_ends_at) if body.trial_ends_at else None
        changes["trial_ends_at"] = body.trial_ends_at

    db.commit()
    _log_activity(db, admin, "subscription.update", "workspace", workspace_id, changes)
    return {"ok": True, "workspace_id": workspace_id, "plan_code": sub.plan_code, "status": sub.status}


@router.get("/trials")
def list_trials(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_superadmin),
):
    """List all trialing workspaces with days remaining."""
    subs = (
        db.query(Subscription, Workspace)
        .join(Workspace, Workspace.id == Subscription.workspace_id)
        .filter(Subscription.status == "trialing")
        .order_by(Subscription.trial_ends_at.asc())
        .all()
    )

    now = datetime.now(timezone.utc)
    items = []
    for sub, ws in subs:
        owner_mem = db.query(Membership).filter(
            Membership.workspace_id == ws.id, Membership.role == "owner"
        ).first()
        owner_email = None
        if owner_mem:
            owner = db.query(User).filter(User.id == owner_mem.user_id).first()
            owner_email = owner.email if owner else None

        days_left = None
        if sub.trial_ends_at:
            trial_end = sub.trial_ends_at
            if trial_end.tzinfo is None:
                trial_end = trial_end.replace(tzinfo=timezone.utc)
            days_left = max(0, (trial_end - now).days)

        items.append(TrialItem(
            workspace_id=ws.id,
            workspace_name=ws.name,
            owner_email=owner_email,
            plan_code=sub.plan_code,
            status=sub.status,
            trial_ends_at=sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
            days_left=days_left,
        ))

    return {"trials": items, "total": len(items)}


@router.post("/trials/{workspace_id}/extend")
def extend_trial(
    workspace_id: int,
    days: int = Query(default=14, ge=1, le=36500),
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Extend a workspace's trial by N days from now, or grant lifetime access."""
    sub = db.query(Subscription).filter(Subscription.workspace_id == workspace_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if days >= 36500:
        # Lifetime: remove trial end, set active permanently with "lifetime" plan
        sub.trial_ends_at = None
        sub.status = "active"
        sub.plan_code = "lifetime"
        db.commit()
        _log_activity(db, admin, "trial.extend", "workspace", workspace_id, {"days": "lifetime"})
        return {"ok": True, "trial_ends_at": None, "days": "lifetime"}
    else:
        new_end = datetime.now(timezone.utc) + timedelta(days=days)
        sub.trial_ends_at = new_end
        sub.status = "trialing"
        sub.plan_code = "trial"
        db.commit()
        _log_activity(db, admin, "trial.extend", "workspace", workspace_id, {"days": days})
        return {"ok": True, "trial_ends_at": new_end.isoformat(), "days": days}


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
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Trigger a scheduled job immediately."""
    try:
        from app.workers.scheduler import scheduler
        job = scheduler.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        job.modify(next_run_time=datetime.now(timezone.utc))
        _log_activity(db, admin, "job.trigger", "job", None, {"job_id": job_id})
        return {"ok": True, "job_id": job_id, "status": "triggered"}
    except HTTPException:
        raise
    except Exception as e:
        import logging as _lg
        _lg.getLogger(__name__).exception("Job trigger error: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/job-metrics")
def get_job_metrics_endpoint(
    _admin: User = Depends(get_superadmin),
):
    """Return execution metrics for all jobs (runs, ok, fail, timeout, durations)."""
    try:
        from app.workers.scheduler import get_job_metrics
        metrics = get_job_metrics()
        return {"metrics": metrics, "total": len(metrics)}
    except Exception as e:
        return {"metrics": {}, "total": 0, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# Force Re-scrape
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/apps/{app_id}/rescrape")
def force_rescrape(
    app_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Trigger full data refresh for an app (scrape + reviews + keywords)."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    def _run_scrape():
        try:
            from app.database import SessionLocal
            from app.services.post_import_hydration import PostImportHydrationService
            sess = SessionLocal()
            try:
                svc = PostImportHydrationService(sess)
                svc._step_full_scrape(app.id)
                svc._step_reviews(app.id)
                svc._step_keywords(app.id)
            finally:
                sess.close()
        except Exception as exc:
            logger.error("Admin rescrape failed for app %s: %s", app_id, exc)

    t = threading.Thread(target=_run_scrape, daemon=True)
    t.start()

    _log_activity(db, admin, "app.rescrape", "app", app_id, {"name": app.name, "apple_id": app.app_id})
    return {"ok": True, "app_id": app_id, "name": app.name}


@router.post("/apps/bulk-backfill")
def bulk_backfill_apps(
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
    batch_size: int = Query(default=200, ge=50, le=1000),
):
    """
    Fast bulk backfill for apps missing descriptions.
    Uses iTunes batch lookup API (200 IDs per request) instead of
    individual full scrapes — ~100x faster than the scheduled job.
    Runs synchronously in a background thread; returns immediately.
    """
    incomplete_count = (
        db.query(func.count(App.id))
        .filter(App.description.is_(None))
        .scalar() or 0
    )
    if incomplete_count == 0:
        return {"ok": True, "message": "No incomplete apps found", "total_incomplete": 0}

    def _run_bulk_backfill():
        import urllib.request
        import json as _json
        from app.database import SessionLocal

        sess = SessionLocal()
        total_updated = 0
        try:
            # Process in batches of 200 (iTunes API limit)
            while True:
                rows = (
                    sess.query(App)
                    .filter(App.description.is_(None))
                    .order_by(App.created_at.desc())
                    .limit(200)
                    .all()
                )
                if not rows:
                    break

                store_ids = [a.app_id for a in rows]
                app_map = {str(a.app_id): a for a in rows}

                # Batch iTunes lookup (comma-separated IDs)
                ids_param = ",".join(str(sid) for sid in store_ids)
                url = f"https://itunes.apple.com/lookup?id={ids_param}&country=us&entity=software"
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "RankSpy/1.0"})
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        data = _json.loads(resp.read().decode())
                except Exception as e:
                    logger.error(f"[BULK-BACKFILL] iTunes batch lookup failed: {e}")
                    break

                results = data.get("results", [])
                batch_updated = 0
                for r in results:
                    track_id = str(r.get("trackId", ""))
                    app_obj = app_map.get(track_id)
                    if not app_obj:
                        continue

                    app_obj.description = r.get("description") or app_obj.description
                    app_obj.subtitle = r.get("subtitle") or app_obj.subtitle
                    app_obj.developer = r.get("sellerName") or r.get("artistName") or app_obj.developer
                    app_obj.developer_id = str(r.get("artistId", "")) or app_obj.developer_id
                    app_obj.icon_url = r.get("artworkUrl512") or r.get("artworkUrl100") or app_obj.icon_url
                    genres = r.get("genres", [])
                    app_obj.primary_category = r.get("primaryGenreName") or (genres[0] if genres else None) or app_obj.primary_category
                    app_obj.secondary_category = (genres[1] if len(genres) > 1 else None) or app_obj.secondary_category
                    app_obj.current_rating = r.get("averageUserRating") or app_obj.current_rating
                    app_obj.current_reviews = r.get("userRatingCount") or app_obj.current_reviews or 0
                    app_obj.current_version = r.get("version") or app_obj.current_version
                    app_obj.content_rating = r.get("contentAdvisoryRating") or app_obj.content_rating
                    app_obj.is_free = r.get("price", 0) == 0
                    app_obj.price = r.get("price", 0)
                    app_obj.currency = r.get("currency", "USD")
                    screenshots = r.get("screenshotUrls", []) + r.get("ipadScreenshotUrls", [])
                    if screenshots:
                        app_obj.screenshots = screenshots
                    if r.get("releaseDate"):
                        try:
                            app_obj.release_date = datetime.fromisoformat(r["releaseDate"].replace("Z", "+00:00"))
                        except Exception:
                            pass
                    if r.get("currentVersionReleaseDate"):
                        try:
                            app_obj.last_updated = datetime.fromisoformat(r["currentVersionReleaseDate"].replace("Z", "+00:00"))
                        except Exception:
                            pass
                    app_obj.url = r.get("trackViewUrl") or app_obj.url
                    batch_updated += 1

                sess.commit()
                total_updated += batch_updated
                logger.info(f"[BULK-BACKFILL] Batch done: {batch_updated} updated, {total_updated} total so far")

                if total_updated >= batch_size:
                    break

            logger.info(f"[BULK-BACKFILL] Complete: {total_updated} apps updated")
        except Exception as exc:
            logger.error(f"[BULK-BACKFILL] Failed: {exc}")
            sess.rollback()
        finally:
            sess.close()

    t = threading.Thread(target=_run_bulk_backfill, daemon=True)
    t.start()

    _log_activity(db, admin, "apps.bulk_backfill", details={"batch_size": batch_size, "total_incomplete": incomplete_count})
    return {
        "ok": True,
        "message": f"Bulk backfill started for up to {batch_size} apps",
        "total_incomplete": incomplete_count,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# System Health
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/system", response_model=SystemHealth)
def system_health(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_superadmin),
):
    """System health overview."""
    try:
        row = db.execute(text(
            "SELECT pg_database_size(current_database()) / 1024.0 / 1024.0"
        )).scalar()
        db_size_mb = round(float(row or 0), 1)
    except Exception:
        db_size_mb = 0.0

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
# Activity Log
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/activity")
def list_activity(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_superadmin),
):
    """List admin activity log entries."""
    total = db.query(func.count(AdminActivityLog.id)).scalar() or 0
    rows = (
        db.query(AdminActivityLog, User)
        .outerjoin(User, User.id == AdminActivityLog.admin_id)
        .order_by(AdminActivityLog.created_at.desc())
        .offset(skip).limit(limit)
        .all()
    )

    items = []
    for log, admin_user in rows:
        items.append(ActivityItem(
            id=log.id,
            admin_email=admin_user.email if admin_user else None,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            details=log.details,
            created_at=log.created_at.isoformat() if log.created_at else None,
        ))

    return {"activity": items, "total": total}


# ═══════════════════════════════════════════════════════════════════════════════
# Announcements
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/announcements")
def list_announcements(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_superadmin),
):
    """List all announcements (admin view)."""
    rows = db.query(Announcement).order_by(Announcement.created_at.desc()).all()
    return {
        "announcements": [
            {
                "id": a.id,
                "title": a.title,
                "message": a.message,
                "type": a.type,
                "is_active": a.is_active,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in rows
        ],
        "total": len(rows),
    }


@router.post("/announcements", status_code=201)
def create_announcement(
    body: AnnouncementCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Create a new announcement."""
    ann = Announcement(
        title=body.title,
        message=body.message,
        type=body.type,
        is_active=True,
        created_by=admin.id,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    _log_activity(db, admin, "announcement.create", "announcement", ann.id, {"title": body.title})
    return {"ok": True, "id": ann.id}


@router.patch("/announcements/{ann_id}")
def update_announcement(
    ann_id: int,
    body: AnnouncementUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Update an announcement."""
    ann = db.query(Announcement).filter(Announcement.id == ann_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")

    if body.title is not None:
        ann.title = body.title
    if body.message is not None:
        ann.message = body.message
    if body.type is not None:
        ann.type = body.type
    if body.is_active is not None:
        ann.is_active = body.is_active

    db.commit()
    _log_activity(db, admin, "announcement.update", "announcement", ann_id)
    return {"ok": True}


@router.delete("/announcements/{ann_id}")
def delete_announcement(
    ann_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Delete an announcement."""
    ann = db.query(Announcement).filter(Announcement.id == ann_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")
    db.delete(ann)
    db.commit()
    _log_activity(db, admin, "announcement.delete", "announcement", ann_id)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Public: Active Announcements (for regular users)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/announcements/active")
def get_active_announcements(
    db: Session = Depends(get_db),
):
    """Return active announcements (no auth required — shown to all logged-in users)."""
    rows = (
        db.query(Announcement)
        .filter(Announcement.is_active == True)
        .order_by(Announcement.created_at.desc())
        .limit(5)
        .all()
    )
    return {
        "announcements": [
            {"id": a.id, "title": a.title, "message": a.message, "type": a.type, "created_at": a.created_at.isoformat() if a.created_at else None}
            for a in rows
        ]
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Quick Actions
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/promote/{user_id}")
def promote_to_superadmin(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Promote a user to superadmin."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_superadmin = True
    db.commit()
    _log_activity(db, admin, "user.promote", "user", user_id, {"email": user.email})
    return {"ok": True, "user_id": user.id, "email": user.email}


# ===========================================================================
# Settings — payment gateways & plan configuration
# ===========================================================================

# Keys we expose to the admin UI.  Sensitive keys are masked on read.
_PAYMENT_KEYS = [
    "stripe_secret_key", "stripe_publishable_key", "stripe_webhook_secret",
    "stripe_price_starter", "stripe_price_pro",
    "paypal_client_id", "paypal_client_secret", "paypal_webhook_id",
    "paypal_mode",  # sandbox | live
]

_SENSITIVE_KEYS = {"stripe_secret_key", "stripe_webhook_secret", "paypal_client_secret"}

_PLAN_KEYS = [
    "plans_config",  # JSON blob: { free: {...}, starter: {...}, pro: {...} }
]


def _get_setting(db: Session, key: str) -> str:
    row = db.query(AdminSetting).filter(AdminSetting.key == key).first()
    return row.value if row else ""


def _set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(AdminSetting).filter(AdminSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(AdminSetting(key=key, value=value))


def _mask(value: str) -> str:
    """Mask sensitive values: show first 4 + last 4 chars."""
    if len(value) <= 10:
        return "••••••••" if value else ""
    return value[:4] + "••••••••" + value[-4:]


# --- Payment gateway settings ---

class PaymentSettingsResponse(BaseModel):
    settings: dict[str, str]


class PaymentSettingsUpdate(BaseModel):
    settings: dict[str, str]


@router.get("/settings/payment", response_model=PaymentSettingsResponse)
def get_payment_settings(
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Return payment gateway settings (sensitive values masked)."""
    result: dict[str, str] = {}
    for key in _PAYMENT_KEYS:
        val = _get_setting(db, key)
        result[key] = _mask(val) if key in _SENSITIVE_KEYS else val
    return {"settings": result}


@router.put("/settings/payment")
def update_payment_settings(
    body: PaymentSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Update payment gateway settings.  Masked values (containing ••) are skipped."""
    updated = []
    for key, val in body.settings.items():
        if key not in _PAYMENT_KEYS:
            continue
        # Skip masked values — don't overwrite with the mask
        if "••" in val:
            continue
        _set_setting(db, key, val.strip())
        updated.append(key)
    db.commit()
    _log_activity(db, admin, "settings.payment.update", "settings", None, {"updated_keys": updated})
    return {"ok": True, "updated": updated}


# --- Plan configuration ---

import json as _json

_DEFAULT_PLANS = {
    "free": {
        "name": "Free",
        "price": 0,
        "period": "forever",
        "app_imports": 5,
        "keyword_refreshes": 10,
        "ai_requests": 5,
        "exports": 0,
        "access_premium": False,
    },
    "starter": {
        "name": "Starter",
        "price": 19.99,
        "period": "month",
        "app_imports": 100,
        "keyword_refreshes": 200,
        "ai_requests": 100,
        "exports": 50,
        "access_premium": True,
    },
    "pro": {
        "name": "Pro",
        "price": 49.99,
        "period": "month",
        "app_imports": None,
        "keyword_refreshes": None,
        "ai_requests": None,
        "exports": None,
        "access_premium": True,
    },
}


@router.get("/settings/plans")
def get_plans_config(
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Return plan configuration.  Falls back to built-in defaults."""
    raw = _get_setting(db, "plans_config")
    if raw:
        try:
            plans = _json.loads(raw)
        except _json.JSONDecodeError:
            plans = _DEFAULT_PLANS
    else:
        plans = _DEFAULT_PLANS
    return {"plans": plans}


class PlanUpdate(BaseModel):
    plans: dict


@router.put("/settings/plans")
def update_plans_config(
    body: PlanUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Update plan configuration and sync to plan enforcement."""
    _set_setting(db, "plans_config", _json.dumps(body.plans))
    db.commit()

    # Hot-reload plan limits in memory
    try:
        from app.config.plans import PLAN_LIMITS
        for code, cfg in body.plans.items():
            if code in PLAN_LIMITS:
                PLAN_LIMITS[code]["app_imports"] = cfg.get("app_imports")
                PLAN_LIMITS[code]["keyword_refreshes"] = cfg.get("keyword_refreshes")
                PLAN_LIMITS[code]["ai_requests"] = cfg.get("ai_requests")
                PLAN_LIMITS[code]["exports"] = cfg.get("exports")
                PLAN_LIMITS[code]["access_premium"] = cfg.get("access_premium", False)
    except Exception:
        pass  # non-fatal; takes effect on next restart

    _log_activity(db, admin, "settings.plans.update", "settings", None, {"plan_codes": list(body.plans.keys())})
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Data quality / coverage metrics
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/data-quality")
def get_data_quality(
    db: Session = Depends(get_db),
    admin: User = Depends(get_superadmin),
):
    """Coverage and freshness metrics used to monitor data pipeline health."""
    return get_data_quality_metrics(db)
