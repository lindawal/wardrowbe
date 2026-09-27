'use client';

import { useState } from 'react';
import Image from 'next/image';
import { useTranslations } from 'next-intl';
import { ArrowLeftRight, X } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { WardrobeItemPickerDialog } from '@/components/inspiration/wardrobe-item-picker-dialog';
import { useClothingTypes, useItemDisplayName } from '@/lib/hooks/use-translated-constants';
import {
  useSetInspirationMatch,
  type InspirationLookItem,
  type WardrobeItemSummary,
} from '@/lib/hooks/use-inspiration';
import { getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';

function MatchThumb({ item, className }: { item: WardrobeItemSummary; className?: string }) {
  const itemDisplayName = useItemDisplayName();
  const clothingTypes = useClothingTypes();
  const src = item.thumbnail_url || item.image_url;

  return (
    <div className={cn('relative shrink-0 overflow-hidden rounded-md border bg-muted', className)}>
      {src ? (
        <Image
          src={src}
          alt={itemDisplayName(item)}
          fill
          className="object-cover"
          sizes="80px"
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center p-1">
          <span className="text-center text-[10px] text-muted-foreground">
            {clothingTypes.find((ct) => ct.value === item.type)?.label ?? item.type}
          </span>
        </div>
      )}
    </div>
  );
}

interface WardrobeMatchProps {
  lookId: string;
  item: InspirationLookItem;
}

/**
 * The wardrobe side of one inspiration slot: the current pick, the other suggested
 * pieces as one-click alternatives, and a picker for anything else. Every change
 * saves immediately, like the tag editor next to it.
 */
export function WardrobeMatch({ lookId, item }: WardrobeMatchProps) {
  const t = useTranslations('inspiration.match');
  const itemDisplayName = useItemDisplayName();
  const setMatch = useSetInspirationMatch();
  const [pickerOpen, setPickerOpen] = useState(false);

  const matched = item.matched_item;
  const alternatives = item.suggested_items.filter((s) => s.id !== matched?.id);

  const pick = (wardrobeItemId: string | null) => {
    setMatch.mutate(
      { lookId, itemId: item.id, wardrobeItemId },
      { onError: (error) => toast.error(getErrorMessage(error, t('updateError'))) }
    );
  };

  return (
    <div className="space-y-3">
      <Label>{t('fromWardrobe')}</Label>

      {matched ? (
        <div className="flex items-center gap-3">
          <MatchThumb item={matched} className="h-20 w-20" />
          <p className="min-w-0 flex-1 truncate text-sm font-medium">{itemDisplayName(matched)}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setPickerOpen(true)}
            disabled={setMatch.isPending}
          >
            <ArrowLeftRight className="mr-1.5 h-4 w-4" />
            {t('swap')}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={t('leaveOut')}
            title={t('leaveOut')}
            onClick={() => pick(null)}
            disabled={setMatch.isPending}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      ) : (
        <div className="flex items-center justify-between gap-3 rounded-md border border-dashed p-3">
          <p className="text-sm text-muted-foreground">
            {item.suggested_items.length > 0 ? t('nothingPicked') : t('noMatch')}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setPickerOpen(true)}
            disabled={setMatch.isPending}
          >
            {t('choose')}
          </Button>
        </div>
      )}

      {alternatives.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs text-muted-foreground">{t('alternatives')}</p>
          <div className="flex flex-wrap items-center gap-2">
            {alternatives.map((alt) => (
              <button
                key={alt.id}
                type="button"
                onClick={() => pick(alt.id)}
                disabled={setMatch.isPending}
                aria-label={t('pickAlternative', { name: itemDisplayName(alt) })}
                title={itemDisplayName(alt)}
                className="rounded-md transition-opacity hover:opacity-80 disabled:opacity-50"
              >
                <MatchThumb item={alt} className="h-14 w-14" />
              </button>
            ))}
            <Button
              type="button"
              variant="link"
              size="sm"
              className="px-1"
              onClick={() => setPickerOpen(true)}
            >
              {t('showAll')}
            </Button>
          </div>
        </div>
      )}

      <WardrobeItemPickerDialog
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        itemType={item.type}
        selectedId={matched?.id ?? null}
        onSelect={(picked) => pick(picked.id)}
      />
    </div>
  );
}
