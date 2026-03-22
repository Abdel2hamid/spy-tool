/**
 * Shared formatting utilities for download & revenue estimate display.
 * Pure functions — no React dependencies, fully testable.
 */

/** Format a number as a compact string: 1.2M / 345.6K / 123. Returns '—' for null/NaN/undefined. */
export function fmtNum(n: number | null | undefined): string {
  if (n == null || !isFinite(n) || isNaN(n)) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(Math.round(n));
}

/** Format a dollar value compactly: $1.2M / $345.6K / $123. Returns '—' for null/NaN. */
export function fmtRev(n: number | null | undefined): string {
  if (n == null || !isFinite(n) || isNaN(n)) return '—';
  return `$${fmtNum(n)}`;
}

/** Format a range as "12.3K–45.6K". Returns single value if lo === hi or hi is null. */
export function fmtRange(lo: number | null | undefined, hi: number | null | undefined): string {
  if (lo == null && hi == null) return '—';
  const a = fmtNum(lo);
  const b = hi != null && hi !== lo ? fmtNum(hi) : null;
  return b ? `${a}–${b}` : a;
}

/** Same as fmtRange but with $ prefix on both ends. */
export function fmtRevRange(lo: number | null | undefined, hi: number | null | undefined): string {
  if (lo == null && hi == null) return '—';
  const a = fmtRev(lo);
  const b = hi != null && hi !== lo ? fmtRev(hi) : null;
  return b ? `${a}–${b}` : a;
}

/** Derive confidence label string ('high' | 'medium' | 'low') from a 0–1 score. */
export function confidenceLabel(score: number | null | undefined): 'high' | 'medium' | 'low' | null {
  if (score == null || !isFinite(score)) return null;
  if (score >= 0.65) return 'high';
  if (score >= 0.40) return 'medium';
  return 'low';
}

/** Compute daily downloads midpoint from monthly range columns. Returns null when no data. */
export function getDailyDownloads(
  app: { estimated_installs_min?: number | null; estimated_installs_max?: number | null },
): number | null {
  const min = app.estimated_installs_min ?? null;
  const max = app.estimated_installs_max ?? null;
  if (min != null && max != null) return (min + max) / 2 / 30;
  if (min != null) return min / 30;
  return null;
}

/** Tailwind class-name strings for a given confidence label. */
export const CONFIDENCE_BADGE: Record<'high' | 'medium' | 'low', string> = {
  high:   'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400',
  medium: 'bg-amber-100   text-amber-700   dark:bg-amber-900/40   dark:text-amber-400',
  low:    'bg-gray-100    text-gray-500    dark:bg-gray-800       dark:text-gray-400',
};
