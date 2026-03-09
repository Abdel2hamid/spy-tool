import { getTrendingApps } from '@/lib/api';
import TrendingClient from './TrendingClient';

async function getData() {
  try {
    const trending = await getTrendingApps(20);
    return { trending: Array.isArray(trending) ? trending : [] };
  } catch {
    return { trending: [] };
  }
}

export default async function Page() {
  const { trending } = await getData();
  return <TrendingClient initialApps={trending} />;
}
