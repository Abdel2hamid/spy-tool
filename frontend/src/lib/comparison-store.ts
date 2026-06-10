/**
 * Shared comparison selection store backed by localStorage.
 * Components subscribe to changes via a custom "comparison-changed" window event.
 */

const STORAGE_KEY = 'comparison_ids';
const EVENT_NAME = 'comparison-changed';
const MAX_ITEMS = 5;

function _read(): number[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((n: unknown) => typeof n === 'number') : [];
  } catch {
    return [];
  }
}

function _write(ids: number[]) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  window.dispatchEvent(new CustomEvent(EVENT_NAME));
}

export function getComparisonIds(): number[] {
  return _read();
}

export function addToComparison(id: number): boolean {
  const ids = _read();
  if (ids.includes(id)) return false;
  if (ids.length >= MAX_ITEMS) return false;
  _write([...ids, id]);
  return true;
}

export function removeFromComparison(id: number) {
  const ids = _read();
  _write(ids.filter((x) => x !== id));
}

export function clearComparison() {
  _write([]);
}

export function setComparisonIds(ids: number[]) {
  const unique = Array.from(new Set(ids)).slice(0, MAX_ITEMS);
  _write(unique);
}

// ── React hook ──────────────────────────────────────────────────────────────

import { useState, useEffect, useSyncExternalStore } from 'react';

let _snapshot = typeof window !== 'undefined' ? _read() : [];

if (typeof window !== 'undefined') {
  window.addEventListener(EVENT_NAME, () => {
    _snapshot = _read();
  });
}

function _subscribe(cb: () => void) {
  if (typeof window === 'undefined') return () => {};
  window.addEventListener(EVENT_NAME, cb);
  // Also listen for storage events from other tabs
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) {
      _snapshot = _read();
      cb();
    }
  };
  window.addEventListener('storage', onStorage);
  return () => {
    window.removeEventListener(EVENT_NAME, cb);
    window.removeEventListener('storage', onStorage);
  };
}

function _getSnapshot() {
  return _snapshot;
}

function _getServerSnapshot(): number[] {
  return [];
}

export function useComparison(): number[] {
  return useSyncExternalStore(_subscribe, _getSnapshot, _getServerSnapshot);
}
