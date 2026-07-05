"""
Feature Gap Analyzer

Scans negative reviews (rating <= 3) for feature requests and complaints,
extracts feature names, normalizes them, and aggregates by mention count.
"""

import re
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.models import App, Review, FeatureGap

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Trigger patterns — sentences with these patterns likely contain a feature request
# ---------------------------------------------------------------------------

_TRIGGER_PATTERNS = [
    # Explicit wish/desire patterns (most reliable)
    r"wish(?:ed)?\s+(?:it|this|the\s+app|there)\s+(?:had|have|offered|supported?|included?)\s+",
    r"wish\s+(?:they|you|devs?|developers?)\s+(?:would|could|will)\s+(?:add|include|implement|support)\s+",
    r"wish\s+(?:it|there)\s+(?:was|were)\s+(?:a\s+|an\s+)?(?:way\s+to\s+)?",
    # "needs a X" / "needs to have X" (explicit noun gap)
    r"(?:really\s+)?needs?\s+(?:a\s+|an\s+|to\s+have\s+|to\s+add\s+)",
    # "missing X" — very reliable signal
    r"\bmissing\s+(?:a\s+|an\s+|the\s+)?",
    # "should have/add/include/support X"
    r"\bshould\s+(?:have|add|include|support|implement)\s+",
    # "please add/implement/include X"
    r"\bplease\s+(?:add|include|implement|support)\s+",
    # "would love/like to see/have X"
    r"would\s+(?:love|like)\s+(?:to\s+(?:see|have|use)\s+|if\s+(?:it|there)\s+(?:had|have)\s+)",
    # "would be nice/great to have X"
    r"(?:it\s+)?would\s+be\s+(?:nice|great|helpful|useful|amazing|awesome|perfect)\s+(?:to\s+have\s+|if\s+(?:it|there)\s+(?:had|have)\s+|to\s+add\s+)",
    # "doesn't have a X" / "don't have a X" — only with explicit article to avoid false matches
    r"doesn'?t\s+have\s+(?:a\s+|an\s+|the\s+)",
    r"don'?t\s+have\s+(?:a\s+|an\s+|the\s+)",
    # "doesn't support X" / "does not support X"
    r"doesn'?t\s+support\s+",
    r"does\s+not\s+support\s+",
    # "lacks a X" / "lacking X"
    r"\black(?:s|ing)?\s+(?:a\s+|an\s+|the\s+)?",
    # "no support for X" / "no way to X" / "no option to X" — specific form only
    r"\bno\s+(?:support\s+for|way\s+to|option\s+(?:for|to)|ability\s+to)\s+",
    # "can't sync/export/import/etc X"
    r"\bcan'?t\s+(?:even\s+)?(?:sync|share|export|import|access|find|change|edit|delete|backup|download|upload|connect|integrate)\s+",
    r"\bcannot\s+(?:sync|share|export|import|access|backup|download|upload|connect)\s+",
    # "add a feature/option/ability/support for X"
    r"(?:add|bring)\s+(?:a\s+|an\s+|the\s+)?(?:feature|option|ability|support)\s+(?:for|to|of)\s+",
]

_COMPILED_TRIGGERS = [re.compile(p, re.IGNORECASE) for p in _TRIGGER_PATTERNS]

# ---------------------------------------------------------------------------
# Normalization map — canonicalize common variants
# ---------------------------------------------------------------------------

_NORMALIZE_MAP: Dict[str, Optional[str]] = {
    # dark mode
    "night mode": "dark mode",
    "dark theme": "dark mode",
    "dark themes": "dark mode",
    "darkmode": "dark mode",
    "dark mode support": "dark mode",
    # offline
    "offline support": "offline mode",
    "offline access": "offline mode",
    "offline use": "offline mode",
    "offline functionality": "offline mode",
    "works offline": "offline mode",
    "work offline": "offline mode",
    "offline version": "offline mode",
    # sync
    "cross device sync": "sync across devices",
    "cross-device sync": "sync across devices",
    "cloud sync": "sync across devices",
    "cloud syncing": "sync across devices",
    "device sync": "sync across devices",
    "icloud sync": "sync across devices",
    "icloud": "sync across devices",
    # widgets
    "home screen widget": "widget support",
    "home screen widgets": "widget support",
    "widgets": "widget support",
    "widget": "widget support",
    "lock screen widget": "widget support",
    # biometrics
    "face id support": "biometric login",
    "face id": "biometric login",
    "touch id": "biometric login",
    "fingerprint login": "biometric login",
    "fingerprint": "biometric login",
    "biometrics": "biometric login",
    # apple watch
    "apple watch app": "apple watch support",
    "watch app": "apple watch support",
    "watch support": "apple watch support",
    # export/import
    "export feature": "export data",
    "data export": "export data",
    "import feature": "import data",
    "data import": "import data",
    # backup
    "backup and restore": "backup & restore",
    "backup feature": "backup & restore",
    "data backup": "backup & restore",
    "restore": "backup & restore",
    # undo
    "undo redo": "undo/redo",
    "undo and redo": "undo/redo",
    # notifications
    "push notifications": "push notifications",
    "push notification": "push notifications",
    "notification": "push notifications",
    "notifications": "push notifications",
    # siri
    "siri integration": "siri integration",
    "siri shortcut": "siri shortcuts",
    # ipad
    "ipad support": "ipad support",
    "ipad version": "ipad support",
    "ipad app": "ipad support",
    # landscape
    "landscape support": "landscape mode",
    "landscape view": "landscape mode",
    "landscape orientation": "landscape mode",
    # password
    "password protection": "password protection",
    "passcode protection": "password protection",
    "passcode lock": "password protection",
    # multiple accounts
    "multi account": "multiple accounts",
    "multi-account": "multiple accounts",
    # search
    "search function": "search feature",
    "search functionality": "search feature",
    "search bar": "search feature",
    # sort/filter
    "sorting": "sort & filter",
    "filtering": "sort & filter",
    "sort and filter": "sort & filter",
    "filter option": "sort & filter",
    # folders
    "categories": "folders/categories",
    "folder support": "folders/categories",
    "folder organization": "folders/categories",
    "folders": "folders/categories",
    # themes
    "custom theme": "theme customization",
    "custom themes": "theme customization",
    "themes": "theme customization",
    # skip-list (too generic to be useful)
    "it": None,
    "this": None,
    "that": None,
    "app": None,
    "update": None,
    "fix": None,
    "more": None,
    "better": None,
    # billing/support/account complaints (not real feature gaps)
    "cancel": None,
    "cancellation": None,
    "cancel subscription": None,
    "cancel my subscription": None,
    "refund": None,
    "refunds": None,
    "refund policy": None,
    "money back": None,
    "subscription": None,
    "subscriptions": None,
    "subscription management": None,
    "payment": None,
    "payments": None,
    "payment method": None,
    "payment methods": None,
    "payment options": None,
    "billing": None,
    "billing issue": None,
    "billing issues": None,
    "charge": None,
    "charges": None,
    "charged": None,
    "price": None,
    "pricing": None,
    "free version": None,
    "free trial": None,
    "trial": None,
    "account": None,
    "account management": None,
    "customer service": None,
    "customer support": None,
    "support team": None,
    "help center": None,
    "contact support": None,
    "login": None,
    "log in": None,
    "sign in": None,
    "sign up": None,
    "signup": None,
    "signin": None,
    "logout": None,
    "log out": None,
    "sign out": None,
    # generic UI/UX complaints (not app ideas)
    "options": None,
    "option": None,
    "settings": None,
    "preferences": None,
    "customize": None,
    "customization": None,
    "configuration": None,
    "bugs": None,
    "bug fixes": None,
    "crash": None,
    "crashes": None,
    "crashing": None,
    "freezing": None,
    "lagging": None,
    "loading": None,
    "slow": None,
    "ads": None,
    "advertisements": None,
    "ad free": None,
    "remove ads": None,
    "no ads": None,
    "less ads": None,
    "fewer ads": None,
    "privacy": None,
    "privacy policy": None,
    "terms": None,
    "terms of service": None,
    "security": None,
    "permissions": None,
    "data": None,
    "user data": None,
    "personal data": None,
    "delete account": None,
    "delete my account": None,
    # generic platform features (not differentiators)
    "updates": None,
    "new features": None,
    "more features": None,
    "better ui": None,
    "better design": None,
    "better interface": None,
    "user interface": None,
    "ui design": None,
    "ux": None,
    "tutorial": None,
    "tutorials": None,
    "help": None,
    "instructions": None,
    "documentation": None,
    "language support": None,
    "languages": None,
    "translation": None,
    "translations": None,
    "accessibility": None,
    "voiceover": None,
    "voice over": None,
}

_STOP_WORDS = {
    "a", "an", "the", "it", "this", "that", "these", "those",
    "my", "your", "their", "our", "its", "i", "you", "we", "they",
    "he", "she", "me", "him", "her", "us", "them",
    "what", "which", "who", "how", "when", "where", "why",
    "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "must", "shall", "can",
    "and", "or", "but", "with", "from", "for", "of", "to", "in", "on",
    "at", "by", "up", "about", "like", "as", "into", "through",
    "after", "over", "between", "out", "off",
    "more", "also", "just", "very", "so", "if", "not", "no", "yes",
    "all", "any", "some", "many", "much", "most", "other", "such",
    "now", "then", "here", "there", "too", "still", "already", "even",
    "only", "really", "please", "app", "feature", "option", "way",
    "able", "make", "add", "get", "set", "use", "let", "give",
    "want", "need", "support", "time", "update", "work", "works", "working",
    "good", "great", "nice", "better", "best", "well", "bad", "fix",
    # additional noise words
    "one", "else", "avail", "available", "reason", "response", "person",
    "point", "contact", "someone", "something", "anything", "nothing",
    "everyone", "nobody", "always", "never", "every", "each",
    "thing", "things", "stuff", "lot", "lots",
    # billing/support/account (single-word catches)
    "cancel", "refund", "subscription", "payment", "billing", "charge",
    "price", "pricing", "trial", "account", "login", "logout",
    "signup", "signin", "money", "cost", "costs", "paid", "pay",
    "free", "premium", "pro", "plan", "plans",
    # generic complaints
    "options", "settings", "preferences", "bugs", "crash", "crashes",
    "ads", "slow", "loading", "lagging", "freezing", "privacy",
    "security", "permissions", "terms", "policy", "data",
    "help", "tutorial", "instructions", "issue", "issues",
    "problem", "problems", "error", "errors", "glitch", "glitches",
}

_MIN_FEATURE_LEN = 4
_MAX_FEATURE_LEN = 60


def _extract_candidate(text: str, trigger_end: int) -> Optional[str]:
    """Extract the phrase immediately after a trigger match."""
    remainder = text[trigger_end:].strip()
    if not remainder:
        return None
    # Stop at sentence-ending punctuation, conjunctions, or clause starters
    stop = re.search(
        r'[.!?;,\n]|\s+(?:and|or|but|also|as well|plus|although|because|since|so|that|which|when|if)\b',
        remainder,
        re.IGNORECASE,
    )
    phrase = remainder[: stop.start()].strip() if stop else remainder.strip()
    # Remove leading articles
    phrase = re.sub(r'^(?:a|an|the|some|any|more)\s+', '', phrase, flags=re.IGNORECASE).strip()
    # Remove trailing noise words / punctuation
    phrase = re.sub(
        r'\s+(?:please|though|really|honestly|tbh|imo|lol|smh|haha|either|yet|at all)$',
        '', phrase, flags=re.IGNORECASE,
    ).strip()
    phrase = phrase.strip("'\".,!?")
    # Reject phrases containing parentheses, quotes, or special chars (noise indicators)
    if re.search(r'[()"\[\]{}\\]', phrase):
        return None
    # Strip trailing "option/support/ability/feature/mode to/for the X app"
    phrase = re.sub(r'\s+(?:option|support|ability|feature)\s+(?:to|for|in|of)\s+(?:the\s+)?(?:\w+\s+)?app$', '', phrase, flags=re.IGNORECASE).strip()
    phrase = re.sub(r'\s+(?:in|for|to|on)\s+(?:the\s+)?(?:this\s+)?app(?:lication)?$', '', phrase, flags=re.IGNORECASE).strip()
    phrase = re.sub(r'\s+(?:feature|option|functionality|ability|capability)s?$', '', phrase, flags=re.IGNORECASE).strip()
    # Remove em-dash and surrounding chars
    phrase = re.sub(r'\s*[—–]\s*.*$', '', phrase).strip()
    # Reject if starts with a possessive or pronoun (e.g. "one's going to buy...")
    if re.match(r"^(?:one|ones|one's|no\s+one|nobody|someone|anyone)\b", phrase, re.IGNORECASE):
        return None
    # Reject if starts with complaint/sentiment words rather than feature nouns
    _bad_starts = re.compile(
        r'^(?:longer|matter|wonder|believe|understand|imagine|stand|tell|'
        r'trust|think|seem|figure|afford|wait|deal|handle|bear|'
        r'serious|happy|sad|sure|certain|aware|money|hungry|bad|worse|worst|'
        r'even|real|actual|different|another|working|broken|same|old|new\s+(?:version|update)|'
        r'me|him|her|them|us|you|they|it|this|that)',
        re.IGNORECASE,
    )
    if _bad_starts.match(phrase):
        return None
    if _MIN_FEATURE_LEN <= len(phrase) <= _MAX_FEATURE_LEN:
        return phrase
    return None


def _normalize(feature: str) -> Optional[str]:
    """Normalize a raw extracted feature to a canonical form."""
    lower = feature.lower().strip()

    # Direct map lookup
    if lower in _NORMALIZE_MAP:
        return _NORMALIZE_MAP[lower]  # may be None → skip

    # All single words that are stop words → skip
    words = lower.split()
    if not words:
        return None
    if len(words) == 1 and words[0] in _STOP_WORDS:
        return None
    if all(w in _STOP_WORDS for w in words):
        return None
    # Must contain at least one meaningful word (non-stop, ≥3 chars)
    meaningful = [w for w in words if w not in _STOP_WORDS and len(w) >= 3 and w.isalpha()]
    if not meaningful:
        return None

    # Substring match in normalize map (phrase contains a known pattern)
    for pattern, canonical in _NORMALIZE_MAP.items():
        if canonical is None:
            continue
        if pattern in lower:
            return canonical

    return lower


def analyze_feature_gaps(reviews: List) -> List[Dict]:
    """
    Analyze Review ORM objects and return aggregated feature gap counts.

    Only considers reviews with rating <= 3 and content >= 20 chars.
    Deduplicates features per review so one review can't inflate a count.

    Returns list sorted by mentions desc:
        [{"feature": "dark mode", "mentions": 48}, ...]
    """
    counts: Dict[str, int] = defaultdict(int)

    for review in reviews:
        if not review.content:
            continue
        content = review.content.strip()
        if len(content) < 20:
            continue

        review_features: set = set()
        sentences = re.split(r'[.!?\n]+', content)

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue

            for pattern in _COMPILED_TRIGGERS:
                for match in pattern.finditer(sentence):
                    candidate = _extract_candidate(sentence, match.end())
                    if not candidate:
                        continue
                    normalized = _normalize(candidate)
                    if not normalized:
                        continue
                    if normalized in review_features:
                        continue  # already counted for this review
                    review_features.add(normalized)
                    counts[normalized] += 1

    return sorted(
        [{"feature": feat, "mentions": cnt} for feat, cnt in counts.items()],
        key=lambda x: x["mentions"],
        reverse=True,
    )


# ---------------------------------------------------------------------------
# DB-level operations
# ---------------------------------------------------------------------------

class FeatureGapAnalyzer:
    def __init__(self, db: Session):
        self.db = db

    def compute_for_app(self, app_id: int) -> List[Dict]:
        """
        Run gap analysis for one app and upsert results into feature_gaps table.
        Returns the list of gaps found.
        """
        reviews = (
            self.db.query(Review)
            .filter(
                Review.app_id == app_id,
                Review.rating <= 3,
                Review.content.isnot(None),
            )
            .all()
        )

        if not reviews:
            return []

        gaps = analyze_feature_gaps(reviews)
        if not gaps:
            return []

        # Delete old rows for this app, then bulk insert fresh results
        self.db.query(FeatureGap).filter(FeatureGap.app_id == app_id).delete()

        for gap in gaps:
            row = FeatureGap(
                app_id=app_id,
                feature_name=gap["feature"],
                mentions=gap["mentions"],
                detected_at=datetime.now(timezone.utc),
            )
            self.db.add(row)

        self.db.commit()
        logger.debug(f"Feature gaps for app {app_id}: {len(gaps)} features found")
        return gaps

    def get_gaps(self, app_id: int) -> List[Dict]:
        """Return stored gaps for an app, sorted by mentions desc."""
        rows = (
            self.db.query(FeatureGap)
            .filter(FeatureGap.app_id == app_id)
            .order_by(FeatureGap.mentions.desc())
            .all()
        )
        return [{"feature": r.feature_name, "mentions": r.mentions, "detected_at": r.detected_at} for r in rows]
