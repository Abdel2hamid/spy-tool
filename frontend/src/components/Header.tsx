'use client';

import { Menu, Bell } from 'lucide-react';
import { ThemeToggle } from './ThemeToggle';
import { SearchDropdown } from './SearchDropdown';

interface HeaderProps {
  onMenuClick: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
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
        <SearchDropdown />
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
