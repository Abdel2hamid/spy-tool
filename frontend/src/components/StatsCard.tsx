'use client';

import { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

type AccentColor = 'indigo' | 'emerald' | 'amber' | 'purple' | 'cyan';

interface StatsCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: string;
  trendUp?: boolean;
  description?: string;
  accent?: AccentColor;
}

const accentClasses: Record<AccentColor, { icon: string; iconHover: string; bg: string; bgHover: string }> = {
  indigo: {
    icon: 'text-gray-400 dark:text-gray-500',
    iconHover: 'group-hover:text-indigo-600 dark:group-hover:text-indigo-400',
    bg: 'bg-gray-50 dark:bg-gray-800',
    bgHover: 'group-hover:bg-indigo-50 dark:group-hover:bg-indigo-950/50',
  },
  emerald: {
    icon: 'text-gray-400 dark:text-gray-500',
    iconHover: 'group-hover:text-emerald-600 dark:group-hover:text-emerald-400',
    bg: 'bg-gray-50 dark:bg-gray-800',
    bgHover: 'group-hover:bg-emerald-50 dark:group-hover:bg-emerald-950/50',
  },
  amber: {
    icon: 'text-gray-400 dark:text-gray-500',
    iconHover: 'group-hover:text-amber-600 dark:group-hover:text-amber-400',
    bg: 'bg-gray-50 dark:bg-gray-800',
    bgHover: 'group-hover:bg-amber-50 dark:group-hover:bg-amber-950/50',
  },
  purple: {
    icon: 'text-gray-400 dark:text-gray-500',
    iconHover: 'group-hover:text-purple-600 dark:group-hover:text-purple-400',
    bg: 'bg-gray-50 dark:bg-gray-800',
    bgHover: 'group-hover:bg-purple-50 dark:group-hover:bg-purple-950/50',
  },
  cyan: {
    icon: 'text-gray-400 dark:text-gray-500',
    iconHover: 'group-hover:text-cyan-600 dark:group-hover:text-cyan-400',
    bg: 'bg-gray-50 dark:bg-gray-800',
    bgHover: 'group-hover:bg-cyan-50 dark:group-hover:bg-cyan-950/50',
  },
};

export function StatsCard({
  title,
  value,
  icon: Icon,
  trend,
  trendUp,
  description,
  accent = 'indigo',
}: StatsCardProps) {
  const a = accentClasses[accent];
  return (
    <div className="group rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-all duration-200 hover:shadow-md dark:border-gray-800 dark:bg-gray-900">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
            {title}
          </p>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">
            {value}
          </p>
          {description && (
            <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
              {description}
            </p>
          )}
        </div>
        <div className={cn('flex h-10 w-10 items-center justify-center rounded-lg transition-colors', a.bg, a.bgHover)}>
          <Icon className={cn('h-5 w-5 transition-colors', a.icon, a.iconHover)} />
        </div>
      </div>
      {trend && (
        <div className="mt-3 flex items-center gap-1">
          <span
            className={cn(
              'text-sm font-medium',
              trendUp
                ? 'text-emerald-600 dark:text-emerald-400'
                : 'text-red-600 dark:text-red-400'
            )}
          >
            {trend}
          </span>
          <span className="text-xs text-gray-400 dark:text-gray-500">
            vs last week
          </span>
        </div>
      )}
    </div>
  );
}
