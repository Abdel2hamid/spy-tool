// Niche Radar has been merged into the Opportunities hub.
// This redirect preserves old bookmarks.
import { redirect } from 'next/navigation';

export default function NicheRadarPage() {
  redirect('/opportunities?tab=niches');
}
