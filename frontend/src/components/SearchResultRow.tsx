'use client';

import { ExternalLink, Loader2, Plus } from 'lucide-react';
import { AppImportSearchItem } from '@/lib/api';

interface SearchResultRowProps {
  app: AppImportSearchItem;
  isFocused: boolean;
  isImporting: boolean;
  onClick: () => void;
  onMouseEnter: () => void;
}

function AppIcon({ app }: { app: AppImportSearchItem }) {
  const gradient =
    app.source === 'database'
      ? 'from-indigo-400 to-violet-500'
      : 'from-emerald-400 to-cyan-500';

  if (app.icon_url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={app.icon_url}
        alt={app.name}
        className="h-10 w-10 flex-shrink-0 rounded-xl object-cover shadow-sm"
      />
    );
  }

  return (
    <div
      className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${gradient} shadow-sm`}
    >
      <span className="text-sm font-bold text-white">
        {app.name[0]?.toUpperCase()}
      </span>
    </div>
  );
}

export function SearchResultRow({
  app,
  isFocused,
  isImporting,
  onClick,
  onMouseEnter,
}: SearchResultRowProps) {
  const isDB = app.source === 'database';

  const subtitle = [
    app.current_rating ? `★ ${app.current_rating.toFixed(1)}` : null,
    app.developer,
  ]
    .filter(Boolean)
    .join('  ·  ');

  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      disabled={isImporting}
      role="option"
      aria-selected={isFocused}
      className={`group w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors duration-75 outline-none ${
        isFocused
          ? 'bg-gray-50 dark:bg-gray-800/60'
          : 'hover:bg-gray-50/80 dark:hover:bg-gray-800/40'
      } ${isImporting ? 'cursor-not-allowed opacity-70' : 'cursor-pointer'}`}
    >
      <AppIcon app={app} />

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-gray-900 dark:text-white">
          {app.name}
        </p>
        {subtitle && (
          <p className="truncate text-xs text-gray-500 dark:text-gray-400">
            {subtitle}
          </p>
        )}
      </div>

      {/* Action */}
      <div className="flex-shrink-0">
        {isDB ? (
          <span className="flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2 py-1 text-xs font-medium text-gray-500 transition-colors group-hover:border-gray-300 group-hover:text-gray-700 dark:border-gray-700 dark:bg-transparent dark:text-gray-400 dark:group-hover:border-gray-600 dark:group-hover:text-gray-300">
            <ExternalLink className="h-3 w-3" />
            Open
          </span>
        ) : (
          <span
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
              isImporting
                ? 'bg-indigo-50 text-indigo-400 dark:bg-indigo-950/40 dark:text-indigo-400'
                : 'bg-indigo-600 text-white group-hover:bg-indigo-700 dark:bg-indigo-500 dark:group-hover:bg-indigo-600'
            }`}
          >
            {isImporting ? (
              <>
                <Loader2 className="h-3 w-3 animate-spin" />
                Importing…
              </>
            ) : (
              <>
                <Plus className="h-3 w-3" />
                Import
              </>
            )}
          </span>
        )}
      </div>
    </button>
  );
}
