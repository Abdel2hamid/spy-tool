'use client';

export const dynamic = 'force-dynamic';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { AppShell } from '@/components';
import { AppDetail, AppVersion, Review, AppAnalytics, MarketWeakness, FeatureGapResponse, KeywordIntelligence, AppAutopsy, KeywordHistory, getAppDetail, getAppVersions, getAppReviews, getAppAnalytics, getRankHistory, getMarketWeakness, getFeatureGaps, analyzeFeatureGaps, getKeywordIntelligence, runKeywordSearch, getAppAutopsy, getKeywordHistory, getAppKeywords, RankHistory } from '@/lib/api';
import {
  ArrowLeft, Star, Download, Calendar, Globe, MessageSquare,
  TrendingUp, BarChart3, AlertTriangle, ThumbsUp, Code, ExternalLink,
  ChevronRight, Filter, Lightbulb, RefreshCw, Search, Target,
  Zap, DollarSign, Users, FlaskConical
} from 'lucide-react';
import { cn } from '@/lib/utils';

type TabType = 'overview' | 'versions' | 'reviews' | 'rankings' | 'analytics' | 'market' | 'gaps' | 'keywords' | 'autopsy';

function RatingStars({ rating }: { rating: number | null }) {
  if (!rating) return <span className="text-gray-400">-</span>;
  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <Star
          key={star}
          className={cn(
            "h-4 w-4",
            star <= Math.round(rating) ? "fill-yellow-400 text-yellow-400" : "text-gray-300"
          )}
        />
      ))}
      <span className="ml-1 font-medium">{rating.toFixed(2)}</span>
    </div>
  );
}

function formatRange(min: number | null, max: number | null): string {
  if (!min && !max) return '—';
  const fmt = (n: number) => n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1_000 ? `${(n / 1_000).toFixed(0)}K` : String(n);
  if (min === max || !max) return fmt(min ?? 0);
  return `${fmt(min ?? 0)}–${fmt(max)}`;
}

function formatRevenue(min: number | null, max: number | null): string {
  if (!min && !max) return '—';
  const fmt = (n: number) => n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(1)}M` : n >= 1_000 ? `$${(n / 1_000).toFixed(0)}K` : `$${n.toFixed(0)}`;
  if (!max || min === max) return fmt(min ?? 0);
  return `${fmt(min ?? 0)}–${fmt(max)}`;
}

function AppHeader({ app }: { app: AppDetail }) {
  return (
    <div className="flex flex-col gap-6 md:flex-row">
      <div className="flex-shrink-0">
        {app.icon_url ? (
          <img 
            src={app.icon_url} 
            alt={app.name} 
            className="h-32 w-32 rounded-2xl object-cover shadow-lg"
          />
        ) : (
          <div className="h-32 w-32 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
            <span className="text-4xl font-bold text-white">{app.name?.[0] || '?'}</span>
          </div>
        )}
      </div>
      <div className="flex-1 space-y-2">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">{app.name}</h1>
        {app.subtitle && (
          <p className="text-lg text-gray-500 dark:text-gray-400">{app.subtitle}</p>
        )}
        <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
          {app.developer && (
            <span className="flex items-center gap-1">
              <Code className="h-4 w-4" />
              {app.developer}
            </span>
          )}
          {app.primary_category && (
            <span className="flex items-center gap-1">
              <Globe className="h-4 w-4" />
              {app.primary_category}
              {app.secondary_category && ` › ${app.secondary_category}`}
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <RatingStars rating={app.current_rating} />
          <span className="text-gray-500 dark:text-gray-400">
            {app.current_reviews?.toLocaleString() || 0} ratings
          </span>
          {app.current_version && (
            <span className="flex items-center gap-1 text-gray-500 dark:text-gray-400">
              <Calendar className="h-4 w-4" />
              v{app.current_version}
            </span>
          )}
          {app.is_free !== undefined && (
            <span className={cn(
              "px-2 py-1 rounded-full text-xs font-medium",
              app.is_free ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400" : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
            )}>
              {app.is_free ? 'Free' : `$${app.price}`}
            </span>
          )}
          {app.url && (
            <a 
              href={app.url} 
              target="_blank" 
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-indigo-600 hover:text-indigo-700 dark:text-indigo-400"
            >
              View on App Store <ExternalLink className="h-4 w-4" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

function OverviewTab({ app }: { app: AppDetail }) {
  return (
    <div className="space-y-6">
      {app.description && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">Description</h3>
          <p className="text-gray-600 dark:text-gray-300 whitespace-pre-wrap">{app.description}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400 mb-2">
            <Star className="h-4 w-4" />
            <span className="text-sm font-medium">Rating</span>
          </div>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {app.current_rating?.toFixed(2) || '-'}
          </p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400 mb-2">
            <MessageSquare className="h-4 w-4" />
            <span className="text-sm font-medium">Reviews</span>
          </div>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {app.current_reviews?.toLocaleString() || 0}
          </p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400 mb-2">
            <Download className="h-4 w-4" />
            <span className="text-sm font-medium">Version</span>
          </div>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {app.current_version || '-'}
          </p>
        </div>
      </div>

      {/* Install & Revenue Estimates */}
      {(app.estimated_installs_min || app.estimated_revenue_monthly_min) && (
        <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-5 dark:border-indigo-800 dark:bg-indigo-950/30">
          <h3 className="mb-3 text-sm font-semibold text-indigo-800 dark:text-indigo-300 flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Market Estimates
          </h3>
          <div className="grid grid-cols-2 gap-4">
            {app.estimated_installs_min != null && (
              <div>
                <div className="flex items-center gap-1.5 text-xs text-indigo-600 dark:text-indigo-400 mb-1">
                  <Users className="h-3.5 w-3.5" />
                  Monthly Downloads
                </div>
                <p className="text-lg font-bold text-indigo-900 dark:text-indigo-100">
                  {formatRange(app.estimated_installs_min, app.estimated_installs_max)}
                </p>
                {app.install_confidence != null && (
                  <p className="text-xs text-indigo-500">
                    {Math.round(app.install_confidence * 100)}% confidence
                  </p>
                )}
              </div>
            )}
            {app.estimated_revenue_monthly_min != null && (
              <div>
                <div className="flex items-center gap-1.5 text-xs text-indigo-600 dark:text-indigo-400 mb-1">
                  <DollarSign className="h-3.5 w-3.5" />
                  Monthly Revenue
                </div>
                <p className="text-lg font-bold text-indigo-900 dark:text-indigo-100">
                  {formatRevenue(app.estimated_revenue_monthly_min, app.estimated_revenue_monthly_max)}
                </p>
                <p className="text-xs text-indigo-500">estimated net</p>
              </div>
            )}
          </div>
        </div>
      )}

      {app.screenshots && app.screenshots.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Screenshots</h3>
          <div className="flex gap-4 overflow-x-auto pb-2">
            {app.screenshots.map((screenshot, i) => (
              <img 
                key={i}
                src={screenshot}
                alt={`Screenshot ${i + 1}`}
                className="h-64 rounded-lg object-cover flex-shrink-0"
              />
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">App Info</h3>
          <dl className="space-y-3">
            {app.developer_id && (
              <div className="flex justify-between">
                <dt className="text-gray-500 dark:text-gray-400">Developer ID</dt>
                <dd className="text-gray-900 dark:text-white font-mono text-sm">{app.developer_id}</dd>
              </div>
            )}
            {app.content_rating && (
              <div className="flex justify-between">
                <dt className="text-gray-500 dark:text-gray-400">Content Rating</dt>
                <dd className="text-gray-900 dark:text-white">{app.content_rating}</dd>
              </div>
            )}
            {app.minimum_ios_version && (
              <div className="flex justify-between">
                <dt className="text-gray-500 dark:text-gray-400">Minimum iOS</dt>
                <dd className="text-gray-900 dark:text-white">{app.minimum_ios_version}</dd>
              </div>
            )}
            {app.release_date && (
              <div className="flex justify-between">
                <dt className="text-gray-500 dark:text-gray-400">Release Date</dt>
                <dd className="text-gray-900 dark:text-white">
                  {new Date(app.release_date).toLocaleDateString()}
                </dd>
              </div>
            )}
            {app.last_updated && (
              <div className="flex justify-between">
                <dt className="text-gray-500 dark:text-gray-400">Last Updated</dt>
                <dd className="text-gray-900 dark:text-white">
                  {new Date(app.last_updated).toLocaleDateString()}
                </dd>
              </div>
            )}
          </dl>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Languages</h3>
          {app.supported_languages && app.supported_languages.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {app.supported_languages.map((lang, i) => (
                <span 
                  key={i}
                  className="px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded text-sm text-gray-700 dark:text-gray-300"
                >
                  {lang}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-gray-400">No language data available</p>
          )}

          {app.in_app_purchases && app.in_app_purchases.length > 0 && (
            <div className="mt-4">
              <h4 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">In-App Purchases</h4>
              <ul className="space-y-1">
                {app.in_app_purchases.slice(0, 5).map((iap, i) => (
                  <li key={i} className="text-sm text-gray-600 dark:text-gray-300">
                    {typeof iap === 'string' ? iap : iap.name}
                  </li>
                ))}
                {app.in_app_purchases.length > 5 && (
                  <li className="text-sm text-gray-400">
                    +{app.in_app_purchases.length - 5} more
                  </li>
                )}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function VersionsTab({ versions }: { versions: AppVersion[] }) {
  if (versions.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-8 text-center dark:border-gray-800 dark:bg-gray-900">
        <Calendar className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600 mb-4" />
        <p className="text-gray-500 dark:text-gray-400">No version history available</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {versions.map((version, i) => (
        <div 
          key={version.id}
          className={cn(
            "rounded-xl border p-4",
            version.is_latest 
              ? "border-indigo-200 bg-indigo-50 dark:border-indigo-800 dark:bg-indigo-950" 
              : "border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900"
          )}
        >
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2">
                <h4 className="font-semibold text-gray-900 dark:text-white">v{version.version}</h4>
                {version.is_latest && (
                  <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 dark:bg-indigo-800 dark:text-indigo-300 text-xs rounded-full">
                    Latest
                  </span>
                )}
              </div>
              {version.release_date && (
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {new Date(version.release_date).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                  })}
                </p>
              )}
            </div>
          </div>
          {version.release_notes && (
            <div className="mt-3 text-sm text-gray-600 dark:text-gray-300 whitespace-pre-wrap">
              {version.release_notes.slice(0, 300)}
              {version.release_notes.length > 300 && '...'}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function ReviewsTab({ reviews, appId }: { reviews: Review[], appId: number }) {
  const [filterRating, setFilterRating] = useState<number | null>(null);
  const [filteredReviews, setFilteredReviews] = useState<Review[]>(reviews);

  useEffect(() => {
    if (filterRating) {
      setFilteredReviews(reviews.filter(r => r.rating === filterRating));
    } else {
      setFilteredReviews(reviews);
    }
  }, [filterRating, reviews]);

  if (reviews.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-8 text-center dark:border-gray-800 dark:bg-gray-900">
        <MessageSquare className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600 mb-4" />
        <p className="text-gray-500 dark:text-gray-400">No reviews available</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Filter className="h-4 w-4 text-gray-400" />
        <span className="text-sm text-gray-500 dark:text-gray-400">Filter:</span>
        <button
          onClick={() => setFilterRating(null)}
          className={cn(
            "px-3 py-1 rounded-full text-sm",
            filterRating === null 
              ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-800 dark:text-indigo-300" 
              : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
          )}
        >
          All
        </button>
        {[5, 4, 3, 2, 1].map(rating => (
          <button
            key={rating}
            onClick={() => setFilterRating(rating)}
            className={cn(
              "px-3 py-1 rounded-full text-sm flex items-center gap-1",
              filterRating === rating 
                ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-800 dark:text-indigo-300" 
                : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
            )}
          >
            <Star className="h-3 w-3 fill-current" /> {rating}
          </button>
        ))}
      </div>

      <div className="space-y-4">
        {filteredReviews.map((review) => (
          <div 
            key={review.id}
            className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900"
          >
            <div className="flex items-start justify-between mb-2">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-900 dark:text-white">
                    {review.user_name || 'Anonymous'}
                  </span>
                  <div className="flex">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <Star
                        key={star}
                        className={cn(
                          "h-3 w-3",
                          star <= (review.rating || 0) ? "fill-yellow-400 text-yellow-400" : "text-gray-300"
                        )}
                      />
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-400">
                  {review.date && (
                    <span>{new Date(review.date).toLocaleDateString()}</span>
                  )}
                  {review.app_version && <span>v{review.app_version}</span>}
                  {review.storefront && <span>{review.storefront}</span>}
                </div>
              </div>
            </div>
            {review.title && (
              <h4 className="font-medium text-gray-900 dark:text-white mb-1">{review.title}</h4>
            )}
            {review.content && (
              <p className="text-sm text-gray-600 dark:text-gray-300">{review.content}</p>
            )}
            {review.developer_reply_text && (
              <div className="mt-3 pl-3 border-l-2 border-indigo-200 dark:border-indigo-800">
                <p className="text-xs font-medium text-indigo-600 dark:text-indigo-400 mb-1">Developer Reply</p>
                <p className="text-sm text-gray-600 dark:text-gray-300">{review.developer_reply_text}</p>
                {review.developer_reply_date && (
                  <p className="text-xs text-gray-400 mt-1">
                    {new Date(review.developer_reply_date).toLocaleDateString()}
                  </p>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

const CHART_LABELS: Record<string, string> = {
  topfree: 'Top Free',
  toppaid: 'Top Paid',
  topgrossing: 'Top Grossing',
};

function RankingsTab({ appId }: { appId: number }) {
  const [rankHistory, setRankHistory] = useState<RankHistory | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchRankHistory() {
      try {
        const data = await getRankHistory(appId, 30);
        setRankHistory(data);
      } catch (error) {
        console.error('Failed to fetch rank history:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchRankHistory();
  }, [appId]);

  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-8 dark:border-gray-800 dark:bg-gray-900">
        <div className="animate-pulse space-y-4">
          <div className="h-16 bg-gray-200 dark:bg-gray-800 rounded-lg" />
          <div className="h-64 bg-gray-200 dark:bg-gray-800 rounded-lg" />
        </div>
      </div>
    );
  }

  if (!rankHistory || rankHistory.dates.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-8 text-center dark:border-gray-800 dark:bg-gray-900">
        <TrendingUp className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600 mb-4" />
        <p className="text-gray-500 dark:text-gray-400">No ranking data available</p>
        <p className="mt-2 text-sm text-gray-400 dark:text-gray-500">
          Rankings are populated from App Store top charts. Run a charts scrape to collect data.
        </p>
      </div>
    );
  }

  const minRank = Math.min(...rankHistory.ranks);
  const maxRank = Math.max(...rankHistory.ranks);
  const chartLabel = rankHistory.chart_type ? (CHART_LABELS[rankHistory.chart_type] ?? rankHistory.chart_type) : 'Top Free';

  // SVG rank chart — lower rank number = higher on chart (inverted Y)
  const pts = rankHistory.ranks.map((r, i) => {
    const x = rankHistory.dates.length > 1
      ? (i / (rankHistory.dates.length - 1)) * 760 + 20
      : 400;
    const range = maxRank - minRank || 1;
    const y = 20 + ((r - minRank) / range) * 240;
    return { x, y, rank: r, date: rankHistory.dates[i] };
  });
  const linePath = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  const areaPath = `M ${pts[0].x} 280 ${pts.map(p => `L ${p.x} ${p.y}`).join(' ')} L ${pts[pts.length - 1].x} 280 Z`;

  return (
    <div className="space-y-4">
      {/* Current rank summary */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-4 dark:border-indigo-800 dark:bg-indigo-950">
          <p className="text-sm font-medium text-indigo-600 dark:text-indigo-400">Current Rank</p>
          <p className="mt-1 text-3xl font-bold text-indigo-700 dark:text-indigo-300">
            #{rankHistory.current_rank ?? rankHistory.ranks[rankHistory.ranks.length - 1]}
          </p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Category</p>
          <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">
            {rankHistory.category_name ?? 'Unknown'}
          </p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Chart</p>
          <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">{chartLabel}</p>
        </div>
      </div>

      {/* Rank history chart */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <h3 className="mb-1 text-lg font-semibold text-gray-900 dark:text-white">
          Rank History — {rankHistory.category_name ?? 'Category'} · {chartLabel}
        </h3>
        <p className="mb-4 text-xs text-gray-400 dark:text-gray-500">Lower number = better rank</p>
        <svg className="w-full" viewBox="0 0 800 300" preserveAspectRatio="none">
          <defs>
            <linearGradient id="rankAreaGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#6366f1" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={areaPath} fill="url(#rankAreaGrad)" />
          <path d={linePath} fill="none" stroke="#6366f1" strokeWidth="2.5" strokeLinejoin="round" />
          {pts.map((p, i) => (
            <circle key={i} cx={p.x} cy={p.y} r="4" fill="#6366f1" />
          ))}
          {/* Y axis labels */}
          <text x="4" y="24" fontSize="10" fill="#9ca3af">#{minRank}</text>
          <text x="4" y="276" fontSize="10" fill="#9ca3af">#{maxRank}</text>
        </svg>
        <div className="mt-2 flex items-center justify-between text-xs text-gray-400">
          <span>{rankHistory.dates[0]}</span>
          <span>{rankHistory.dates.length} data point{rankHistory.dates.length !== 1 ? 's' : ''}</span>
          <span>{rankHistory.dates[rankHistory.dates.length - 1]}</span>
        </div>
      </div>
    </div>
  );
}

function AnalyticsTab({ analytics }: { analytics: AppAnalytics | null }) {
  if (!analytics) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-8 text-center dark:border-gray-800 dark:bg-gray-900">
        <BarChart3 className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600 mb-4" />
        <p className="text-gray-500 dark:text-gray-400">No analytics data available</p>
        <p className="text-sm text-gray-400 mt-2">Analytics are computed from review data</p>
      </div>
    );
  }

  const getScoreColor = (score: number) => {
    if (score >= 70) return 'text-emerald-500';
    if (score >= 40) return 'text-amber-500';
    return 'text-red-500';
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <p className="text-sm text-gray-500 dark:text-gray-400">Sentiment</p>
          <p className={cn("text-2xl font-bold", getScoreColor(analytics.sentiment_score))}>
            {analytics.sentiment_label || 'Unknown'}
          </p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <p className="text-sm text-gray-500 dark:text-gray-400">Quality Score</p>
          <p className={cn("text-2xl font-bold", getScoreColor(analytics.quality_score))}>
            {analytics.quality_score.toFixed(0)}%
          </p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <p className="text-sm text-gray-500 dark:text-gray-400">Opportunity</p>
          <p className={cn("text-2xl font-bold", getScoreColor(analytics.opportunity_score))}>
            {analytics.opportunity_score.toFixed(0)}%
          </p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <p className="text-sm text-gray-500 dark:text-gray-400">Churn Risk</p>
          <p className={cn("text-2xl font-bold", getScoreColor(100 - analytics.churn_risk_score))}>
            {analytics.churn_risk_score.toFixed(0)}%
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Growth Metrics</h3>
          <dl className="space-y-3">
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Reviews (30d)</dt>
              <dd className={cn(
                "font-medium",
                analytics.review_growth_30d > 0 ? "text-emerald-500" : "text-red-500"
              )}>
                {analytics.review_growth_30d > 0 ? '+' : ''}{analytics.review_growth_30d.toFixed(1)}%
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Reviews (90d)</dt>
              <dd className={cn(
                "font-medium",
                analytics.review_growth_90d > 0 ? "text-emerald-500" : "text-red-500"
              )}>
                {analytics.review_growth_90d > 0 ? '+' : ''}{analytics.review_growth_90d.toFixed(1)}%
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Rating Change (30d)</dt>
              <dd className={cn(
                "font-medium",
                analytics.rating_change_30d > 0 ? "text-emerald-500" : analytics.rating_change_30d < 0 ? "text-red-500" : "text-gray-500"
              )}>
                {analytics.rating_change_30d > 0 ? '+' : ''}{analytics.rating_change_30d.toFixed(2)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Rating Change (90d)</dt>
              <dd className={cn(
                "font-medium",
                analytics.rating_change_90d > 0 ? "text-emerald-500" : analytics.rating_change_90d < 0 ? "text-red-500" : "text-gray-500"
              )}>
                {analytics.rating_change_90d > 0 ? '+' : ''}{analytics.rating_change_90d.toFixed(2)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Update Cadence</dt>
              <dd className="font-medium text-gray-900 dark:text-white">
                {analytics.update_cadence_score.toFixed(0)}%
              </dd>
            </div>
          </dl>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Insights</h3>
          <div className="space-y-4">
            {analytics.positive_themes && analytics.positive_themes.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">Top Positive Themes</p>
                <div className="flex flex-wrap gap-2">
                  {analytics.positive_themes.slice(0, 5).map((theme, i) => (
                    <span key={i} className="px-2 py-1 bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400 text-xs rounded-full">
                      {theme}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {analytics.bug_keywords && analytics.bug_keywords.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">Bug Keywords</p>
                <div className="flex flex-wrap gap-2">
                  {analytics.bug_keywords.slice(0, 5).map((keyword, i) => (
                    <span key={i} className="px-2 py-1 bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400 text-xs rounded-full">
                      {keyword}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {analytics.common_features && analytics.common_features.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">Requested Features</p>
                <div className="flex flex-wrap gap-2">
                  {analytics.common_features.slice(0, 5).map((feature, i) => (
                    <span key={i} className="px-2 py-1 bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-400 text-xs rounded-full">
                      {feature}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

const COUNTRY_NAMES: Record<string, string> = {
  US: '🇺🇸 United States', GB: '🇬🇧 United Kingdom', DE: '🇩🇪 Germany',
  FR: '🇫🇷 France', JP: '🇯🇵 Japan', AU: '🇦🇺 Australia', CA: '🇨🇦 Canada',
  CN: '🇨🇳 China', IN: '🇮🇳 India', BR: '🇧🇷 Brazil', MX: '🇲🇽 Mexico',
  KR: '🇰🇷 South Korea', IT: '🇮🇹 Italy', ES: '🇪🇸 Spain', RU: '🇷🇺 Russia',
  NL: '🇳🇱 Netherlands', SE: '🇸🇪 Sweden', NO: '🇳🇴 Norway', DK: '🇩🇰 Denmark',
  FI: '🇫🇮 Finland', SG: '🇸🇬 Singapore', TW: '🇹🇼 Taiwan', HK: '🇭🇰 Hong Kong',
  AE: '🇦🇪 UAE', SA: '🇸🇦 Saudi Arabia', TR: '🇹🇷 Turkey', PL: '🇵🇱 Poland',
  PT: '🇵🇹 Portugal', AR: '🇦🇷 Argentina', CO: '🇨🇴 Colombia', CL: '🇨🇱 Chile',
  ZA: '🇿🇦 South Africa', NG: '🇳🇬 Nigeria', EG: '🇪🇬 Egypt', PH: '🇵🇭 Philippines',
  TH: '🇹🇭 Thailand', VN: '🇻🇳 Vietnam', ID: '🇮🇩 Indonesia', MY: '🇲🇾 Malaysia',
  NZ: '🇳🇿 New Zealand', CH: '🇨🇭 Switzerland', AT: '🇦🇹 Austria', BE: '🇧🇪 Belgium',
  IL: '🇮🇱 Israel', PK: '🇵🇰 Pakistan', BD: '🇧🇩 Bangladesh',
};

function getCountryLabel(code: string): { flag: string; name: string } {
  const label = COUNTRY_NAMES[code.toUpperCase()];
  if (label) {
    const [flag, ...rest] = label.split(' ');
    return { flag, name: rest.join(' ') };
  }
  return { flag: '🌐', name: code };
}

function negativeRatioColor(ratio: number) {
  if (ratio < 0.15) return 'text-emerald-600 dark:text-emerald-400';
  if (ratio < 0.30) return 'text-amber-600 dark:text-amber-400';
  return 'text-red-600 dark:text-red-400';
}

function negativeRatioBg(ratio: number) {
  if (ratio < 0.15) return 'border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950';
  if (ratio < 0.30) return 'border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950';
  return 'border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950';
}

function negativeRatioLabel(ratio: number) {
  if (ratio < 0.15) return 'Healthy';
  if (ratio < 0.30) return 'Moderate';
  return 'High Risk';
}

function MarketWeaknessTab({ appId }: { appId: number }) {
  const [data, setData] = useState<MarketWeakness | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const result = await getMarketWeakness(appId);
        setData(result);
      } catch (error) {
        console.error('Failed to fetch market weakness:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [appId]);

  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-8 dark:border-gray-800 dark:bg-gray-900">
        <div className="animate-pulse space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 rounded-lg bg-gray-200 dark:bg-gray-800" />
          ))}
        </div>
      </div>
    );
  }

  if (!data || !data.has_data) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-8 text-center dark:border-gray-800 dark:bg-gray-900">
        <Globe className="mx-auto mb-4 h-12 w-12 text-gray-300 dark:text-gray-600" />
        <p className="text-gray-500 dark:text-gray-400">No market weakness data available</p>
        <p className="mt-2 text-sm text-gray-400 dark:text-gray-500">
          Requires at least 20 reviews per country with a storefront code.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Market Weakness by Country
            </h3>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Negative review ratio (rating ≤ 2) — countries with &lt;20 reviews excluded
            </p>
          </div>
          <div className="flex flex-wrap gap-3 text-xs text-gray-600 dark:text-gray-400">
            <span className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-500" />
              &lt;15% Healthy
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-500" />
              15–30% Moderate
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-red-500" />
              ≥30% High Risk
            </span>
          </div>
        </div>

        <div className="space-y-3">
          {data.countries.map((stat) => {
            const { flag, name } = getCountryLabel(stat.country);
            return (
              <div
                key={stat.country}
                className={cn(
                  'flex items-center justify-between rounded-lg border p-4',
                  negativeRatioBg(stat.negative_ratio)
                )}
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{flag}</span>
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">{name}</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {stat.total_reviews.toLocaleString()} reviews &middot; avg {stat.average_rating.toFixed(1)} ★
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className={cn('text-2xl font-bold', negativeRatioColor(stat.negative_ratio))}>
                    {(stat.negative_ratio * 100).toFixed(1)}%
                  </p>
                  <p className={cn('text-xs font-medium', negativeRatioColor(stat.negative_ratio))}>
                    {negativeRatioLabel(stat.negative_ratio)}
                  </p>
                  <p className="mt-0.5 text-xs text-gray-400">{stat.negative_reviews} negative</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function FeatureGapsTab({ appId }: { appId: number }) {
  const [data, setData] = useState<FeatureGapResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    getFeatureGaps(appId)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [appId]);

  const handleReanalyze = async () => {
    setAnalyzing(true);
    try {
      const result = await analyzeFeatureGaps(appId);
      setData(result);
    } catch {}
    setAnalyzing(false);
  };

  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-8 dark:border-gray-800 dark:bg-gray-900">
        <div className="animate-pulse space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-14 rounded-lg bg-gray-200 dark:bg-gray-800" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-5 dark:border-indigo-800 dark:bg-indigo-950">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Lightbulb className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
              <h3 className="text-lg font-semibold text-indigo-900 dark:text-indigo-100">
                Feature Opportunities
              </h3>
            </div>
            <p className="text-sm text-indigo-700 dark:text-indigo-300">
              Detected from negative reviews (rating ≤ 3) using NLP pattern matching.
              {data && data.has_data && (
                <span className="ml-1 font-medium">
                  {data.total_features} unique requests · {data.total_mentions} total mentions
                </span>
              )}
            </p>
          </div>
          <button
            onClick={handleReanalyze}
            disabled={analyzing}
            className="flex items-center gap-2 rounded-lg border border-indigo-300 bg-white px-3 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-100 disabled:opacity-50 dark:border-indigo-700 dark:bg-indigo-900 dark:text-indigo-300 dark:hover:bg-indigo-800"
          >
            <RefreshCw className={cn('h-4 w-4', analyzing && 'animate-spin')} />
            {analyzing ? 'Analyzing…' : 'Re-analyze'}
          </button>
        </div>
      </div>

      {!data || !data.has_data ? (
        <div className="rounded-xl border border-gray-200 bg-white p-8 text-center dark:border-gray-800 dark:bg-gray-900">
          <Lightbulb className="mx-auto mb-4 h-12 w-12 text-gray-300 dark:text-gray-600" />
          <p className="text-gray-500 dark:text-gray-400">No feature gap data available</p>
          <p className="mt-2 text-sm text-gray-400 dark:text-gray-500">
            Requires negative reviews (rating ≤ 3) with enough text content.
          </p>
          <button
            onClick={handleReanalyze}
            disabled={analyzing}
            className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {analyzing ? 'Analyzing…' : 'Run Analysis'}
          </button>
        </div>
      ) : (
        <>
          {/* Top 3 highlighted */}
          <div>
            <p className="mb-3 text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
              💡 Users frequently request:
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {data.feature_gaps.slice(0, 3).map((gap, i) => {
                const colors = [
                  'border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950',
                  'border-indigo-200 bg-indigo-50 dark:border-indigo-800 dark:bg-indigo-950',
                  'border-purple-200 bg-purple-50 dark:border-purple-800 dark:bg-purple-950',
                ];
                const textColors = [
                  'text-amber-800 dark:text-amber-200',
                  'text-indigo-800 dark:text-indigo-200',
                  'text-purple-800 dark:text-purple-200',
                ];
                const badgeColors = [
                  'bg-amber-200 text-amber-800 dark:bg-amber-800 dark:text-amber-200',
                  'bg-indigo-200 text-indigo-800 dark:bg-indigo-800 dark:text-indigo-200',
                  'bg-purple-200 text-purple-800 dark:bg-purple-800 dark:text-purple-200',
                ];
                return (
                  <div key={gap.feature} className={cn('rounded-xl border p-4', colors[i])}>
                    <div className="flex items-start justify-between gap-2">
                      <p className={cn('font-semibold capitalize', textColors[i])}>
                        {gap.feature}
                      </p>
                      <span className={cn('rounded-full px-2 py-0.5 text-xs font-bold whitespace-nowrap', badgeColors[i])}>
                        {gap.mentions} mention{gap.mentions !== 1 ? 's' : ''}
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 rounded-full bg-white/60 dark:bg-black/20">
                      <div
                        className="h-1.5 rounded-full bg-current opacity-40"
                        style={{ width: `${Math.min(100, (gap.mentions / data.feature_gaps[0].mentions) * 100)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Full list */}
          {data.feature_gaps.length > 3 && (
            <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
              <div className="border-b border-gray-100 px-5 py-3 dark:border-gray-800">
                <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                  All Feature Requests ({data.feature_gaps.length})
                </h4>
              </div>
              <div className="divide-y divide-gray-100 dark:divide-gray-800">
                {data.feature_gaps.map((gap, i) => {
                  const pct = Math.round((gap.mentions / data.feature_gaps[0].mentions) * 100);
                  return (
                    <div key={gap.feature} className="flex items-center gap-4 px-5 py-3">
                      <span className="w-5 text-xs font-medium text-gray-400">
                        {i + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium capitalize text-gray-900 dark:text-white truncate">
                          {gap.feature}
                        </p>
                        <div className="mt-1 h-1 rounded-full bg-gray-100 dark:bg-gray-800">
                          <div
                            className="h-1 rounded-full bg-indigo-500"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                      <span className="text-sm font-semibold text-gray-700 dark:text-gray-300 whitespace-nowrap">
                        {gap.mentions} {gap.mentions === 1 ? 'mention' : 'mentions'}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}


// ---------------------------------------------------------------------------
// KeywordIntelligenceTab
// ---------------------------------------------------------------------------

function KeywordIntelligenceTab({ appId }: { appId: number }) {
  const [data, setData] = useState<KeywordIntelligence | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [scanKeyword, setScanKeyword] = useState('');

  useEffect(() => {
    getKeywordIntelligence(appId)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [appId]);

  const handleScan = async () => {
    if (!scanKeyword.trim()) return;
    setScanning(true);
    try {
      await runKeywordSearch(scanKeyword.trim());
      const result = await getKeywordIntelligence(appId);
      setData(result);
    } catch {}
    setScanning(false);
    setScanKeyword('');
  };

  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-8 dark:border-gray-800 dark:bg-gray-900">
        <div className="animate-pulse space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-12 rounded-lg bg-gray-200 dark:bg-gray-800" />
          ))}
        </div>
      </div>
    );
  }

  const confidence = data?.confidence ?? 0;
  const confidenceColor = confidence >= 70 ? 'text-emerald-600' : confidence >= 40 ? 'text-amber-600' : 'text-red-500';

  return (
    <div className="space-y-6">
      {/* Stats strip */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label: 'Primary Keyword', value: data?.primary_keyword ?? '—' },
          { label: 'Confidence', value: `${confidence}%`, className: confidenceColor },
          { label: 'Organic Keywords', value: String(data?.organic_keywords?.length ?? 0) },
          { label: 'Ad Keywords', value: String(data?.ads_keywords?.length ?? 0) },
        ].map(({ label, value, className }) => (
          <div key={label} className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
            <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
            <p className={cn('mt-1 text-lg font-bold text-gray-900 dark:text-white truncate', className)}>{value}</p>
          </div>
        ))}
      </div>

      {/* Traffic mix */}
      {data && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
          <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">Traffic Mix</h3>
          <div className="flex h-3 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
            <div
              className="bg-emerald-500 transition-all"
              style={{ width: `${data.traffic_mix.organic}%` }}
            />
            <div
              className="bg-rose-400 transition-all"
              style={{ width: `${data.traffic_mix.ads}%` }}
            />
          </div>
          <div className="mt-2 flex gap-6 text-xs text-gray-500">
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
              Organic {data.traffic_mix.organic}%
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-full bg-rose-400" />
              Ads {data.traffic_mix.ads}%
            </span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Organic Keywords */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300">
            <TrendingUp className="h-4 w-4 text-emerald-500" />
            Organic Rankings
          </h3>
          {data?.organic_keywords?.length ? (
            <div className="space-y-2">
              {data.organic_keywords.map((kw) => (
                <div key={kw.keyword} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 dark:bg-gray-800">
                  <div>
                    <span className="text-sm font-medium text-gray-900 dark:text-white">{kw.keyword}</span>
                    <div className="mt-0.5 flex gap-3 text-xs text-gray-400">
                      <span>Vol: {kw.search_volume.toLocaleString()}</span>
                      <span>Diff: {kw.difficulty.toFixed(0)}</span>
                    </div>
                  </div>
                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400">
                    #{kw.rank}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No organic ranking data yet.</p>
          )}
        </div>

        {/* Ad Keywords */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300">
            <Target className="h-4 w-4 text-rose-500" />
            Sponsored Placements
          </h3>
          {data?.ads_keywords?.length ? (
            <div className="space-y-2">
              {data.ads_keywords.map((kw) => (
                <div key={kw.keyword} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 dark:bg-gray-800">
                  <span className="text-sm font-medium text-gray-900 dark:text-white">{kw.keyword}</span>
                  <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs font-bold text-rose-700 dark:bg-rose-950 dark:text-rose-400">
                    Ad #{kw.position}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No sponsored placements detected.</p>
          )}
        </div>
      </div>

      {/* Manual scan */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
        <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">Scan a Keyword</h3>
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="e.g. focus timer, habit tracker..."
              value={scanKeyword}
              onChange={(e) => setScanKeyword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleScan()}
              className="w-full rounded-lg border border-gray-200 bg-white py-2 pl-10 pr-4 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white"
            />
          </div>
          <button
            onClick={handleScan}
            disabled={scanning || !scanKeyword.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {scanning ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Search className="h-4 w-4" />
            )}
            {scanning ? 'Scanning…' : 'Scan'}
          </button>
        </div>
        {data?.last_scanned && (
          <p className="mt-2 text-xs text-gray-400">
            Last scanned: {new Date(data.last_scanned).toLocaleString()}
          </p>
        )}
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// KeywordHistoryChart — rank over time for a single keyword
// ---------------------------------------------------------------------------

function KeywordHistoryChart({ history }: { history: { date: string; best_rank: number; is_sponsored: boolean }[] }) {
  if (history.length === 0) return <p className="text-sm text-gray-400">No history data for this keyword yet.</p>;

  const ranks = history.map(h => h.best_rank);
  const maxRank = Math.max(...ranks);
  const minRank = Math.min(...ranks);
  const range = maxRank - minRank || 1;
  const W = 100;
  const H = 60;
  const pts = history.map((h, i) => {
    const x = (i / (history.length - 1 || 1)) * W;
    const y = H - ((h.best_rank - minRank) / range) * (H - 8) - 4;
    return `${x},${y}`;
  }).join(' ');

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-16 overflow-visible" preserveAspectRatio="none">
        <polyline points={pts} fill="none" stroke="#6366f1" strokeWidth="1.5" strokeLinejoin="round" />
        {history.map((h, i) => {
          const x = (i / (history.length - 1 || 1)) * W;
          const y = H - ((h.best_rank - minRank) / range) * (H - 8) - 4;
          return <circle key={i} cx={x} cy={y} r="1.5" fill={h.is_sponsored ? '#f43f5e' : '#6366f1'} />;
        })}
      </svg>
      <div className="mt-1 flex justify-between text-xs text-gray-400">
        <span>{history[0]?.date}</span>
        <span className="text-center text-gray-600 dark:text-gray-400">
          Current: #{history[history.length - 1]?.best_rank ?? '—'}
        </span>
        <span>{history[history.length - 1]?.date}</span>
      </div>
    </div>
  );
}

function KeywordHistoryPanel({ appId }: { appId: number }) {
  const [keywords, setKeywords] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [history, setHistory] = useState<KeywordHistory | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getAppKeywords(appId).then(kws => {
      setKeywords(kws);
      if (kws.length > 0) setSelected(kws[0]);
    });
  }, [appId]);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    getKeywordHistory(appId, selected)
      .then(setHistory)
      .catch(() => setHistory(null))
      .finally(() => setLoading(false));
  }, [appId, selected]);

  if (keywords.length === 0) return <p className="text-sm text-gray-400">No keyword history yet. Scan keywords first.</p>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {keywords.map(kw => (
          <button
            key={kw}
            onClick={() => setSelected(kw)}
            className={cn(
              'rounded-full px-3 py-1 text-xs font-medium transition-colors',
              selected === kw
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400'
            )}
          >
            {kw}
          </button>
        ))}
      </div>
      {loading ? (
        <div className="h-20 animate-pulse rounded-lg bg-gray-100 dark:bg-gray-800" />
      ) : history && history.history.length > 0 ? (
        <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
          <div className="mb-2 flex items-center justify-between">
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Rank history for &quot;{selected}&quot;
            </h4>
            <span className="text-xs text-gray-400">{history.total_days} days</span>
          </div>
          <KeywordHistoryChart history={history.history} />
          <div className="mt-2 flex gap-4 text-xs text-gray-500">
            <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full bg-indigo-500" /> Organic</span>
            <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full bg-rose-400" /> Sponsored</span>
          </div>
        </div>
      ) : (
        <p className="text-sm text-gray-400">No history data for &quot;{selected}&quot;.</p>
      )}
    </div>
  );
}


// ---------------------------------------------------------------------------
// AppAutopsyTab
// ---------------------------------------------------------------------------

function AppAutopsyTab({ appId }: { appId: number }) {
  const [data, setData] = useState<AppAutopsy | null>(null);
  const [loading, setLoading] = useState(true);
  const [useLlm, setUseLlm] = useState(true);

  const load = (llm: boolean) => {
    setLoading(true);
    getAppAutopsy(appId, llm)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(useLlm); }, [appId]);

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        {[...Array(4)].map((_, i) => <div key={i} className="h-24 rounded-xl bg-gray-100 dark:bg-gray-800" />)}
      </div>
    );
  }

  if (!data) return <p className="text-gray-400">Could not load autopsy data.</p>;

  const trendColor = data.rank_trajectory.trend === 'improving' ? 'text-emerald-600' : data.rank_trajectory.trend === 'declining' ? 'text-red-500' : 'text-gray-500';

  return (
    <div className="space-y-6">
      {/* Narrative */}
      {data.narrative && (
        <div className="rounded-xl border border-violet-200 bg-violet-50 p-5 dark:border-violet-800 dark:bg-violet-950/30">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-violet-800 dark:text-violet-300">
            <FlaskConical className="h-4 w-4" />
            AI Analysis
          </div>
          <p className="text-sm text-violet-900 dark:text-violet-100 leading-relaxed">{data.narrative}</p>
        </div>
      )}

      {/* Strengths */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
        <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">Key Strengths</h3>
        <ul className="space-y-2">
          {data.strengths.map((s, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300">
              <span className="mt-0.5 text-emerald-500">✓</span>
              {s}
            </li>
          ))}
        </ul>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label: 'Rating Momentum', value: `${data.rating_momentum > 0 ? '+' : ''}${data.rating_momentum.toFixed(2)}★`, color: data.rating_momentum > 0 ? 'text-emerald-600' : 'text-red-500' },
          { label: 'Review Growth 30d', value: `${data.review_growth_30d > 0 ? '+' : ''}${data.review_growth_30d.toFixed(0)}%`, color: data.review_growth_30d > 0 ? 'text-emerald-600' : 'text-red-500' },
          { label: 'Rank Trend', value: data.rank_trajectory.trend, color: trendColor },
          { label: 'Updates (90d)', value: String(data.update_cadence.versions_last_90d), color: 'text-gray-900 dark:text-white' },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={cn('mt-1 text-lg font-bold capitalize', color)}>{value}</p>
          </div>
        ))}
      </div>

      {/* Estimates */}
      {(data.estimated_installs_min || data.estimated_revenue_monthly_min) && (
        <div className="grid grid-cols-2 gap-4">
          {data.estimated_installs_min != null && (
            <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-4 dark:border-indigo-800 dark:bg-indigo-950/30">
              <p className="text-xs text-indigo-600 dark:text-indigo-400">Est. Monthly Downloads</p>
              <p className="mt-1 text-xl font-bold text-indigo-900 dark:text-indigo-100">
                {formatRange(data.estimated_installs_min, data.estimated_installs_max)}
              </p>
            </div>
          )}
          {data.estimated_revenue_monthly_min != null && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-800 dark:bg-emerald-950/30">
              <p className="text-xs text-emerald-600 dark:text-emerald-400">Est. Monthly Revenue</p>
              <p className="mt-1 text-xl font-bold text-emerald-900 dark:text-emerald-100">
                {formatRevenue(data.estimated_revenue_monthly_min, data.estimated_revenue_monthly_max)}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Competitor gaps */}
      {data.competitor_feature_gaps.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
          <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">
            What Competitors Are Missing
          </h3>
          <div className="space-y-2">
            {data.competitor_feature_gaps.map((gap) => (
              <div key={gap.feature} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 dark:bg-gray-800">
                <span className="text-sm capitalize text-gray-700 dark:text-gray-300">{gap.feature}</span>
                <div className="flex gap-3 text-xs text-gray-400">
                  <span>{gap.apps_missing} apps missing</span>
                  <span>{gap.total_mentions} mentions</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Re-run without LLM */}
      {!data.narrative && (
        <button
          onClick={() => load(false)}
          className="text-xs text-indigo-600 hover:underline dark:text-indigo-400"
        >
          Regenerate without AI narrative
        </button>
      )}
    </div>
  );
}


export default function AppDetailPage() {
  const params = useParams();
  const router = useRouter();
  const appId = parseInt(params.id as string);
  
  const [app, setApp] = useState<AppDetail | null>(null);
  const [versions, setVersions] = useState<AppVersion[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [analytics, setAnalytics] = useState<AppAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  useEffect(() => {
    async function fetchData() {
      try {
        const [appData, versionsData, reviewsData, analyticsData] = await Promise.all([
          getAppDetail(appId),
          getAppVersions(appId),
          getAppReviews(appId, undefined, 20),
          getAppAnalytics(appId).catch(() => null),
        ]);
        setApp(appData);
        setVersions(versionsData);
        setReviews(reviewsData);
        setAnalytics(analyticsData);
      } catch (error) {
        console.error('Failed to fetch app data:', error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [appId]);

  if (loading) {
    return (
      <AppShell>
        <div className="space-y-6">
          <div className="animate-pulse space-y-4">
            <div className="h-8 bg-gray-200 dark:bg-gray-800 rounded w-1/4"></div>
            <div className="h-32 bg-gray-200 dark:bg-gray-800 rounded"></div>
          </div>
        </div>
      </AppShell>
    );
  }

  if (!app) {
    return (
      <AppShell>
        <div className="text-center py-12">
          <p className="text-gray-500 dark:text-gray-400">App not found</p>
          <button
            onClick={() => router.push('/apps')}
            className="mt-4 text-indigo-600 hover:text-indigo-700"
          >
            Back to Apps
          </button>
        </div>
      </AppShell>
    );
  }

  const tabs: { id: TabType; label: string; icon: React.ElementType }[] = [
    { id: 'overview', label: 'Overview', icon: Star },
    { id: 'versions', label: 'Versions', icon: Calendar },
    { id: 'reviews', label: 'Reviews', icon: MessageSquare },
    { id: 'rankings', label: 'Rankings', icon: TrendingUp },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'market', label: 'Market Weakness', icon: Globe },
    { id: 'gaps', label: 'Feature Gaps', icon: Lightbulb },
    { id: 'keywords', label: 'Keywords', icon: Search },
    { id: 'autopsy', label: 'Autopsy', icon: FlaskConical },
  ];

  return (
    <AppShell>
      <div className="space-y-6">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>

        <AppHeader app={app} />

        <div className="border-b border-gray-200 dark:border-gray-700">
          <nav className="flex space-x-8">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors",
                  activeTab === tab.id
                    ? "border-indigo-500 text-indigo-600 dark:text-indigo-400"
                    : "border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                )}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        <div>
          {activeTab === 'overview' && <OverviewTab app={app} />}
          {activeTab === 'versions' && <VersionsTab versions={versions} />}
          {activeTab === 'reviews' && <ReviewsTab reviews={reviews} appId={appId} />}
          {activeTab === 'rankings' && <RankingsTab appId={appId} />}
          {activeTab === 'analytics' && <AnalyticsTab analytics={analytics} />}
          {activeTab === 'market' && <MarketWeaknessTab appId={appId} />}
          {activeTab === 'gaps' && <FeatureGapsTab appId={appId} />}
          {activeTab === 'keywords' && (
            <div className="space-y-8">
              <div>
                <h3 className="mb-4 text-base font-semibold text-gray-800 dark:text-gray-200">Keyword Intelligence</h3>
                <KeywordIntelligenceTab appId={appId} />
              </div>
              <div>
                <h3 className="mb-4 text-base font-semibold text-gray-800 dark:text-gray-200">Rank History</h3>
                <KeywordHistoryPanel appId={appId} />
              </div>
            </div>
          )}
          {activeTab === 'autopsy' && <AppAutopsyTab appId={appId} />}
        </div>
      </div>
    </AppShell>
  );
}
