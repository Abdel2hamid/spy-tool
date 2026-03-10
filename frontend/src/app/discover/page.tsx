'use client';

import { useState } from 'react';
import Link from 'next/link';
import { AppShell } from '@/components';
import { searchAppsByKeyword, KeywordSearchResultItem } from '@/lib/api';
import {
  Search,
  Loader2,
  Star,
  ExternalLink,
  Sparkles,
  ArrowRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';

export default function DiscoverClient() {
  const [keyword, setKeyword] = useState('');
  const [results, setResults] = useState<KeywordSearchResultItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [total, setTotal] = useState(0);
  const [newAppsCount, setNewAppsCount] = useState(0);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyword.trim() || keyword.trim().length < 2) return;

    setLoading(true);
    setSearched(true);

    try {
      const response = await searchAppsByKeyword(keyword.trim());
      setResults(response.results);
      setTotal(response.total);
      setNewAppsCount(response.new_apps_count);
    } catch (error) {
      console.error('Search failed:', error);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppShell>
      <div className="p-6 max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Discover Apps</h1>
          <p className="text-muted-foreground">
            Search any keyword to discover apps on the App Store
          </p>
        </div>

        <form onSubmit={handleSearch} className="mb-8">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
              <input
                type="text"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder="Enter keyword (e.g., 'fitness', 'game', 'music')..."
                className="w-full pl-10 pr-4 py-3 rounded-lg border bg-background focus:outline-none focus:ring-2 focus:ring-primary"
                minLength={2}
              />
            </div>
            <button
              type="submit"
              disabled={loading || keyword.trim().length < 2}
              className="px-6 py-3 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Searching...
                </>
              ) : (
                <>
                  <Search className="h-5 w-5" />
                  Search
                </>
              )}
            </button>
          </div>
        </form>

        {searched && !loading && (
          <div className="mb-6 flex items-center gap-4">
            <div className="text-muted-foreground">
              Found <span className="font-semibold text-foreground">{total}</span> apps for "
              <span className="font-semibold text-foreground">{keyword}</span>"
            </div>
            {newAppsCount > 0 && (
              <div className="flex items-center gap-1 text-sm bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 px-3 py-1 rounded-full">
                <Sparkles className="h-4 w-4" />
                {newAppsCount} new apps added to database
              </div>
            )}
          </div>
        )}

        {results.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {results.map((app) => (
              <div
                key={app.id}
                className="border rounded-lg p-4 hover:shadow-md transition-shadow bg-card"
              >
                <div className="flex items-start gap-3">
                  {app.icon_url ? (
                    <img
                      src={app.icon_url}
                      alt={app.name}
                      className="w-14 h-14 rounded-lg object-cover"
                    />
                  ) : (
                    <div className="w-14 h-14 rounded-lg bg-muted flex items-center justify-center">
                      <AppWindow className="h-6 w-6 text-muted-foreground" />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold truncate">{app.name}</h3>
                    <p className="text-sm text-muted-foreground truncate">
                      {app.developer}
                    </p>
                  </div>
                </div>

                <div className="mt-3 flex items-center gap-4 text-sm">
                  {app.current_rating && app.current_rating > 0 && (
                    <div className="flex items-center gap-1">
                      <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
                      <span>{app.current_rating.toFixed(1)}</span>
                    </div>
                  )}
                  {app.current_reviews !== null && app.current_reviews > 0 && (
                    <span className="text-muted-foreground">
                      {app.current_reviews.toLocaleString()} reviews
                    </span>
                  )}
                  {app.primary_category && (
                    <span className="text-muted-foreground">
                      {app.primary_category}
                    </span>
                  )}
                </div>

                <div className="mt-3 flex items-center justify-between">
                  <span className="text-sm">
                    {app.is_free ? (
                      <span className="text-green-600 font-medium">Free</span>
                    ) : (
                      <span className="font-medium">${app.price}</span>
                    )}
                  </span>
                  <div className="flex items-center gap-2">
                    {app.is_new && (
                      <span className="text-xs bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded">
                        NEW
                      </span>
                    )}
                    <Link
                      href={`/apps/${app.id}`}
                      className="text-sm text-primary hover:underline flex items-center gap-1"
                    >
                      View <ArrowRight className="h-3 w-3" />
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {searched && !loading && results.length === 0 && (
          <div className="text-center py-12">
            <Search className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No apps found</h3>
            <p className="text-muted-foreground">
              Try a different keyword
            </p>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function AppWindow({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <rect width="18" height="18" x="3" y="3" rx="2" ry="2" />
      <path d="M3 9h18" />
    </svg>
  );
}
