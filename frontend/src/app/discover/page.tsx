'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { AppShell } from '@/components';
import { searchAppsImport, lookupApp, AppImportSearchItem, AppLookupResponse } from '@/lib/api';
import {
  Search,
  Loader2,
  Star,
  Sparkles,
  ArrowRight,
  X,
  Download,
  ExternalLink,
  Calendar,
  Globe,
  Tag,
} from 'lucide-react';

export default function DiscoverClient() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<AppImportSearchItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [total, setTotal] = useState(0);
  const [fromCache, setFromCache] = useState(0);
  const [selectedApp, setSelectedApp] = useState<AppLookupResponse | null>(null);
  const [loadingApp, setLoadingApp] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || query.trim().length < 2) return;

    setLoading(true);
    setSearched(true);
    setSelectedApp(null);

    try {
      const response = await searchAppsImport(query.trim());
      setResults(response.results);
      setTotal(response.total);
      setFromCache(response.from_cache);
    } catch (error) {
      console.error('Search failed:', error);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleAppClick = async (app: AppImportSearchItem) => {
    setLoadingApp(true);
    try {
      const appDetails = await lookupApp(app.app_id);
      setSelectedApp(appDetails);
    } catch (error) {
      console.error('Failed to load app details:', error);
    } finally {
      setLoadingApp(false);
    }
  };

  return (
    <AppShell>
      <div className="p-6-6 max-wxl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Import App</h1>
          <p className="text-muted-foreground">
            Search for any app on the App Store and import it to your database
          </p>
        </div>

        <form onSubmit={handleSearch} className="mb-8">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter app name (e.g., 'Spotify', 'Netflix', 'WhatsApp')..."
                className="w-full pl-10 pr-4 py-3 rounded-lg border bg-background focus:outline-none focus:ring-2 focus:ring-primary"
                minLength={2}
              />
            </div>
            <button
              type="submit"
              disabled={loading || query.trim().length < 2}
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
          <div className="mb-6 flex items-center gap-4 flex-wrap">
            <div className="text-muted-foreground">
              Found <span className="font-semibold text-foreground">{total}</span> apps for "
              <span className="font-semibold text-foreground">{query}</span>"
            </div>
            {fromCache > 0 && (
              <div className="flex items-center gap-1 text-sm bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 px-3 py-1 rounded-full">
                <Download className="h-4 w-4" />
                {fromCache} from database
              </div>
            )}
            {total > fromCache && (
              <div className="flex items-center gap-1 text-sm bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 px-3 py-1 rounded-full">
                <Globe className="h-4 w-4" />
                {total - fromCache} from App Store
              </div>
            )}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            {results.length > 0 && (
              <div className="space-y-3">
                <h2 className="text-lg font-semibold mb-4">Results</h2>
                {results.map((app) => (
                  <div
                    key={app.id}
                    onClick={() => handleAppClick(app)}
                    className={`border rounded-lg p-3 hover:shadow-md transition-all cursor-pointer bg-card ${
                      selectedApp?.app_id === app.app_id ? 'ring-2 ring-primary' : ''
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      {app.icon_url ? (
                        <img
                          src={app.icon_url}
                          alt={app.name}
                          className="w-12 h-12 rounded-lg object-cover"
                        />
                      ) : (
                        <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
                          <AppIcon className="h-6 w-6 text-muted-foreground" />
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <h3 className="font-semibold truncate">{app.name}</h3>
                        <p className="text-sm text-muted-foreground truncate">
                          {app.developer}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        {app.current_rating && app.current_rating > 0 && (
                          <div className="flex items-center gap-1 text-sm">
                            <Star className="h-3.5 w-3.5 fill-yellow-400 text-yellow-400" />
                            <span>{app.current_rating.toFixed(1)}</span>
                          </div>
                        )}
                        {app.source === 'itunes' && (
                          <span className="text-xs bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 px-2 py-0.5 rounded">
                            NEW
                          </span>
                        )}
                        <ArrowRight className="h-4 w-4 text-muted-foreground" />
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
                  Try a different app name
                </p>
              </div>
            )}
          </div>

          <div>
            {loadingApp ? (
              <div className="border rounded-lg p-6 flex items-center justify-center min-h-[400px]">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : selectedApp ? (
              <div className="border rounded-lg p-6 bg-card">
                <div className="flex items-start gap-4 mb-6">
                  {selectedApp.icon_url ? (
                    <img
                      src={selectedApp.icon_url}
                      alt={selectedApp.name}
                      className="w-20 h-20 rounded-xl object-cover"
                    />
                  ) : (
                    <div className="w-20 h-20 rounded-xl bg-muted flex items-center justify-center">
                      <AppIcon className="h-10 w-10 text-muted-foreground" />
                    </div>
                  )}
                  <div className="flex-1">
                    <h2 className="text-xl font-bold">{selectedApp.name}</h2>
                    <p className="text-muted-foreground">{selectedApp.developer}</p>
                    <div className="flex items-center gap-4 mt-2">
                      {selectedApp.current_rating && selectedApp.current_rating > 0 && (
                        <div className="flex items-center gap-1">
                          <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
                          <span className="font-medium">{selectedApp.current_rating.toFixed(1)}</span>
                        </div>
                      )}
                      {selectedApp.current_reviews !== null && selectedApp.current_reviews > 0 && (
                        <span className="text-sm text-muted-foreground">
                          {selectedApp.current_reviews.toLocaleString()} reviews
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div className="bg-muted rounded-lg p-3">
                    <div className="text-sm text-muted-foreground mb-1">Category</div>
                    <div className="font-medium flex items-center gap-1">
                      <Tag className="h-4 w-4" />
                      {selectedApp.primary_category || 'N/A'}
                    </div>
                  </div>
                  <div className="bg-muted rounded-lg p-3">
                    <div className="text-sm text-muted-foreground mb-1">Price</div>
                    <div className="font-medium">
                      {selectedApp.is_free ? (
                        <span className="text-green-600">Free</span>
                      ) : (
                        <span>${selectedApp.price}</span>
                      )}
                    </div>
                  </div>
                  <div className="bg-muted rounded-lg p-3">
                    <div className="text-sm text-muted-foreground mb-1">Version</div>
                    <div className="font-medium">{selectedApp.current_version || 'N/A'}</div>
                  </div>
                  <div className="bg-muted rounded-lg p-3">
                    <div className="text-sm text-muted-foreground mb-1">Release Date</div>
                    <div className="font-medium flex items-center gap-1">
                      <Calendar className="h-4 w-4" />
                      {selectedApp.release_date
                        ? new Date(selectedApp.release_date).toLocaleDateString()
                        : 'N/A'}
                    </div>
                  </div>
                </div>

                {selectedApp.description && (
                  <div className="mb-6">
                    <h3 className="font-semibold mb-2">Description</h3>
                    <p className="text-sm text-muted-foreground line-clamp-4">
                      {selectedApp.description}
                    </p>
                  </div>
                )}

                {selectedApp.screenshots && selectedApp.screenshots.length > 0 && (
                  <div className="mb-6">
                    <h3 className="font-semibold mb-2">Screenshots</h3>
                    <div className="flex gap-2 overflow-x-auto pb-2">
                      {selectedApp.screenshots.slice(0, 5).map((shot, idx) => (
                        <img
                          key={idx}
                          src={shot}
                          alt={`Screenshot ${idx + 1}`}
                          className="w-32 h-auto rounded-lg"
                        />
                      ))}
                    </div>
                  </div>
                )}

                {selectedApp.is_new && (
                  <div className="mb-4 flex items-center gap-2 text-sm bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 px-4 py-2 rounded-lg">
                    <Sparkles className="h-4 w-4" />
                    App imported successfully! Background enrichment started.
                  </div>
                )}

                <div className="flex gap-3">
                  <Link
                    href={`/apps/${selectedApp.id}`}
                    className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 text-center"
                  >
                    View Full Details
                  </Link>
                  {selectedApp.url && (
                    <a
                      href={selectedApp.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-4 py-2 border rounded-lg font-medium hover:bg-muted flex items-center gap-2"
                    >
                      <ExternalLink className="h-4 w-4" />
                      App Store
                    </a>
                  )}
                </div>
              </div>
            ) : (
              <div className="border rounded-lg p-6 flex items-center justify-center min-h-[400px] text-muted-foreground">
                <div className="text-center">
                  <Download className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>Click on an app to import and view details</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function AppIcon({ className }: { className?: string }) {
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
