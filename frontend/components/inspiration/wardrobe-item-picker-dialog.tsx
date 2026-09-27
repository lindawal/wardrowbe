'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ItemPicker } from '@/components/shared/item-picker';
import { useClothingTypes } from '@/lib/hooks/use-translated-constants';
import type { Item } from '@/lib/types';

interface WardrobeItemPickerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The type AI identified; the picker starts filtered to it. */
  itemType: string;
  selectedId: string | null;
  onSelect: (item: Item) => void;
}

/**
 * "Show all" for one inspiration slot: any wardrobe item can be picked, starting
 * with the detected type and switchable to the whole wardrobe.
 */
export function WardrobeItemPickerDialog({
  open,
  onOpenChange,
  itemType,
  selectedId,
  onSelect,
}: WardrobeItemPickerDialogProps) {
  const t = useTranslations('inspiration.match');
  const clothingTypes = useClothingTypes();
  const [showAllTypes, setShowAllTypes] = useState(false);

  const typeLabel = clothingTypes.find((ct) => ct.value === itemType)?.label ?? itemType;
  const filterType = showAllTypes ? undefined : itemType;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setShowAllTypes(false);
        onOpenChange(next);
      }}
    >
      <DialogContent className="sm:max-w-xl max-h-[85vh] flex flex-col p-6">
        <DialogHeader>
          <DialogTitle>{t('pickerTitle')}</DialogTitle>
          <DialogDescription>{t('pickerDescription')}</DialogDescription>
        </DialogHeader>

        <div className="flex gap-1.5 py-1">
          <Button
            type="button"
            variant={showAllTypes ? 'outline' : 'default'}
            size="sm"
            className="text-xs h-7 px-2.5 rounded-full"
            onClick={() => setShowAllTypes(false)}
          >
            {t('onlyType', { type: typeLabel })}
          </Button>
          <Button
            type="button"
            variant={showAllTypes ? 'default' : 'outline'}
            size="sm"
            className="text-xs h-7 px-2.5 rounded-full"
            onClick={() => setShowAllTypes(true)}
          >
            {t('allTypes')}
          </Button>
        </div>

        <div className="flex-1 overflow-hidden min-h-0 pt-1">
          <ItemPicker
            key={filterType ?? 'all'}
            selectedIds={selectedId ? new Set([selectedId]) : new Set()}
            onToggle={(item) => {
              onSelect(item);
              setShowAllTypes(false);
              onOpenChange(false);
            }}
            filterType={filterType}
            // Matching doesn't skip items waiting for the wash either.
            hideNeedsWash={false}
            emptyMessage={t('pickerEmpty')}
            heightClass="h-[340px]"
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
