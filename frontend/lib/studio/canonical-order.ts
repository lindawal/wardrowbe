export const ITEM_ROLE: Record<string, string> = {
  't-shirt': 'base_top',
  blouse: 'base_top',
  'tank-top': 'base_top',
  sweater: 'base_top',
  pants: 'bottom',
  jeans: 'bottom',
  shorts: 'bottom',
  skirt: 'bottom',
  dress: 'full_body',
  overall: 'full_body',
  blouson: 'mid_layer',
  vest: 'mid_layer',
  jacket: 'outer_layer',
  coat: 'outer_layer',
  shoes: 'footwear',
  sneakers: 'footwear',
  boots: 'footwear',
  sandals: 'footwear',
  socks: 'socks',
  hat: 'accessory',
  scarf: 'accessory',
  belt: 'accessory',
  tights: 'accessory',
};

export const CANONICAL_ROLE_ORDER = [
  'full_body',
  'base_top',
  'mid_layer',
  'outer_layer',
  'bottom',
  'footwear',
  'socks',
  'neckwear',
  'accessory',
] as const;

const ROLE_SORT_INDEX: Record<string, number> = Object.fromEntries(
  CANONICAL_ROLE_ORDER.map((role, idx) => [role, idx])
);

export function canonicalItemOrder<T extends { id: string; type: string }>(
  items: T[]
): T[] {
  const originalPositions = new Map(items.map((item, idx) => [item.id, idx]));
  return [...items].sort((a, b) => {
    const roleA = ITEM_ROLE[a.type] ?? '';
    const roleB = ITEM_ROLE[b.type] ?? '';
    const idxA =
      ROLE_SORT_INDEX[roleA] ?? CANONICAL_ROLE_ORDER.length;
    const idxB =
      ROLE_SORT_INDEX[roleB] ?? CANONICAL_ROLE_ORDER.length;
    if (idxA !== idxB) return idxA - idxB;
    return (
      (originalPositions.get(a.id) ?? 0) -
      (originalPositions.get(b.id) ?? 0)
    );
  });
}
