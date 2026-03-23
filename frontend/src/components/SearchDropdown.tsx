'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Search, X, Loader2, ChevronRight, Zap } from 'lucide-react';
import Link from 'next/link';
import { searchAppsImport, lookupApp, AppImportSearchItem, PlanLimitExceededError, PlanLimitError } from '@/lib/api';
import { SearchSection } from './SearchSection';
import { SearchResultRow } from './SearchResultRow';
import { useAuth } from '@/lib/auth';

export function SearchDropdown() {
  const [query, setQuery] = useState('');
  const [focused, setFocused] = useState(false);
  const [results, setResults] = useState<AppImportSearchItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [importing, setImporting] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [planLimitError, setPlanLimitError] = useState<PlanLimitError | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);

  const router = useRouter();
  const { token } = useAuth();
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Derived
  const localResults = results.filter((r) => r.source === 'database');
  const storeResults = results.filter((r) => r.source === 'app_store');
  const allItems = [...localResults, ...storeResults];
  const hasResults = allItems.length > 0;
  const isOpen = showDropdown && query.trim().length >= 2;

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        closeDropdown();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Debounced search
  useEffect(() => {
    clearTimeout(debounceRef.current);
    setFocusedIndex(-1);

    if (query.trim().length < 2) {
      setResults([]);
      setSearchError(null);
      setShowDropdown(false);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      setSearchError(null);
      setPlanLimitError(null);
      setShowDropdown(true);
      try {
        const res = await searchAppsImport(query.trim(), 8, token);

        // Direct lookup success → auto-navigate, skip dropdown
        if (
          res.direct_lookup &&
          res.results.length === 1 &&
          res.results[0].id > 0
        ) {
          setShowDropdown(false);
          setQuery('');
          router.push(`/apps/${res.results[0].id}?imported=1`);
          return;
        }

        // Direct lookup failed → surface error
        if (res.error_hint) {
          setSearchError(res.error_hint);
          setResults([]);
          return;
        }

        setResults(res.results);
      } catch (err) {
        if (err instanceof PlanLimitExceededError) {
          setPlanLimitError(err.detail);
          setResults([]);
        } else {
          setSearchError('Search failed. Please try again.');
          setResults([]);
        }
      } finally {
        setSearching(false);
      }
    }, 350);

    return () => clearTimeout(debounceRef.current);
  }, [query]); // eslint-disable-line react-hooks/exhaustive-deps

  const closeDropdown = useCallback(() => {
    setShowDropdown(false);
    setQuery('');
    setImportError(null);
    setSearchError(null);
    setPlanLimitError(null);
    setFocusedIndex(-1);
    inputRef.current?.blur();
  }, []);

  const handleOpen = useCallback(
    (app: AppImportSearchItem) => {
      closeDropdown();
      router.push(`/apps/${app.id}`);
    },
    [closeDropdown, router]
  );

  const handleImport = useCallback(
    async (app: AppImportSearchItem) => {
      setImporting(app.app_id);
      setImportError(null);
      setPlanLimitError(null);
      try {
        const detail = await lookupApp(app.app_id, token);
        closeDropdown();
        router.push(`/apps/${detail.id}?imported=1`);
      } catch (err) {
        if (err instanceof PlanLimitExceededError) {
          setPlanLimitError(err.detail);
        } else {
          setImportError('Import failed. Please try again.');
        }
      } finally {
        setImporting(null);
      }
    },
    [closeDropdown, router, token]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        if (allItems.length > 0)
          setFocusedIndex((i) => (i + 1) % allItems.length);
        break;
      case 'ArrowUp':
        e.preventDefault();
        if (allItems.length > 0)
          setFocusedIndex((i) => (i - 1 + allItems.length) % allItems.length);
        break;
      case 'Enter':
        e.preventDefault();
        if (focusedIndex >= 0 && focusedIndex < allItems.length) {
          const item = allItems[focusedIndex];
          if (item.source === 'database') handleOpen(item);
          else handleImport(item);
        }
        break;
      case 'Escape':
        e.preventDefault();
        closeDropdown();
        break;
    }
  };

  return (
    <div ref={containerRef} className="relative hidden sm:block">
      {/* ── Search input ── */}
      <div
        className={`flex items-center gap-2 rounded-lg border px-3 py-2 transition-all duration-200 ${
          focused || isOpen
            ? 'border-indigo-300 bg-white shadow-sm shadow-indigo-100/60 dark:border-indigo-700 dark:bg-gray-900 dark:shadow-indigo-900/20'
            : 'border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900'
        }`}
      >
        <Search className="h-4 w-4 flex-shrink-0 text-gray-400" />
        <input
          ref={inputRef}
          type="text"
          placeholder="Search apps, paste URL, or App Store ID"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => {
            setFocused(true);
            if (results.length > 0) setShowDropdown(true);
          }}
          onBlur={() => setFocused(false)}
          onKeyDown={handleKeyDown}
          className="w-56 bg-transparent text-sm text-gray-900 placeholder-gray-400 focus:outline-none dark:text-white dark:placeholder-gray-500 lg:w-72"
          role="combobox"
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          aria-autocomplete="list"
          aria-label="Search apps"
          autoComplete="off"
          spellCheck={false}
        />
        {searching ? (
          <Loader2 className="h-3.5 w-3.5 flex-shrink-0 animate-spin text-gray-400" />
        ) : query ? (
          <button
            type="button"
            onClick={() => {
              setQuery('');
              setShowDropdown(false);
              setSearchError(null);
              setPlanLimitError(null);
              inputRef.current?.focus();
            }}
            className="flex-shrink-0 rounded text-gray-400 hover:text-gray-600 focus:outline-none dark:hover:text-gray-300"
            aria-label="Clear search"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        ) : null}
      </div>

      {/* ── Dropdown panel ── always in DOM, transitions in/out ── */}
      <div
        className={`absolute left-0 top-full z-50 mt-2 min-w-[380px] overflow-hidden rounded-2xl border border-gray-200/80 bg-white shadow-xl shadow-gray-900/[0.08] dark:border-gray-700/70 dark:bg-gray-900 dark:shadow-black/30 transition-all duration-150 ease-out origin-top ${
          isOpen
            ? 'opacity-100 scale-100 pointer-events-auto'
            : 'opacity-0 scale-95 pointer-events-none'
        }`}
        role="listbox"
        aria-label="Search results"
      >
        {/* Loading */}
        {searching && !hasResults && (
          <div className="flex items-center justify-center gap-2 px-4 py-8">
            <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Searching…
            </span>
          </div>
        )}

        {/* Plan limit error */}
        {!searching && planLimitError && (
          <div className="px-4 py-5">
            <div className="flex items-start gap-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700/50 px-3 py-3">
              <Zap className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
                  {planLimitError.message}
                </p>
                <p className="mt-0.5 text-xs text-amber-600 dark:text-amber-400">
                  {planLimitError.upgrade_message}
                </p>
                <p className="mt-1 text-xs text-amber-500 dark:text-amber-500">
                  {planLimitError.current_usage}/{planLimitError.limit} used this month
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Error */}
        {!searching && !planLimitError && searchError && (
          <div className="px-4 py-6 text-center">
            <p className="text-sm text-red-500 dark:text-red-400">
              {searchError}
            </p>
          </div>
        )}

        {/* Empty */}
        {!searching && !planLimitError && !searchError && query.trim().length >= 2 && !hasResults && (
          <div className="px-4 py-8 text-center">
            <p className="text-sm font-medium text-gray-900 dark:text-white">
              No apps found
            </p>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Try a different name, or paste an App Store URL
            </p>
          </div>
        )}

        {/* Results */}
        {hasResults && (
          <div className="max-h-[440px] overflow-y-auto pb-1">
            {/* In your workspace */}
            {localResults.length > 0 && (
              <SearchSection title="In your workspace">
                {localResults.map((app, idx) => (
                  <SearchResultRow
                    key={app.id}
                    app={app}
                    isFocused={idx === focusedIndex}
                    isImporting={false}
                    onClick={() => handleOpen(app)}
                    onMouseEnter={() => setFocusedIndex(idx)}
                  />
                ))}
              </SearchSection>
            )}

            {/* Divider */}
            {localResults.length > 0 && storeResults.length > 0 && (
              <div className="mx-4 my-1 border-t border-gray-100 dark:border-gray-800" />
            )}

            {/* From App Store */}
            {storeResults.length > 0 && (
              <SearchSection title="From App Store">
                {storeResults.map((app, idx) => {
                  const absoluteIdx = localResults.length + idx;
                  return (
                    <SearchResultRow
                      key={app.app_id}
                      app={app}
                      isFocused={absoluteIdx === focusedIndex}
                      isImporting={importing === app.app_id}
                      onClick={() => handleImport(app)}
                      onMouseEnter={() => setFocusedIndex(absoluteIdx)}
                    />
                  );
                })}
              </SearchSection>
            )}

            {/* Import error */}
            {importError && (
              <div className="border-t border-gray-100 px-4 py-2 dark:border-gray-800">
                <p className="text-xs text-red-500 dark:text-red-400">
                  {importError}
                </p>
              </div>
            )}
          </div>
        )}

        {/* Footer — always show when results visible */}
        {(hasResults || (searching && results.length > 0)) && query && (
          <div className="border-t border-gray-100 px-4 py-2.5 dark:border-gray-800">
            <Link
              href={`/apps?search=${encodeURIComponent(query)}`}
              onClick={closeDropdown}
              className="flex items-center gap-1 text-xs text-indigo-500 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300"
            >
              <span>
                Search &ldquo;{query}&rdquo; in all apps
              </span>
              <ChevronRight className="h-3 w-3" />
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
