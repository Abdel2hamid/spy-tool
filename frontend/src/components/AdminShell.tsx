'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { cn } from '@/lib/utils';
import {
  Shield,
  BarChart3,
  Users,
  Clock,
  Server,
  LogOut,
  Menu,
  X,
  Activity,
  Megaphone,
  Settings,
} from 'lucide-react';
import { ThemeToggle } from './ThemeToggle';

const adminNav = [
  { href: '/admin', label: 'Dashboard', icon: BarChart3 },
  { href: '/admin/users', label: 'Users & Accounts', icon: Users },
  { href: '/admin/jobs', label: 'Scheduler Jobs', icon: Clock },
  { href: '/admin/announcements', label: 'Announcements', icon: Megaphone },
  { href: '/admin/activity', label: 'Activity Log', icon: Activity },
  { href: '/admin/system', label: 'System Health', icon: Server },
  { href: '/admin/settings', label: 'Settings', icon: Settings },
];

function AdminNavLink({
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
        'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all',
        isActive
          ? 'bg-red-50 text-red-700 dark:bg-red-950/60 dark:text-red-300'
          : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800/80 dark:hover:text-white',
      )}
    >
      <Icon
        className={cn(
          'h-4 w-4 flex-shrink-0 transition-colors',
          isActive
            ? 'text-red-600 dark:text-red-400'
            : 'text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300',
        )}
      />
      <span>{label}</span>
      {isActive && (
        <span className="ml-auto h-1.5 w-1.5 rounded-full bg-red-500 dark:bg-red-400" />
      )}
    </Link>
  );
}

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isLoading, isAuthenticated, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Redirect if not superadmin
  useEffect(() => {
    if (!isLoading && (!isAuthenticated || !user?.is_superadmin)) {
      router.replace('/login');
    }
  }, [isLoading, isAuthenticated, user, router]);

  if (isLoading || !user?.is_superadmin) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="w-8 h-8 border-2 border-red-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  function handleLogout() {
    logout();
    router.push('/login');
  }

  const sidebarContent = (
    <>
      {/* Logo */}
      <div className="flex h-16 flex-shrink-0 items-center border-b border-gray-200 px-5 dark:border-gray-800">
        <Link href="/admin" className="flex items-center gap-2.5 group">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-red-500 to-orange-500 shadow-sm transition-transform group-hover:scale-105">
            <Shield className="h-4 w-4 text-white" />
          </div>
          <div>
            <span className="block text-sm font-bold text-gray-900 dark:text-white leading-tight">
              RankSpy
            </span>
            <span className="block text-[10px] font-medium text-red-500 dark:text-red-400 uppercase tracking-wider leading-tight">
              Admin Console
            </span>
          </div>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-600">
          MANAGEMENT
        </p>
        {adminNav.map((item) => (
          <AdminNavLink
            key={item.href}
            href={item.href}
            label={item.label}
            icon={item.icon}
            isActive={pathname === item.href}
            onClick={() => setMobileOpen(false)}
          />
        ))}
      </nav>

      {/* Footer */}
      <div className="flex-shrink-0 border-t border-gray-200 p-4 dark:border-gray-800 space-y-3">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 flex-shrink-0 rounded-full bg-gradient-to-br from-red-400 to-orange-500 flex items-center justify-center text-white text-xs font-bold">
            {user.full_name?.[0]?.toUpperCase() || user.email[0].toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-gray-900 dark:text-white">
              {user.full_name || user.email}
            </p>
            <p className="truncate text-xs text-red-500 dark:text-red-400 font-medium">Superadmin</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/50 transition"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      {/* Desktop sidebar */}
      <aside className="fixed left-0 top-0 z-40 hidden h-screen w-64 lg:block">
        <div className="flex h-full flex-col border-r border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950">
          {sidebarContent}
        </div>
      </aside>

      {/* Mobile sidebar */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
          <aside className="fixed left-0 top-0 h-full w-64 shadow-xl">
            <div className="flex h-full flex-col bg-white dark:bg-gray-950">
              <div className="absolute right-2 top-4 z-10">
                <button onClick={() => setMobileOpen(false)} className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800">
                  <X className="h-5 w-5" />
                </button>
              </div>
              {sidebarContent}
            </div>
          </aside>
        </div>
      )}

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Admin header */}
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-4 border-b border-gray-200 bg-white/90 px-4 backdrop-blur-md dark:border-gray-800 dark:bg-gray-950/90 lg:px-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen(true)}
              className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 lg:hidden dark:text-gray-400 dark:hover:bg-gray-800"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="hidden sm:flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
              <Shield className="h-4 w-4 text-red-500" />
              <span className="font-medium text-gray-700 dark:text-gray-300">Admin Console</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
          </div>
        </header>

        <main className="p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
