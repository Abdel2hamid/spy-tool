import { getKeywords, getKeywordOpportunities } from '@/lib/api';
import KeywordsClient from './KeywordsClient';

async function getData() {
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
  const [keywords, keywordOpps] = await Promise.all([
    fetch(`${API_BASE}/keywords?limit=50`, { cache: 'no-store' }).then(r => r.json()).catch(() => []),
    fetch(`${API_BASE}/keyword-opportunities`, { cache: 'no-store' }).then(r => r.json()).catch(() => []),
  ]);
  return { keywords, keywordOpps };
}

export default async function Page() {
  const { keywords, keywordOpps } = await getData();
  return <KeywordsClient initialKeywords={keywords} initialKeywordOpps={keywordOpps} />;
}
