// AI Opportunities has been merged into the Opportunities hub.
// This redirect preserves old bookmarks.
import { redirect } from 'next/navigation';

export default function IdeasPage() {
  redirect('/opportunities?tab=ideas');
}
