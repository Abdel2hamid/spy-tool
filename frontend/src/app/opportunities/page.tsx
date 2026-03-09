import { getOpportunityOfDay, getKeywordOpportunities } from '@/lib/api';
import OpportunitiesClient from './OpportunitiesClient';

async function getData() {
  const [opportunity, keywordOpps] = await Promise.all([
    getOpportunityOfDay().catch(() => null),
    getKeywordOpportunities()
      .then((r) => (Array.isArray(r) ? r : []))
      .catch(() => []),
  ]);
  return { opportunity: opportunity ?? null, keywordOpps };
}

export default async function Page() {
  const { opportunity, keywordOpps } = await getData();
  return (
    <OpportunitiesClient
      initialOpportunity={opportunity}
      initialKeywordOpps={keywordOpps}
    />
  );
}
