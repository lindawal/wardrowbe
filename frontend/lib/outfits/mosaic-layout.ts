// Long garments are photographed upright, so they get the tall tile. Lower value wins.
const LONG_ITEM_PRIORITY: Record<string, number> = {
  dress: 0,
  overall: 0,
  pants: 1,
  jeans: 1,
};

export interface MosaicTile<T> {
  item: T;
  className: string;
}

export interface MosaicLayout<T> {
  gridClassName: string;
  tiles: MosaicTile<T>[];
  // Items that did not fit; the card renders an extra "+overflow" tile for them.
  overflow: number;
}

function longItemFirst<T extends { type: string }>(items: T[]): T[] {
  let longIdx = -1;
  items.forEach((item, idx) => {
    const priority = LONG_ITEM_PRIORITY[item.type];
    if (priority === undefined) return;
    if (longIdx === -1 || priority < LONG_ITEM_PRIORITY[items[longIdx].type]) {
      longIdx = idx;
    }
  });
  if (longIdx <= 0) return items;
  return [items[longIdx], ...items.slice(0, longIdx), ...items.slice(longIdx + 1)];
}

export function buildMosaicLayout<T extends { type: string }>(items: T[]): MosaicLayout<T> {
  const ordered = longItemFirst(items);
  const plainTiles = (list: T[]) => list.map((item) => ({ item, className: '' }));

  switch (ordered.length) {
    case 0:
    case 1:
      return { gridClassName: 'grid-cols-1', tiles: plainTiles(ordered), overflow: 0 };
    case 2:
      return { gridClassName: 'grid-cols-2', tiles: plainTiles(ordered), overflow: 0 };
    case 3:
      return {
        gridClassName: 'grid-cols-2 grid-rows-2',
        tiles: ordered.map((item, idx) => ({ item, className: idx === 0 ? 'row-span-2' : '' })),
        overflow: 0,
      };
    case 4:
      return { gridClassName: 'grid-cols-2 grid-rows-2', tiles: plainTiles(ordered), overflow: 0 };
    default:
      // The fourth cell holds the "+N" tile.
      return {
        gridClassName: 'grid-cols-2 grid-rows-2',
        tiles: plainTiles(ordered.slice(0, 3)),
        overflow: ordered.length - 3,
      };
  }
}
