import { getOpportunityOfDay, getKeywordOpportunities } from '@/lib/api';
import OpportunitiesClient from './OpportunitiesClient';

async function getData() {
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
  const [opportunity, keywordOpps] = await Promise.all([
    fetch(`${API_BASE}/opportunity-of-day`, { cache: 'no-store' }).then(r => r.json()).catch(() => null),
    fetch(`${API_BASE}/keyword-opportunities`, { cache: 'no-store' }).then(r => r.json()).catch(() => []),
  ]);
  return { opportunity, keywordOpps };
}

export default async function Page() {
  const { opportunity, keywordOpps } = await getData();
  return <OpportunitiesClient initialOpportunity={opportunity} initialKeywordOpps={keywordOpps} />;
}
