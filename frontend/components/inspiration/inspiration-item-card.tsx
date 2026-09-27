'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { ChevronDown } from 'lucide-react';
import { toast } from 'sonner';

import { Card, CardContent } from '@/components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
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
import { WardrobeMatch } from '@/components/inspiration/wardrobe-match';
import { withCurrent, type EditableTags } from '@/lib/item-tags';
import { useClothingColors, useClothingTypes } from '@/lib/hooks/use-translated-constants';
import { useTagOptions } from '@/lib/hooks/use-items';
import {
  useUpdateInspirationLookItem,
  type InspirationLookItem,
  type InspirationLookItemUpdate,
} from '@/lib/hooks/use-inspiration';
import { getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';

interface InspirationItemCardProps {
  lookId: string;
  item: InspirationLookItem;
  /** Whether the look has been matched against the wardrobe (look.matched_at). */
  matched: boolean;
}

/**
 * One AI-identified garment of an inspiration look: the wardrobe piece picked for it
 * (Step 2) up front, and the tag correction (Step 1) behind a toggle. Type/color use
 * the same constants as the wardrobe item editor; the shared tag fields (formality,
 * pattern, material, fit, colors, style, season) reuse ItemTagEditor itself, so this
 * offers exactly the vocabulary the AI tagger and the matching use. Every change saves
 * immediately -- there's no separate "edit mode" here. Correcting a tag the match
 * depends on re-matches the piece on the server.
 */
export function InspirationItemCard({ lookId, item, matched }: InspirationItemCardProps) {
  const t = useTranslations('inspiration.detail');
  const clothingTypes = useClothingTypes();
  const clothingColors = useClothingColors();
  const { data: tagOptions } = useTagOptions();
  const updateItem = useUpdateInspirationLookItem();

  const [description, setDescription] = useState(item.description ?? '');
  // Before the look is matched, correcting tags is all there is to do here.
  const [tagsOpen, setTagsOpen] = useState(!matched);

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

  const typeLabel = clothingTypes.find((ct) => ct.value === item.type)?.label ?? item.type;

  return (
    <Card>
      <CardContent className="space-y-4 p-4">
        <div className="min-w-0">
          <p className="font-medium">{typeLabel}</p>
          {item.description && (
            <p className="text-sm italic text-muted-foreground">&ldquo;{item.description}&rdquo;</p>
          )}
        </div>

        {matched && <WardrobeMatch lookId={lookId} item={item} />}

        <Collapsible open={tagsOpen} onOpenChange={setTagsOpen}>
          <CollapsibleTrigger className="flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground">
            <ChevronDown className={cn('h-4 w-4 transition-transform', tagsOpen && 'rotate-180')} />
            {t('editTags')}
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 pt-3">
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
              <Label htmlFor={`inspiration-item-description-${item.id}`}>
                {t('description')}
              </Label>
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
          </CollapsibleContent>
        </Collapsible>
      </CardContent>
    </Card>
  );
}
