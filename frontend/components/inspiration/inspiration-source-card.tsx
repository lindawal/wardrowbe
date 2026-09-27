'use client';

import Link from 'next/link';
import Image from 'next/image';
import { useTranslations } from 'next-intl';
import { Camera } from 'lucide-react';

import { Card, CardContent } from '@/components/ui/card';
import { useInspirationLook } from '@/lib/hooks/use-inspiration';

interface InspirationSourceCardProps {
  lookId: string;
}

/** On an outfit restyled from an inspiration look: a link back to the photo. */
export function InspirationSourceCard({ lookId }: InspirationSourceCardProps) {
  const t = useTranslations('inspiration.source');
  const { data: look } = useInspirationLook(lookId);

  if (!look) return null;

  return (
    <Card className="border-muted bg-muted/30">
      <CardContent className="p-3">
        <Link
          href={`/dashboard/inspiration/${look.id}`}
          className="flex items-center gap-3 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <div className="relative h-12 w-9 shrink-0 overflow-hidden rounded bg-muted">
            {look.photo_thumbnail_url && (
              <Image
                src={look.photo_thumbnail_url}
                alt=""
                fill
                unoptimized
                className="object-cover"
              />
            )}
          </div>
          <Camera className="h-4 w-4 shrink-0" />
          <span className="truncate">{t('inspiredBy')}</span>
        </Link>
      </CardContent>
    </Card>
  );
}
