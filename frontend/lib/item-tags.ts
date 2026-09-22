import type { Item, ItemTags, ItemTagsUpdate, ItemUpdate } from '@/lib/types';

/** The tags the item editor lets the user change. */
export interface EditableTags {
  formality: string | null;
  pattern: string | null;
  material: string | null;
  fit: string | null;
  colors: string[];
  style: string[];
  season: string[];
}

const SINGLE_TAGS = ['formality', 'pattern', 'material', 'fit'] as const;
const LIST_TAGS = ['colors', 'style', 'season'] as const;

// Tags the backend also stores as a column (ItemService.update mirrors these).
const COLUMN_TAGS = ['colors', 'pattern', 'material', 'style', 'season', 'formality', 'primary_color'] as const;

/**
 * The item's tags as suggestion scoring sees them. Scoring reads the columns;
 * the tags JSON can lag behind them on items re-analysed before the backend kept
 * the two in step, so the columns win. fit exists only in the JSON.
 */
export function editableTagsFromItem(item: Item): EditableTags {
  const json: Partial<ItemTags> = item.tags ?? {};
  const pick = <T,>(column: T | undefined, fallback: T): T => (column !== undefined ? column : fallback);
  return {
    formality: pick(item.formality, json.formality ?? null) ?? null,
    pattern: pick(item.pattern, json.pattern ?? null) ?? null,
    material: pick(item.material, json.material ?? null) ?? null,
    fit: json.fit ?? null,
    colors: pick(item.colors, json.colors ?? []) ?? [],
    style: pick(item.style, json.style ?? []) ?? [],
    season: pick(item.season, json.season ?? []) ?? [],
  };
}

function sameList(a: string[], b: string[]): boolean {
  return a.length === b.length && [...a].sort().join('\u0000') === [...b].sort().join('\u0000');
}

/**
 * Only the tags that differ. Sending unchanged tags would rewrite their columns
 * from whatever the editor was showing, and an empty result lets the caller
 * leave tags out of the request entirely.
 */
export function changedTags(before: EditableTags, after: EditableTags): ItemTagsUpdate | undefined {
  const changes: ItemTagsUpdate = {};
  for (const key of SINGLE_TAGS) {
    if (before[key] !== after[key]) changes[key] = after[key];
  }
  for (const key of LIST_TAGS) {
    if (!sameList(before[key], after[key])) changes[key] = after[key];
  }
  return Object.keys(changes).length ? changes : undefined;
}

/**
 * Apply an update the way the backend will, for the optimistic cache write:
 * tags are merged into the existing ones and mirrored into their columns.
 * A plain spread would replace item.tags with the partial update.
 */
export function applyItemUpdate(item: Item, data: ItemUpdate): Item {
  const { tags, ...rest } = data;
  const next = { ...item, ...rest } as Item;
  if (tags) {
    next.tags = { ...item.tags, ...tags } as ItemTags;
    const columns = next as unknown as Record<string, unknown>;
    for (const key of COLUMN_TAGS) {
      if (key in tags) columns[key] = (tags as Record<string, unknown>)[key];
    }
  }
  return next;
}

/**
 * The offered options plus any current value outside them, so a value set
 * before the options matched the tagger (e.g. a manually picked "khaki") is
 * still shown and selected instead of silently disappearing.
 */
export function withCurrent(options: string[], current: string | string[] | null): string[] {
  const values = current === null ? [] : Array.isArray(current) ? current : [current];
  const extra = values.filter((v) => v && !options.includes(v));
  return extra.length ? [...options, ...extra] : options;
}
