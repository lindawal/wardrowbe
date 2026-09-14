'use client';

import { useState, type KeyboardEvent, type MouseEvent } from 'react';
import { X } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { addTag, formatTag, normalizeTag, removeTag, type AddTagError } from '@/lib/lookbook/tags';
import { MAX_TAG_LENGTH, MAX_TAGS } from '@/lib/lookbook/vocab';

const MAX_SUGGESTIONS = 8;

interface TagInputProps {
  id?: string;
  value: string[];
  onChange: (tags: string[]) => void;
  suggestions?: string[];
  disabled?: boolean;
}

// Buttons next to the input must not steal focus, or the blur commit would add the half-typed text.
const keepFocus = (e: MouseEvent) => e.preventDefault();

export function TagInput({ id, value, onChange, suggestions = [], disabled }: TagInputProps) {
  const t = useTranslations('lookbook.attributes');
  const [draft, setDraft] = useState('');

  const errorMessage = (error: AddTagError) =>
    error === 'tooMany'
      ? t('tooManyTags', { max: MAX_TAGS })
      : error === 'tooLong'
        ? t('tagTooLong', { max: MAX_TAG_LENGTH })
        : t('invalidTag');

  const commit = (raw: string) => {
    let tags = value;
    for (const part of raw.split(',')) {
      if (!part.trim()) continue;
      const result = addTag(tags, part);
      if (result.error) {
        toast.error(errorMessage(result.error));
        break;
      }
      tags = result.tags;
    }
    if (tags !== value) onChange(tags);
    setDraft('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      commit(draft);
    } else if (e.key === 'Backspace' && !draft && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  };

  const query = normalizeTag(draft) ?? '';
  const visibleSuggestions = suggestions
    .filter((s) => !value.includes(s) && s.startsWith(query))
    .slice(0, MAX_SUGGESTIONS);
  const full = value.length >= MAX_TAGS;

  return (
    <div className="space-y-2">
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((tag) => (
            <Badge key={tag} variant="secondary" className="gap-1 pr-1">
              {formatTag(tag)}
              <button
                type="button"
                onMouseDown={keepFocus}
                onClick={() => onChange(removeTag(value, tag))}
                disabled={disabled}
                className="rounded-full p-0.5 hover:bg-muted-foreground/20"
                aria-label={t('removeTag', { tag: formatTag(tag) })}
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
      <Input
        id={id}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => commit(draft)}
        placeholder={full ? t('tagLimitReached', { max: MAX_TAGS }) : t('addTagPlaceholder')}
        disabled={disabled || full}
      />
      {!full && visibleSuggestions.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-muted-foreground">{t('suggestions')}</span>
          {visibleSuggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onMouseDown={keepFocus}
              onClick={() => commit(suggestion)}
              disabled={disabled}
            >
              <Badge variant="outline" className="cursor-pointer hover:bg-accent">
                {formatTag(suggestion)}
              </Badge>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
