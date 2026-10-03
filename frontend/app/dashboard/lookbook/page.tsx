import { redirect } from 'next/navigation';

// The lookbook is now the "Lookbook" chip on the outfits page. Old links and bookmarks
// (including ?tag=&season=&weather=&q=&item=) keep working through this redirect.
export default function LookbookRedirect({
  searchParams,
}: {
  searchParams: Record<string, string | string[] | undefined>;
}) {
  const params = new URLSearchParams();
  for (const key of ['tag', 'season', 'weather', 'q', 'item']) {
    const value = searchParams[key];
    if (typeof value === 'string' && value) params.set(key, value);
  }
  params.set('filter', 'my-looks');
  redirect(`/dashboard/outfits?${params.toString()}`);
}
