import { describe, expect, it } from 'vitest';

import { buildOutfitListParams } from '@/lib/hooks/use-outfits';
import { addTag, formatTag, normalizeTag, removeTag } from '@/lib/lookbook/tags';
import {
  buildLookbookQuery,
  hasActiveLookbookFilters,
  parseLookbookParams,
} from '@/lib/lookbook/url-state';
import { MAX_TAG_LENGTH, MAX_TAGS } from '@/lib/lookbook/vocab';

describe('lookbook tags', () => {
  it('normalizes whitespace and casing like the backend', () => {
    expect(normalizeTag('  Date   Night ')).toBe('date night');
    expect(normalizeTag('   ')).toBeNull();
  });

  it('adds normalized tags and ignores duplicates', () => {
    expect(addTag([], ' Büro ')).toEqual({ tags: ['büro'] });
    expect(addTag(['büro'], 'BÜRO')).toEqual({ tags: ['büro'] });
  });

  it('rejects empty, comma, too long and too many tags', () => {
    expect(addTag([], '  ').error).toBe('invalid');
    expect(addTag([], 'work,gym').error).toBe('invalid');
    expect(addTag([], 'x'.repeat(MAX_TAG_LENGTH + 1)).error).toBe('tooLong');
    expect(addTag([], 'x'.repeat(MAX_TAG_LENGTH)).error).toBeUndefined();

    const full = Array.from({ length: MAX_TAGS }, (_, i) => `tag${i}`);
    expect(addTag(full, 'one more')).toEqual({ tags: full, error: 'tooMany' });
  });

  it('removes and formats tags', () => {
    expect(removeTag(['work', 'gym'], 'work')).toEqual(['gym']);
    expect(formatTag('date night')).toBe('Date night');
  });
});

describe('buildOutfitListParams', () => {
  it('joins list filters and omits empty ones', () => {
    expect(
      buildOutfitListParams(
        { is_lookbook: true, tags: ['work', 'date night'], seasons: [], weather_tags: ['cold'] },
        2,
        24
      )
    ).toEqual({
      page: '2',
      page_size: '24',
      is_lookbook: 'true',
      tags: 'work,date night',
      weather_tags: 'cold',
    });
  });

  it('keeps explicit false booleans', () => {
    expect(buildOutfitListParams({ is_lookbook: false }, 1, 20).is_lookbook).toBe('false');
  });
});

describe('lookbook url state', () => {
  it('parses valid values and drops unknown seasons and weather', () => {
    const state = parseLookbookParams(
      new URLSearchParams('tag=Work&season=winter&weather=foggy&q=%20office%20')
    );
    expect(state).toEqual({ tag: 'work', season: 'winter', weather: null, q: 'office' });
  });

  it('round-trips through the query string', () => {
    const state = { tag: 'date night', season: 'summer', weather: 'warm', q: 'linen' } as const;
    expect(parseLookbookParams(new URLSearchParams(buildLookbookQuery(state)))).toEqual(state);
  });

  it('builds an empty query and reports no active filters for the default state', () => {
    const empty = { tag: null, season: null, weather: null, q: '' };
    expect(buildLookbookQuery(empty)).toBe('');
    expect(hasActiveLookbookFilters(empty)).toBe(false);
    expect(hasActiveLookbookFilters({ ...empty, weather: 'rain' })).toBe(true);
  });
});
