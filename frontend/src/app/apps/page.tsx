export const dynamic = 'force-dynamic';

import { Suspense } from 'react';
import AppsClient from './AppsClient';

export default function Page() {
  return (
    <Suspense>
      <AppsClient />
    </Suspense>
  );
}
