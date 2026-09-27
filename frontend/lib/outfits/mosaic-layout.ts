// Long garments are photographed upright, so they get the big hero tile. Lower value wins.
const LONG_ITEM_PRIORITY: Record<string, number> = {
  dress: 0,
  overall: 0,
  pants: 1,
  jeans: 1,
  skirt: 1,
};

// Card image area is 5:4. A hero takes the right 3/5 (a 3:4 portrait tile), the small
// tiles share the remaining 2/5 on the left. Without a hero the small tiles use all of it.
const AREA_WIDTH = 5;
const AREA_HEIGHT = 4;
const HERO_WIDTH = 3;

export type MosaicHero<T> = { kind: 'photo'; src: string } | { kind: 'item'; item: T };

export interface MosaicTile<T> {
  item: T;
  // Grid columns this tile spans; the last tile stretches over otherwise empty cells.
  colSpan: number;
}

export interface MosaicLayout<T> {
  hero: MosaicHero<T> | null;
  // Grid for the small tiles. Every item is shown, nothing is cut off.
  columns: number;
  rows: number;
  tiles: MosaicTile<T>[];
}

function pickLongItem<T extends { type: string }>(items: T[]): number {
  let longIdx = -1;
  items.forEach((item, idx) => {
    const priority = LONG_ITEM_PRIORITY[item.type];
    if (priority === undefined) return;
    if (longIdx === -1 || priority < LONG_ITEM_PRIORITY[items[longIdx].type]) {
      longIdx = idx;
    }
  });
  return longIdx;
}

// Empty cells are filled by stretching the last tile, which looks off when overdone.
const EMPTY_CELL_PENALTY = 0.15;

// Picks the column count whose tiles come closest to square (penalising empty cells),
// preferring fewer empty cells and then fewer columns on ties.
export function chooseGrid(count: number, width: number, height: number) {
  if (count <= 0) return { columns: 1, rows: 1 };
  let best = { columns: 1, rows: count, score: Infinity, empty: Infinity };
  for (let columns = 1; columns <= count; columns++) {
    const rows = Math.ceil(count / columns);
    const empty = columns * rows - count;
    const score =
      Math.abs(Math.log(width / columns / (height / rows))) + empty * EMPTY_CELL_PENALTY;
    const better =
      score < best.score - 1e-9 ||
      (Math.abs(score - best.score) <= 1e-9 && empty < best.empty);
    if (better) best = { columns, rows, score, empty };
  }
  return { columns: best.columns, rows: best.rows };
}

export function buildMosaicLayout<T extends { type: string }>(
  items: T[],
  options: { heroPhoto?: string | null } = {}
): MosaicLayout<T> {
  let hero: MosaicHero<T> | null = null;
  let rest = items;

  if (options.heroPhoto) {
    // A photo leads; all items stay visible as small tiles next to it.
    hero = { kind: 'photo', src: options.heroPhoto };
  } else {
    const longIdx = pickLongItem(items);
    if (longIdx !== -1) {
      hero = { kind: 'item', item: items[longIdx] };
      rest = [...items.slice(0, longIdx), ...items.slice(longIdx + 1)];
    }
  }

  const width = hero && rest.length > 0 ? AREA_WIDTH - HERO_WIDTH : AREA_WIDTH;
  const { columns, rows } = chooseGrid(rest.length, width, AREA_HEIGHT);
  const emptyCells = columns * rows - rest.length;
  const tiles = rest.map((item, idx) => ({
    item,
    colSpan: idx === rest.length - 1 ? 1 + emptyCells : 1,
  }));

  return { hero, columns, rows, tiles };
}
