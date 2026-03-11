"""
Keyword Quality Score Backfill Service
=====================================
Recomputes quality_score, validation_score, and quality_tier for keywords
that may have been affected by the apps_count/search_volume semantic bug.

Usage:
    from app.services.keyword_quality_backfill import recompute_keyword_quality_scores
    
    db = SessionLocal()
    try:
        stats = recompute_keyword_quality_scores(db, dry_run=True)
        print(stats)
    finally:
        db.close()
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def recompute_keyword_quality_scores(
    db: Session,
    dry_run: bool = True,
    batch_size: int = 1000,
    min_quality_threshold: float = 45.0,
) -> Dict:
    """
    Recompute quality scores for all keywords.
    
    Parameters
    ----------
    db : Session
        Database session
    dry_run : bool
        If True, only count affected records without updating
    batch_size : int
        Number of keywords to process per batch
    min_quality_threshold : float
        Keywords below this score will be marked as PRUNED
        
    Returns
    -------
    Dict with stats about the backfill
    """
    from app.models.models import Keyword, KeywordStatus
    from app.services.keyword_quality_engine import KeywordQualityEngine
    
    stats = {
        "total_keywords": 0,
        "processed": 0,
        "updated": 0,
        "affected": 0,
        "dry_run": dry_run,
    }
    
    stats["total_keywords"] = db.query(func.count(Keyword.id)).scalar() or 0
    logger.info(f"[Backfill] Starting quality score recomputation. Total keywords: {stats['total_keywords']}")
    
    if dry_run:
        logger.info("[Backfill] DRY RUN - no changes will be made")
    
    offset = 0
    while True:
        keywords = (
            db.query(Keyword)
            .order_by(Keyword.id)
            .offset(offset)
            .limit(batch_size)
            .all()
        )
        
        if not keywords:
            break
            
        for kw in keywords:
            stats["processed"] += 1
            
            apps_count = kw.apps_count or 0
            search_volume = kw.search_volume or 0
            
            was_likely_affected = (
                apps_count > 0 and 
                search_volume > 0 and
                abs(apps_count - search_volume) < 5 and 
                apps_count <= 100
            )
            
            if was_likely_affected:
                stats["affected"] += 1
            
            try:
                q_score, v_score, r_score = KeywordQualityEngine.compute_quality_score(
                    term=kw.term or "",
                    keyword_source=kw.keyword_source,
                    apps_count=apps_count,
                    search_volume=search_volume,
                    difficulty=kw.difficulty or 0.0,
                    trend_score=kw.trend_score or 0.0,
                )
                
                kw.quality_score = q_score
                kw.validation_score = v_score
                kw.quality_tier = KeywordQualityEngine.assign_tier(q_score)
                
                if q_score < min_quality_threshold and kw.status != KeywordStatus.ENRICHED.value:
                    kw.status = KeywordStatus.PRUNED.value
                
                if not dry_run:
                    stats["updated"] += 1
                    
            except Exception as e:
                logger.warning(f"[Backfill] Failed to recompute for '{kw.term}': {e}")
        
        if not dry_run:
            db.commit()
        
        offset += batch_size
        
        if stats["processed"] % 10000 == 0:
            logger.info(f"[Backfill] Progress: {stats['processed']}/{stats['total_keywords']}")
    
    logger.info(
        f"[Backfill] Complete. Processed={stats['processed']}, "
        f"Affected={stats['affected']}, Updated={stats['updated']}"
    )
    
    return stats


def identify_affected_keywords(db: Session, limit: int = 100) -> List[Dict]:
    """Identify keywords that were likely affected by the apps_count bug."""
    from app.models.models import Keyword
    
    keywords = db.query(Keyword).limit(limit).all()
    affected = []
    
    for kw in keywords:
        apps_count = kw.apps_count or 0
        search_volume = kw.search_volume or 0
        
        is_suspicious = (
            apps_count > 0 and 
            search_volume > 0 and
            abs(apps_count - search_volume) < 5 and 
            apps_count <= 100
        )
        
        if is_suspicious:
            affected.append({
                "id": kw.id,
                "term": kw.term,
                "apps_count": apps_count,
                "search_volume": search_volume,
                "quality_score": kw.quality_score,
                "quality_tier": kw.quality_tier,
                "validation_score": kw.validation_score,
            })
    
    return affected
