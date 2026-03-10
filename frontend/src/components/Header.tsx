'use client';

import { useState } from 'react';
import { Menu, Search, Bell, X } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { ThemeToggle } from './ThemeToggle';

interface HeaderProps {
  onMenuClick: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [focused, setFocused] = useState(false);
  const router = useRouter();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/apps?search=${encodeURIComponent(searchQuery.trim())}`);
      setSearchQuery('');
    }
  };

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

        {/* Search bar */}
        <form onSubmit={handleSearch} className="hidden sm:block">
          <div
            className={`flex items-center gap-2 rounded-lg border px-3 py-2 transition-all duration-200 ${
              focused
                ? 'border-indigo-300 bg-white shadow-sm shadow-indigo-100 dark:border-indigo-700 dark:bg-gray-900 dark:shadow-indigo-900/20'
                : 'border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900'
            }`}
          >
            <Search className="h-4 w-4 flex-shrink-0 text-gray-400" />
            <input
              type="text"
              placeholder="Search apps, keywords…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              className="w-56 bg-transparent text-sm text-gray-900 placeholder-gray-400 focus:outline-none dark:text-white dark:placeholder-gray-500 lg:w-72"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </form>
      </div>

      {/* Right: actions */}
      <div className="flex items-center gap-1.5">
        <ThemeToggle />

        {/* Notification bell */}
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
