'use client';

import Link from 'next/link';
import Image from 'next/image';
import { useParams, useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { AlertTriangle, ChevronLeft, Loader2, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { InspirationItemCard } from '@/components/inspiration/inspiration-item-card';
import { useDeleteInspirationLook, useInspirationLook } from '@/lib/hooks/use-inspiration';
import { getErrorMessage } from '@/lib/api';

export default function InspirationLookDetailPage() {
  const t = useTranslations('inspiration.detail');
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const lookId = params?.id;

  const { data: look, isLoading, isError } = useInspirationLook(lookId);
  const deleteMutation = useDeleteInspirationLook();

  const handleDelete = async () => {
    if (!look) return;
    if (!confirm(t('deleteConfirm'))) return;
    try {
      await deleteMutation.mutateAsync(look.id);
      toast.success(t('deleted'));
      router.push('/dashboard/inspiration');
    } catch (error) {
      toast.error(getErrorMessage(error, t('deleteError')));
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-40" />
        <div className="grid gap-6 md:grid-cols-[320px_1fr]">
          <Skeleton className="aspect-[3/4] w-full rounded-lg" />
          <Skeleton className="h-64 w-full rounded-lg" />
        </div>
      </div>
    );
  }

  if (isError || !look) {
    return <div className="py-8 text-center text-muted-foreground">{t('notFound')}</div>;
  }

  const isBusy = look.status === 'pending' || look.status === 'analyzing';

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" asChild className="-ml-2">
        <Link href="/dashboard/inspiration">
          <ChevronLeft className="mr-1 h-4 w-4" />
          {t('backToList')}
        </Link>
      </Button>

      <div className="grid gap-6 md:grid-cols-[320px_1fr]">
        <div className="space-y-3">
          <div className="relative aspect-[3/4] w-full overflow-hidden rounded-lg bg-muted">
            {look.photo_medium_url && (
              <Image src={look.photo_medium_url} alt="" fill unoptimized className="object-cover" />
            )}
          </div>
          <Button
            variant="outline"
            className="w-full text-destructive hover:text-destructive"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            {t('deleteLook')}
          </Button>
        </div>

        <div className="space-y-4">
          {isBusy && (
            <Alert>
              <Loader2 className="h-4 w-4 animate-spin" />
              <AlertDescription>{t('analyzing')}</AlertDescription>
            </Alert>
          )}

          {look.status === 'error' && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                {look.error_message || t('errorTitle')}
                <br />
                {t('retryHint')}
              </AlertDescription>
            </Alert>
          )}

          {look.status === 'analyzed' && (
            <>
              <h2 className="text-lg font-semibold">{t('itemsTitle')}</h2>
              {look.items.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t('noItems')}</p>
              ) : (
                <div className="space-y-4">
                  {look.items.map((item) => (
                    <InspirationItemCard key={item.id} lookId={look.id} item={item} />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
