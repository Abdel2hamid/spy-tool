# Trending Apps Algorithm V2 - Engineering Note

## Why the Old Algorithm Caused False Positives

The original trending algorithm had several flaws:

1. **Over-reliance on rank velocity**: Single rank jumps could inflate scores
2. **No confidence penalty**: Apps with sparse ranking history (few snapshots) were treated equally to those with rich history
3. **No consistency scoring**: A noisy app with wild swings could rank similarly to a consistent mover
4. **Unbounded review growth**: Tiny apps with few reviews could get massive scores from small review spikes
5. **No category normalization**: Weak categories could dominate global rankings unfairly
6. **Absolute rank underweighted**: A mover in top positions wasn't appropriately valued

## What Changed in V2

### New Multi-Factor Formula

```
trend_score = (
    momentum_normalized (0-60) +
    consistency_normalized (0-15) +
    rank_bonus_normalized (0-20) +
    review_normalized (0-10)
) * confidence_factor (0-1)

Final score range: 0-100
```

### Components

1. **Multi-Window Momentum** (3d, 7d, 14d)
   - Weighted combination: `momentum_3d * 0.2 + momentum_7d * 0.35 + momentum_14d * 0.45`
   - Favors sustained trends over short spikes

2. **Confidence Penalty**
   - Sparse history (few snapshots): 0.0-0.3 multiplier
   - Rich history: 0.7-1.0 multiplier
   - Prevents false positives from apps with insufficient data

3. **Consistency Bonus**
   - Rewards sustained upward movement
   - Penalizes noisy/volatile ranking patterns
   - Range: 0-100, weighted to 0-15 in final score

4. **Absolute Rank Bonus**
   - Top 1-5: 20pts base
   - Top 6-10: 15pts base
   - Top 11-25: 10pts base
   - Top 26-50: 5pts base
   - Capped at 20 to prevent overpowering momentum

5. **Bounded Review Growth**
   - <100 reviews: 0.3x dampening
   - <1,000 reviews: 0.6x dampening
   - <10,000 reviews: 0.85x dampening
   - 10,000+: 1.0x

6. **Category Normalization**
   - Normalizes within category percentile
   - Fallback to raw score if <5 apps in category

### Source of Truth

All trend metrics are now computed **ON THE FLY** from raw ranking history, not from stored `rank_velocity`. This ensures consistency and accuracy.

## Why the New Score is More Trustworthy

1. **Sustained movers outrank spikes**: The multi-window momentum weights favor consistency
2. **Sparse data gets penalized**: Confidence factor reduces scores for apps with insufficient history
3. **Tiny apps can't dominate**: Review growth dampening prevents small apps from hijacking rankings
4. **Top positions matter**: Absolute rank bonus appropriately values movers in strong positions
5. **No category bias**: Category normalization prevents weak-category outliers

## Migration Notes

- The main `/trending` endpoint now uses V2 algorithm
- Response schema has changed to include more detailed scoring components
- Frontend has been updated to handle new fields

## Tests

Run tests with:
```bash
cd backend && python3 -m pytest tests/test_trending_algorithm.py -v
```
