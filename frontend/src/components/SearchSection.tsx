'use client';

import { ReactNode } from 'react';

interface SearchSectionProps {
  title: string;
  children: ReactNode;
}

export function SearchSection({ title, children }: SearchSectionProps) {
  return (
    <div>
      <div className="px-4 pb-1 pt-3">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500">
          {title}
        </span>
      </div>
      <div role="group" aria-label={title}>
        {children}
      </div>
    </div>
  );
}
