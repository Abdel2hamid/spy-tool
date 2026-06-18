export const dynamic = 'force-dynamic';

import MyAppDetailClient from './MyAppDetailClient';

export default function Page({ params }: { params: { id: string } }) {
  return <MyAppDetailClient appId={Number(params.id)} />;
}
