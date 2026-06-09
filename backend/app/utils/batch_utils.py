"""
batch_utils.py
==============
Shared utilities for memory-bounded batch processing across scheduler jobs.

- iter_batches():  Paginated iteration over SQLAlchemy queries
- log_memory():    RSS memory logging for job instrumentation
"""

import logging
import os
import resource

logger = logging.getLogger(__name__)


def iter_batches(query, batch_size: int = 500):
    """
    Yield rows from a SQLAlchemy query in OFFSET/LIMIT batches.

    Usage:
        for batch in iter_batches(db.query(App.id, App.app_id).order_by(App.id), 200):
            for row in batch:
                process(row)
    """
    offset = 0
    while True:
        batch = query.offset(offset).limit(batch_size).all()
        if not batch:
            break
        yield batch
        offset += batch_size


def log_memory(job_id: str, phase: str = ""):
    """
    Log current RSS memory usage (MB) for a scheduler job.

    Uses resource.getrusage which is available on Linux/macOS.
    On Linux ru_maxrss is in KB; on macOS it's in bytes.
    """
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        # macOS returns bytes, Linux returns KB
        rss_kb = usage.ru_maxrss
        if os.uname().sysname == "Darwin":
            rss_mb = rss_kb / (1024 * 1024)
        else:
            rss_mb = rss_kb / 1024

        tag = f" ({phase})" if phase else ""
        logger.info(f"[MEM] {job_id}{tag}: RSS={rss_mb:.1f}MB")
    except Exception:
        pass
