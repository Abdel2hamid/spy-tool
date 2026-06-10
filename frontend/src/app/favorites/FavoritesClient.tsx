'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { AppShell } from '@/components';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { FavoriteAppItem, getFavorites, removeFavorite } from '@/lib/api';
import { Heart, Search, Star, MessageSquare } from 'lucide-react';

export default function FavoritesClient() {
  const [favorites, setFavorites] = useState<FavoriteAppItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getFavorites(0, 200)
      .then((data) => setFavorites(data.favorites ?? []))
      .catch(() => setFavorites([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = favorites.filter(
    (f) =>
      (f.name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (f.developer || '').toLowerCase().includes(searchQuery.toLowerCase()),
  );

  async function handleUnfavorite(appId: number) {
    try {
      await removeFavorite(appId);
      setFavorites((prev) => prev.filter((f) => f.app_id !== appId));
    } catch {
      // ignore
    }
  }

  return (
    <ErrorBoundary>
      <AppShell>
        <div className="space-y-6">
          {/* Header */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Favorites</h1>
              <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
                Apps you&apos;ve saved for quick access
              </p>
            </div>
            {!loading && favorites.length > 0 && (
              <span className="pill bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-400 self-start sm:self-auto">
                {filtered.length} favorite{filtered.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>

          {/* Search */}
          {!loading && favorites.length > 0 && (
            <div className="relative max-w-sm">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search favorites..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-lg border border-gray-200 bg-white py-2 pl-10 pr-4 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-gray-800 dark:bg-gray-900 dark:text-white"
              />
            </div>
          )}

          {/* Content */}
          {loading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-20 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
              ))}
            </div>
          ) : favorites.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 py-20 dark:border-gray-700">
              <Heart className="h-12 w-12 text-gray-300 dark:text-gray-600" />
              <p className="mt-4 text-lg font-medium text-gray-500 dark:text-gray-400">
                No favorites yet
              </p>
              <p className="mt-1 text-sm text-gray-400 dark:text-gray-500">
                Tap the heart icon on any app to save it here.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {filtered.map((fav) => (
                <div
                  key={fav.id}
                  className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 transition hover:shadow-sm dark:border-gray-800 dark:bg-gray-900"
                >
                  {/* Icon */}
                  <Link href={`/apps/${fav.app_id}`} className="flex-shrink-0">
                    {fav.icon_url ? (
                      <img
                        src={fav.icon_url}
                        alt={fav.name}
                        className="h-14 w-14 rounded-xl object-cover ring-1 ring-black/5 dark:ring-white/10"
                      />
                    ) : (
                      <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600">
                        <span className="text-lg font-bold text-white">{fav.name?.[0] || '?'}</span>
                      </div>
                    )}
                  </Link>

                  {/* Info */}
                  <div className="min-w-0 flex-1">
                    <Link
                      href={`/apps/${fav.app_id}`}
                      className="text-sm font-semibold text-gray-900 hover:text-indigo-600 dark:text-white dark:hover:text-indigo-400"
                    >
                      {fav.name}
                    </Link>
                    <p className="truncate text-xs text-gray-500 dark:text-gray-400">
                      {fav.developer || 'Unknown developer'}
                      {fav.primary_category && ` · ${fav.primary_category}`}
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
                      {fav.current_rating != null && (
                        <span className="flex items-center gap-1">
                          <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                          {fav.current_rating.toFixed(1)}
                        </span>
                      )}
                      {fav.current_reviews != null && fav.current_reviews > 0 && (
                        <span className="flex items-center gap-1">
                          <MessageSquare className="h-3 w-3" />
                          {fav.current_reviews.toLocaleString()}
                        </span>
                      )}
                      {fav.current_rank != null && (
                        <span>#{fav.current_rank}</span>
                      )}
                    </div>
                  </div>

                  {/* Unfavorite */}
                  <button
                    onClick={() => handleUnfavorite(fav.app_id)}
                    title="Remove from favorites"
                    className="flex-shrink-0 rounded-lg p-2 text-rose-500 transition hover:bg-rose-50 dark:hover:bg-rose-950/30"
                  >
                    <Heart className="h-5 w-5 fill-current" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </AppShell>
    </ErrorBoundary>
  );
}
