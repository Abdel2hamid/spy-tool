'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { Menu, Search, Bell, X, Loader2, Plus, ExternalLink } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { ThemeToggle } from './ThemeToggle';
import { searchAppsImport, lookupApp, AppImportSearchItem } from '@/lib/api';

interface HeaderProps {
  onMenuClick: () => void;
}

/** Icon + initials fallback for an app result row. */
function AppIcon({ app, gradient }: { app: AppImportSearchItem; gradient: string }) {
  if (app.icon_url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={app.icon_url} alt={app.name} className="h-8 w-8 flex-shrink-0 rounded-lg object-cover" />
    );
  }
  return (
    <div className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br ${gradient}`}>
      <span className="text-xs font-bold text-white">{app.name[0]?.toUpperCase()}</span>
    </div>
  );
}

export function Header({ onMenuClick }: HeaderProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [focused, setFocused] = useState(false);
  const [results, setResults] = useState<AppImportSearchItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [importing, setImporting] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Debounced search
  useEffect(() => {
    clearTimeout(debounceRef.current);
    if (searchQuery.trim().length < 2) {
      setResults([]);
      setSearchError(null);
      setShowDropdown(false);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      setSearchError(null);
      setShowDropdown(true);
      try {
        const res = await searchAppsImport(searchQuery.trim(), 8);
        // Direct lookup succeeded: URL or trackId pasted → auto-import and navigate
        if (res.direct_lookup && res.results.length === 1 && res.results[0].id > 0) {
          setShowDropdown(false);
          setSearchQuery('');
          router.push(`/apps/${res.results[0].id}?imported=1`);
          return;
        }
        // Direct lookup failed: backend returned an error hint
        if (res.error_hint) {
          setSearchError(res.error_hint);
          setResults([]);
          return;
        }
        setResults(res.results);
      } catch {
        setSearchError('Search failed. Please try again.');
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 350);
    return () => clearTimeout(debounceRef.current);
  }, [searchQuery]);

  const closeDropdown = () => {
    setShowDropdown(false);
    setSearchQuery('');
    setImportError(null);
  };

  const handleImport = async (app: AppImportSearchItem) => {
    setImporting(app.app_id);
    setImportError(null);
    try {
      const detail = await lookupApp(app.app_id);
      closeDropdown();
      router.push(`/apps/${detail.id}?imported=1`);
    } catch {
      setImportError('Import failed. Please try again.');
    } finally {
      setImporting(null);
    }
  };

  const localResults = results.filter(r => r.source === 'database');
  const storeResults = results.filter(r => r.source === 'app_store');
  const hasResults = localResults.length > 0 || storeResults.length > 0;

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-4 border-b border-gray-200 bg-white/90 px-4 backdrop-blur-md dark:border-gray-800 dark:bg-gray-950/90 lg:px-6">
      {/* Left: mobile menu + search */}
      <div className="flex flex-1 items-center gap-3">
        <button
          onClick={onMenuClick}
          className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700 lg:hidden dark:text-gray-400 dark:hover:bg-gray-800"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>

        {/* Smart search with dropdown */}
        <div ref={containerRef} className="relative hidden sm:block">
          <div
            className={`flex items-center gap-2 rounded-lg border px-3 py-2 transition-all duration-200 ${
              focused || showDropdown
                ? 'border-indigo-300 bg-white shadow-sm shadow-indigo-100 dark:border-indigo-700 dark:bg-gray-900 dark:shadow-indigo-900/20'
                : 'border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900'
            }`}
          >
            <Search className="h-4 w-4 flex-shrink-0 text-gray-400" />
            <input
              type="text"
              placeholder="Search apps or paste App Store URL…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onFocus={() => {
                setFocused(true);
                if (results.length > 0) setShowDropdown(true);
              }}
              onBlur={() => setFocused(false)}
              className="w-56 bg-transparent text-sm text-gray-900 placeholder-gray-400 focus:outline-none dark:text-white dark:placeholder-gray-500 lg:w-72"
            />
            {searching ? (
              <Loader2 className="h-3.5 w-3.5 flex-shrink-0 animate-spin text-gray-400" />
            ) : searchQuery ? (
              <button
                type="button"
                onClick={() => { setSearchQuery(''); setShowDropdown(false); setSearchError(null); }}
                className="flex-shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            ) : null}
          </div>

          {/* Results dropdown */}
          {showDropdown && (
            <div className="absolute left-0 right-0 top-full z-50 mt-1.5 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-xl dark:border-gray-700 dark:bg-gray-900">
              {searching && !hasResults ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-indigo-400" />
                </div>
              ) : searchError ? (
                <div className="px-4 py-5 text-center text-sm text-red-500 dark:text-red-400">
                  {searchError}
                </div>
              ) : !hasResults ? (
                <div className="px-4 py-5 text-center text-sm text-gray-500 dark:text-gray-400">
                  No apps found for &ldquo;{searchQuery}&rdquo;
                </div>
              ) : (
                <div className="max-h-96 overflow-y-auto">

                  {/* ── Already tracked (in DB) ── */}
                  {localResults.length > 0 && (
                    <div>
                      <p className="px-3 pb-1 pt-2.5 text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                        In your database
                      </p>
                      {localResults.map(app => (
                        <Link
                          key={app.id}
                          href={`/apps/${app.id}`}
                          onClick={closeDropdown}
                          className="group flex items-center gap-3 px-3 py-2.5 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800"
                        >
                          <AppIcon app={app} gradient="from-indigo-400 to-purple-500" />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-gray-900 dark:text-white">{app.name}</p>
                            <p className="truncate text-xs text-gray-500 dark:text-gray-400">{app.developer}</p>
                          </div>
                          {/* "Open" pill — inside Link, not a nested button */}
                          <span className="flex flex-shrink-0 items-center gap-1 rounded-md border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs font-medium text-gray-500 transition-colors group-hover:border-gray-300 group-hover:bg-white dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:group-hover:bg-gray-700">
                            <ExternalLink className="h-3 w-3" />
                            Open
                          </span>
                        </Link>
                      ))}
                    </div>
                  )}

                  {/* ── From App Store (not yet imported) ── */}
                  {storeResults.length > 0 && (
                    <div>
                      {localResults.length > 0 && (
                        <div className="border-t border-gray-100 dark:border-gray-800" />
                      )}
                      <p className="px-3 pb-1 pt-2.5 text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                        From App Store
                      </p>
                      {storeResults.map(app => (
                        <div
                          key={app.app_id}
                          className="flex items-center gap-3 px-3 py-2.5 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800"
                        >
                          <AppIcon app={app} gradient="from-emerald-400 to-cyan-500" />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-gray-900 dark:text-white">{app.name}</p>
                            <p className="truncate text-xs text-gray-500 dark:text-gray-400">{app.developer}</p>
                          </div>
                          <button
                            onClick={() => handleImport(app)}
                            disabled={importing === app.app_id}
                            className="flex flex-shrink-0 items-center gap-1 rounded-lg bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {importing === app.app_id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <Plus className="h-3 w-3" />
                            )}
                            {importing === app.app_id ? 'Importing…' : 'Import'}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Import error */}
                  {importError && (
                    <div className="border-t border-gray-100 px-3 py-2 dark:border-gray-800">
                      <p className="text-xs text-red-500 dark:text-red-400">{importError}</p>
                    </div>
                  )}

                  {/* Footer hint */}
                  <div className="border-t border-gray-100 px-3 py-2 dark:border-gray-800">
                    <Link
                      href={`/apps?search=${encodeURIComponent(searchQuery)}`}
                      onClick={closeDropdown}
                      className="text-xs text-indigo-500 hover:text-indigo-700 dark:text-indigo-400"
                    >
                      Search &ldquo;{searchQuery}&rdquo; in all apps →
                    </Link>
                  </div>

                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right: actions */}
      <div className="flex items-center gap-1.5">
        <ThemeToggle />
        <button
          className="relative rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800"
          aria-label="Notifications"
        >
          <Bell className="h-4 w-4" />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500 ring-2 ring-white dark:ring-gray-950" />
        </button>
      </div>
    </header>
  );
}
