'use client';

import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useTranslations } from 'next-intl';
import { AlertTriangle, Loader2, Sparkles, Upload } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { InspirationUploadDialog } from '@/components/inspiration/inspiration-upload-dialog';
import { useInspirationLooks, type InspirationLook } from '@/lib/hooks/use-inspiration';

function StatusBadge({ status }: { status: InspirationLook['status'] }) {
  const t = useTranslations('inspiration.status');
  const variant = status === 'error' ? 'destructive' : status === 'analyzed' ? 'default' : 'secondary';

  return (
    <Badge variant={variant} className="gap-1">
      {(status === 'pending' || status === 'analyzing') && (
        <Loader2 className="h-3 w-3 animate-spin" />
      )}
      {status === 'error' && <AlertTriangle className="h-3 w-3" />}
      {t(status)}
    </Badge>
  );
}

function EmptyState({ onUpload }: { onUpload: () => void }) {
  const t = useTranslations('inspiration');
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="rounded-full bg-muted p-6 mb-4">
        <Sparkles className="h-12 w-12 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-semibold mb-2">{t('empty.title')}</h3>
      <p className="text-muted-foreground mb-6 max-w-sm">{t('empty.description')}</p>
      <Button onClick={onUpload}>
        <Upload className="h-4 w-4 mr-2" />
        {t('empty.upload')}
      </Button>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
      {[1, 2, 3, 4].map((i) => (
        <Skeleton key={i} className="aspect-[3/4] w-full rounded-lg" />
      ))}
    </div>
  );
}

export default function InspirationPage() {
  const t = useTranslations('inspiration');
  const { data, isLoading, isError } = useInspirationLooks();
  const [uploadOpen, setUploadOpen] = useState(false);

  if (isError) {
    return <div className="text-center py-8 text-red-500">{t('loadError')}</div>;
  }

  const looks = data?.looks ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-primary" />
            {t('title')}
          </h1>
          <p className="text-muted-foreground">{t('subtitle')}</p>
        </div>
        {!isLoading && looks.length > 0 && (
          <Button onClick={() => setUploadOpen(true)}>
            <Upload className="h-4 w-4 mr-2" />
            {t('uploadButton')}
          </Button>
        )}
      </div>

      {isLoading ? (
        <LoadingSkeleton />
      ) : looks.length === 0 ? (
        <EmptyState onUpload={() => setUploadOpen(true)} />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
          {looks.map((look) => (
            <Link key={look.id} href={`/dashboard/inspiration/${look.id}`}>
              <Card className="overflow-hidden transition-colors hover:border-primary/50">
                <div className="relative aspect-[3/4] w-full bg-muted">
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
                <CardContent className="p-3">
                  <StatusBadge status={look.status} />
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}

      <InspirationUploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />
    </div>
  );
}
