import { redirect } from 'next/navigation';

// Pairings are now the "Kombinationen" chip on the outfits page.
export default function PairingsRedirect({
  searchParams,
}: {
  searchParams: Record<string, string | string[] | undefined>;
}) {
  const params = new URLSearchParams({ filter: 'pairings' });
  const item = searchParams.item;
  if (typeof item === 'string' && item) params.set('item', item);
  redirect(`/dashboard/outfits?${params.toString()}`);
}
