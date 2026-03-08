SCORING_WEIGHTS = {
    "rank_velocity": 0.25,
    "review_growth": 0.20,
    "competition": 0.20,
    "category_growth": 0.15,
    "ai_potential": 0.20,
}

CATEGORY_WEIGHTS = {
    "Productivity": 1.2,
    "Business": 1.2,
    "Finance": 1.1,
    "Health & Fitness": 1.1,
    "Medical": 1.1,
    "Education": 1.15,
    "Entertainment": 0.9,
    "Games": 0.8,
    "Utilities": 1.0,
    "Social Networking": 0.85,
}

KEYWORD_DIFFICULTY_THRESHOLDS = {
    "easy": (0, 33),
    "medium": (33, 66),
    "hard": (66, 100),
}

TREND_THRESHOLDS = {
    "declining": (-100, -20),
    "stable": (-20, 20),
    "growing": (20, 50),
    "viral": (50, 100),
}
