'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  TrendingUp,
  Target,
  Search,
  AppWindow,
  BarChart3,
  Settings,
  Zap,
  Flame,
  Megaphone,
  TrendingUp as CampaignIcon,
  X,
  Users,
  Bell,
  Star,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const navSections = [
  {
    label: 'DISCOVER',
    items: [
      { href: '/', label: 'Dashboard', icon: LayoutDashboard },
      { href: '/apps', label: 'Apps', icon: AppWindow },
      { href: '/latest-apps', label: 'New Releases', icon: Zap },
      { href: '/trending', label: 'Trending', icon: TrendingUp },
    ],
  },
  {
    label: 'GROWTH INTELLIGENCE',
    items: [
      { href: '/blowing-up', label: 'Blowing Up', icon: Flame },
      { href: '/campaigns', label: 'Campaigns', icon: CampaignIcon },
      { href: '/ads', label: 'Ad Intelligence', icon: Megaphone },
    ],
  },
  {
    label: 'INTELLIGENCE',
    items: [
      { href: '/opportunities', label: 'Opportunities', icon: Target },
      { href: '/keywords', label: 'Keywords', icon: Search },
      { href: '/rankings', label: 'Rankings', icon: BarChart3 },
    ],
  },
  {
    label: 'TOOLS',
    items: [
      { href: '/competitors', label: 'Competitors', icon: Users },
      { href: '/alerts', label: 'Alerts', icon: Bell },
      { href: '/settings', label: 'Settings', icon: Settings },
    ],
  },
];

// Flat list for mobile (same order)
const allNavItems = navSections.flatMap(s => s.items);

function NavLink({
  href,
  label,
  icon: Icon,
  isActive,
  onClick,
}: {
  href: string;
  label: string;
  icon: React.ElementType;
  isActive: boolean;
  onClick?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className={cn(
        'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150',
        isActive
          ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300'
          : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800/80 dark:hover:text-white',
      )}
    >
      <Icon
        className={cn(
          'h-4 w-4 flex-shrink-0 transition-colors',
          isActive
            ? 'text-indigo-600 dark:text-indigo-400'
            : 'text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300',
        )}
      />
      <span>{label}</span>
      {isActive && (
        <span className="ml-auto h-1.5 w-1.5 rounded-full bg-indigo-500 dark:bg-indigo-400" />
      )}
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-64">
      <div className="flex h-full flex-col border-r border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950">
        {/* Logo */}
        <div className="flex h-16 flex-shrink-0 items-center border-b border-gray-200 px-5 dark:border-gray-800">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 shadow-sm shadow-indigo-200 dark:shadow-indigo-900 transition-transform group-hover:scale-105">
              <Zap className="h-4 w-4 text-white" />
            </div>
            <div>
              <span className="block text-sm font-bold text-gray-900 dark:text-white leading-tight">
                AppStore Spy
              </span>
              <span className="block text-[10px] font-medium text-indigo-500 dark:text-indigo-400 uppercase tracking-wider leading-tight">
                AI Intelligence
              </span>
            </div>
          </Link>
        </div>

        {/* Nav sections */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
          {navSections.map((section) => (
            <div key={section.label}>
              <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-600">
                {section.label}
              </p>
              <div className="space-y-0.5">
                {section.items.map((item) => (
                  <NavLink
                    key={item.href}
                    href={item.href}
                    label={item.label}
                    icon={item.icon}
                    isActive={pathname === item.href}
                  />
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer user */}
        <div className="flex-shrink-0 border-t border-gray-200 p-4 dark:border-gray-800">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="h-8 w-8 flex-shrink-0 rounded-full bg-gradient-to-br from-emerald-400 to-cyan-500" />
              <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border-2 border-white bg-emerald-400 dark:border-gray-950" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-gray-900 dark:text-white">Admin</p>
              <p className="truncate text-xs text-gray-400">admin@appstore.ai</p>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}

export function MobileSidebar({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const pathname = usePathname();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />
      <aside className="fixed left-0 top-0 h-full w-64 shadow-xl">
        <div className="flex h-full flex-col bg-white dark:bg-gray-950">
          {/* Mobile header */}
          <div className="flex h-16 items-center justify-between border-b border-gray-200 px-4 dark:border-gray-800">
            <Link href="/" className="flex items-center gap-2.5" onClick={onClose}>
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600">
                <Zap className="h-4 w-4 text-white" />
              </div>
              <span className="font-bold text-gray-900 dark:text-white">AppStore Spy</span>
            </Link>
            <button
              onClick={onClose}
              className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800"
              aria-label="Close menu"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Mobile nav */}
          <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
            {navSections.map((section) => (
              <div key={section.label}>
                <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-600">
                  {section.label}
                </p>
                <div className="space-y-0.5">
                  {section.items.map((item) => (
                    <NavLink
                      key={item.href}
                      href={item.href}
                      label={item.label}
                      icon={item.icon}
                      isActive={pathname === item.href}
                      onClick={onClose}
                    />
                  ))}
                </div>
              </div>
            ))}
          </nav>
        </div>
      </aside>
    </div>
  );
}
