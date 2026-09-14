import type { ReactNode } from 'react';
import { redirect } from 'next/navigation';
import { FAMILY_ENABLED } from '@/lib/features';

export default function FamilyLayout({ children }: { children: ReactNode }) {
  if (!FAMILY_ENABLED) redirect('/dashboard');
  return <>{children}</>;
}
