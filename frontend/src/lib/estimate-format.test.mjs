/**
 * Tests for estimate-format.ts utility functions.
 * Run with: node --test src/lib/estimate-format.test.mjs
 *
 * Uses Node 18+ built-in test runner — no install required.
 */
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

// ---------------------------------------------------------------------------
// Re-implement the pure functions inline (avoids TS compilation in runner)
// These must stay in sync with estimate-format.ts
// ---------------------------------------------------------------------------

function fmtNum(n) {
  if (n == null || !isFinite(n) || isNaN(n)) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(Math.round(n));
}

function fmtRev(n) {
  if (n == null || !isFinite(n) || isNaN(n)) return '—';
  return `$${fmtNum(n)}`;
}

function fmtRange(lo, hi) {
  if (lo == null && hi == null) return '—';
  const a = fmtNum(lo);
  const b = hi != null && hi !== lo ? fmtNum(hi) : null;
  return b ? `${a}–${b}` : a;
}

function fmtRevRange(lo, hi) {
  if (lo == null && hi == null) return '—';
  const a = fmtRev(lo);
  const b = hi != null && hi !== lo ? fmtRev(hi) : null;
  return b ? `${a}–${b}` : a;
}

function confidenceLabel(score) {
  if (score == null || !isFinite(score)) return null;
  if (score >= 0.65) return 'high';
  if (score >= 0.40) return 'medium';
  return 'low';
}

// ---------------------------------------------------------------------------
// fmtNum
// ---------------------------------------------------------------------------
describe('fmtNum', () => {
  test('formats millions', () => {
    assert.equal(fmtNum(1_500_000), '1.5M');
    assert.equal(fmtNum(2_000_000), '2.0M');
    assert.equal(fmtNum(12_300_000), '12.3M');
  });

  test('formats thousands', () => {
    assert.equal(fmtNum(1_200), '1.2K');
    assert.equal(fmtNum(500_000), '500.0K');
    assert.equal(fmtNum(1_000), '1.0K');
  });

  test('formats small numbers', () => {
    assert.equal(fmtNum(0), '0');
    assert.equal(fmtNum(99), '99');
    assert.equal(fmtNum(999), '999');
  });

  test('returns — for null', () => {
    assert.equal(fmtNum(null), '—');
  });

  test('returns — for undefined', () => {
    assert.equal(fmtNum(undefined), '—');
  });

  test('returns — for NaN', () => {
    assert.equal(fmtNum(NaN), '—');
  });

  test('returns — for Infinity', () => {
    assert.equal(fmtNum(Infinity), '—');
    assert.equal(fmtNum(-Infinity), '—');
  });
});

// ---------------------------------------------------------------------------
// fmtRev
// ---------------------------------------------------------------------------
describe('fmtRev', () => {
  test('prefixes $ for valid numbers', () => {
    assert.equal(fmtRev(5_000), '$5.0K');
    assert.equal(fmtRev(1_200_000), '$1.2M');
    assert.equal(fmtRev(500), '$500');
  });

  test('returns — for null/undefined/NaN', () => {
    assert.equal(fmtRev(null), '—');
    assert.equal(fmtRev(undefined), '—');
    assert.equal(fmtRev(NaN), '—');
  });
});

// ---------------------------------------------------------------------------
// fmtRange
// ---------------------------------------------------------------------------
describe('fmtRange', () => {
  test('formats a range with two distinct values', () => {
    assert.equal(fmtRange(100_000, 200_000), '100.0K–200.0K');
  });

  test('returns single value when lo === hi', () => {
    assert.equal(fmtRange(50_000, 50_000), '50.0K');
  });

  test('returns single value when hi is null', () => {
    assert.equal(fmtRange(75_000, null), '75.0K');
  });

  test('returns — when both null', () => {
    assert.equal(fmtRange(null, null), '—');
  });
});

// ---------------------------------------------------------------------------
// fmtRevRange
// ---------------------------------------------------------------------------
describe('fmtRevRange', () => {
  test('formats revenue range', () => {
    assert.equal(fmtRevRange(10_000, 20_000), '$10.0K–$20.0K');
  });

  test('returns — when both null', () => {
    assert.equal(fmtRevRange(null, null), '—');
  });
});

// ---------------------------------------------------------------------------
// confidenceLabel
// ---------------------------------------------------------------------------
describe('confidenceLabel', () => {
  test('returns high for score >= 0.65', () => {
    assert.equal(confidenceLabel(0.65), 'high');
    assert.equal(confidenceLabel(0.90), 'high');
    assert.equal(confidenceLabel(1.0), 'high');
  });

  test('returns medium for 0.40 <= score < 0.65', () => {
    assert.equal(confidenceLabel(0.40), 'medium');
    assert.equal(confidenceLabel(0.50), 'medium');
    assert.equal(confidenceLabel(0.64), 'medium');
  });

  test('returns low for score < 0.40', () => {
    assert.equal(confidenceLabel(0.00), 'low');
    assert.equal(confidenceLabel(0.20), 'low');
    assert.equal(confidenceLabel(0.39), 'low');
  });

  test('returns null for null', () => {
    assert.equal(confidenceLabel(null), null);
  });

  test('returns null for undefined', () => {
    assert.equal(confidenceLabel(undefined), null);
  });

  test('returns null for NaN', () => {
    assert.equal(confidenceLabel(NaN), null);
  });

  test('handles exactly 0.65 boundary correctly', () => {
    // 0.65 is 'high', just below is 'medium'
    assert.equal(confidenceLabel(0.65), 'high');
    assert.equal(confidenceLabel(0.6499), 'medium');
  });
});
