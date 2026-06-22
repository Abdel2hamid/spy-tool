export const dynamic = 'force-dynamic';

import { Suspense } from 'react';
import RankSpySearchClient from './RankSpySearchClient';

export default function Page() {
  return (
    <Suspense>
      <RankSpySearchClient />
    </Suspense>
  );
}
