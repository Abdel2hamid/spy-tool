import { getTrendingApps } from '@/lib/api';
import TrendingClient from './TrendingClient';

async function getData() {
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
  const trending = await fetch(`${API_BASE}/trending?limit=20`, { cache: 'no-store' })
    .then(r => r.json())
    .catch(() => []);
  return { trending };
}

export default async function Page() {
  const { trending } = await getData();
  return <TrendingClient initialApps={trending} />;
}
