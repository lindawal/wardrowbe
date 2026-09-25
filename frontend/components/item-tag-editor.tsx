'use client';

import type { ReactNode } from 'react';
import { useTranslations } from 'next-intl';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn } from '@/lib/utils';
import type { TagOptions } from '@/lib/types';
import { type EditableTags, withCurrent } from '@/lib/item-tags';
import {
  useFormalityLabel,
  useMaterialLabel,
  usePatternLabel,
  useFitLabel,
  useItemStyleLabel,
  useSeasonLabel,
} from '@/lib/hooks/use-translated-constants';

// Radix Select cannot hold an empty-string value, so "no value" needs a stand-in.
const NONE = '__none__';

type SingleKey = 'formality' | 'pattern' | 'material' | 'fit';
type ListKey = 'colors' | 'style' | 'season';

interface ItemTagEditorProps {
  value: EditableTags;
  onChange: (value: EditableTags) => void;
  options: TagOptions;
  /** Display name and swatch for a color value. */
  describeColor: (value: string) => { name: string; hex?: string };
}

/**
 * Edits the tags the AI tagger sets, offering exactly the values it can assign.
 * Values are shown as stored, matching the tag badges in the item view.
 */
export function ItemTagEditor({ value, onChange, options, describeColor }: ItemTagEditorProps) {
  const t = useTranslations('wardrobe.itemDetail');
  const formalityLabel = useFormalityLabel();
  const materialLabel = useMaterialLabel();
  const patternLabel = usePatternLabel();
  const fitLabel = useFitLabel();
  const itemStyleLabel = useItemStyleLabel();
  const seasonLabel = useSeasonLabel();

  const single = (key: SingleKey, label: string, choices: string[], describe?: (v: string) => string) => (
    <div className="space-y-2">
      <Label>{label}</Label>
      <Select
        value={value[key] ?? NONE}
        onValueChange={(v) => onChange({ ...value, [key]: v === NONE ? null : v })}
      >
        <SelectTrigger aria-label={label}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={NONE}>{t('noValue')}</SelectItem>
          {withCurrent(choices, value[key]).map((choice) => (
            <SelectItem key={choice} value={choice}>
              {describe ? describe(choice) : choice}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );

  const list = (key: ListKey, label: string, choices: string[], render?: (choice: string) => ReactNode) => (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div role="group" aria-label={label} className="flex flex-wrap gap-1.5">
        {withCurrent(choices, value[key]).map((choice) => {
          const selected = value[key].includes(choice);
          return (
            <button
              key={choice}
              type="button"
              aria-pressed={selected}
              onClick={() =>
                onChange({
                  ...value,
                  [key]: selected ? value[key].filter((v) => v !== choice) : [...value[key], choice],
                })
              }
              className={cn(
                'rounded-full border px-2.5 py-0.5 text-xs transition-colors',
                selected
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )}
            >
              {render ? render(choice) : choice}
            </button>
          );
        })}
      </div>
    </div>
  );

  const colorChip = (choice: string) => {
    const { name, hex } = describeColor(choice);
    return (
      <span className="flex items-center gap-1.5">
        {hex && <span className="h-2.5 w-2.5 rounded-full border" style={{ backgroundColor: hex }} />}
        {name}
      </span>
    );
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        {single('formality', t('formality'), options.formality, formalityLabel)}
        {single('pattern', t('pattern'), options.patterns, patternLabel)}
        {single('material', t('material'), options.materials, materialLabel)}
        {single('fit', t('fit'), options.fits, fitLabel)}
      </div>
      {list('colors', t('colors'), options.colors, colorChip)}
      {list('style', t('style'), options.styles, itemStyleLabel)}
      {list('season', t('season'), options.seasons, seasonLabel)}
    </div>
  );
}
