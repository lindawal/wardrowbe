import { MAX_TAG_LENGTH, MAX_TAGS } from '@/lib/lookbook/vocab';

export type AddTagError = 'invalid' | 'tooLong' | 'tooMany';

// Same rules as normalize_tags in backend/app/utils/lookbook.py: tags are stored lowercase.
export function normalizeTag(raw: string): string | null {
  const tag = raw.split(/\s+/).filter(Boolean).join(' ').toLowerCase();
  return tag || null;
}

export function addTag(tags: string[], raw: string): { tags: string[]; error?: AddTagError } {
  const tag = normalizeTag(raw);
  if (!tag || tag.includes(',')) return { tags, error: 'invalid' };
  if (Array.from(tag).length > MAX_TAG_LENGTH) return { tags, error: 'tooLong' };
  if (tags.includes(tag)) return { tags };
  if (tags.length >= MAX_TAGS) return { tags, error: 'tooMany' };
  return { tags: [...tags, tag] };
}

export function removeTag(tags: string[], tag: string): string[] {
  return tags.filter((t) => t !== tag);
}

export function formatTag(tag: string): string {
  return tag.charAt(0).toUpperCase() + tag.slice(1);
}
