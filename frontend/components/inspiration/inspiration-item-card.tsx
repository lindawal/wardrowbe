'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { toast } from 'sonner';

import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ItemTagEditor } from '@/components/item-tag-editor';
import { withCurrent, type EditableTags } from '@/lib/item-tags';
import { useClothingColors, useClothingTypes } from '@/lib/hooks/use-translated-constants';
import { useTagOptions } from '@/lib/hooks/use-items';
import {
  useUpdateInspirationLookItem,
  type InspirationLookItem,
  type InspirationLookItemUpdate,
} from '@/lib/hooks/use-inspiration';
import { getErrorMessage } from '@/lib/api';

interface InspirationItemCardProps {
  lookId: string;
  item: InspirationLookItem;
}

/**
 * Editor for one AI-identified garment within an inspiration look. Type/color use
 * the same constants as the wardrobe item editor; the shared tag fields (formality,
 * pattern, material, fit, colors, style, season) reuse ItemTagEditor itself, so this
 * offers exactly the vocabulary the AI tagger (and, later, Step 2's matching) can use.
 * Every change saves immediately -- there's no separate "edit mode" here.
 */
export function InspirationItemCard({ lookId, item }: InspirationItemCardProps) {
  const t = useTranslations('inspiration.detail');
  const clothingTypes = useClothingTypes();
  const clothingColors = useClothingColors();
  const { data: tagOptions } = useTagOptions();
  const updateItem = useUpdateInspirationLookItem();

  const [description, setDescription] = useState(item.description ?? '');

  const describeColor = (value: string) => {
    const known = clothingColors.find((c) => c.value === value);
    return known ? { name: known.name, hex: known.hex } : { name: value };
  };

  const tags: EditableTags = {
    formality: item.formality,
    pattern: item.pattern,
    material: item.material,
    fit: item.fit,
    colors: item.colors,
    style: item.style,
    season: item.season,
  };

  const save = (updates: InspirationLookItemUpdate) => {
    updateItem.mutate(
      { lookId, itemId: item.id, updates },
      { onError: (error) => toast.error(getErrorMessage(error, t('updateError'))) }
    );
  };

  const primaryColorChoices = tagOptions
    ? withCurrent(tagOptions.colors, item.primary_color)
    : clothingColors.map((c) => c.value);

  return (
    <Card>
      <CardContent className="space-y-4 p-4">
        {item.description && (
          <p className="text-sm italic text-muted-foreground">&ldquo;{item.description}&rdquo;</p>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label>{t('type')}</Label>
            <Select value={item.type} onValueChange={(v) => save({ type: v })}>
              <SelectTrigger aria-label={t('type')}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {withCurrent(
                  clothingTypes.map((ct) => ct.value),
                  item.type
                ).map((value) => (
                  <SelectItem key={value} value={value}>
                    {clothingTypes.find((ct) => ct.value === value)?.label ?? value}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>{t('primaryColor')}</Label>
            <Select
              value={item.primary_color ?? ''}
              onValueChange={(v) => save({ primary_color: v })}
            >
              <SelectTrigger aria-label={t('primaryColor')}>
                <SelectValue placeholder={t('noValue')} />
              </SelectTrigger>
              <SelectContent>
                {primaryColorChoices.map((value) => {
                  const { name, hex } = describeColor(value);
                  return (
                    <SelectItem key={value} value={value}>
                      <div className="flex items-center gap-2">
                        <div
                          className="h-3 w-3 rounded-full border"
                          style={{ backgroundColor: hex }}
                        />
                        {name}
                      </div>
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          </div>
        </div>

        {tagOptions && (
          <ItemTagEditor
            value={tags}
            onChange={(next) => save(next)}
            options={tagOptions}
            describeColor={describeColor}
          />
        )}

        <div className="space-y-2">
          <Label htmlFor={`inspiration-item-description-${item.id}`}>{t('description')}</Label>
          <Input
            id={`inspiration-item-description-${item.id}`}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onBlur={() => {
              const next = description.trim();
              if (next !== (item.description ?? '')) {
                save({ description: next || null });
              }
            }}
            placeholder={t('descriptionPlaceholder')}
          />
        </div>
      </CardContent>
    </Card>
  );
}
