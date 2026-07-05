'use client';

import { useEffect, useState } from 'react';
import { Globe } from 'lucide-react';
import { getCountries, CountryOption } from '@/lib/api';

/**
 * Shared storefront (country) selector. Loads the countries list once from the
 * shared /countries endpoint and drives country-aware views (Top Charts,
 * Trending, Blowing Up, …). Falls back to a single "United States" option
 * while the list loads or if it fails, so the control is always usable.
 */
export function CountrySelect({
  value,
  onChange,
  className,
}: {
  value: string;
  onChange: (code: string) => void;
  className?: string;
}) {
  const [countries, setCountries] = useState<CountryOption[]>([]);

  useEffect(() => {
    let alive = true;
    getCountries()
      .then((c) => { if (alive) setCountries(c); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  return (
    <div className={`relative ${className ?? ''}`}>
      <Globe className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-gray-200 bg-white py-1.5 pl-8 pr-3 text-sm text-gray-900 focus:border-indigo-500 focus:outline-none dark:border-gray-800 dark:bg-gray-900 dark:text-white"
        aria-label="Storefront"
      >
        {countries.length === 0 && <option value="us">United States</option>}
        {countries.map((c) => (
          <option key={c.code} value={c.code}>{c.name}</option>
        ))}
      </select>
    </div>
  );
}
