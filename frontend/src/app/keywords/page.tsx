import { getKeywords, getKeywordOpportunities } from '@/lib/api';
import KeywordsClient from './KeywordsClient';

async function getData() {
  const [keywords, keywordOpps] = await Promise.all([
    getKeywords(50)
      .then((r) => (Array.isArray(r) ? r : []))
      .catch(() => []),
    getKeywordOpportunities()
      .then((r) => (Array.isArray(r) ? r : []))
      .catch(() => []),
  ]);
  return { keywords, keywordOpps };
}

export default async function Page() {
  const { keywords, keywordOpps } = await getData();
  return (
    <KeywordsClient
      initialKeywords={keywords}
      initialKeywordOpps={keywordOpps}
    />
  );
}
