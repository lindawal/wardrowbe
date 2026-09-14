import { describe, expect, it } from 'vitest';

import { buildMosaicLayout, type MosaicLayout } from '@/lib/outfits/mosaic-layout';

function makeItem(id: string, type: string) {
  return { id, type };
}

function tileIds(layout: MosaicLayout<{ id: string; type: string }>) {
  return layout.tiles.map((tile) => tile.item.id);
}

describe('buildMosaicLayout', () => {
  it('renders nothing for an outfit without items', () => {
    const layout = buildMosaicLayout([]);
    expect(layout).toEqual({ gridClassName: 'grid-cols-1', tiles: [], overflow: 0 });
  });

  it('lets a single item fill the whole area', () => {
    const layout = buildMosaicLayout([makeItem('a', 'shirt')]);
    expect(layout.gridClassName).toBe('grid-cols-1');
    expect(tileIds(layout)).toEqual(['a']);
  });

  it('puts two items side by side', () => {
    const layout = buildMosaicLayout([makeItem('a', 'shirt'), makeItem('b', 'shoes')]);
    expect(layout.gridClassName).toBe('grid-cols-2');
    expect(tileIds(layout)).toEqual(['a', 'b']);
    expect(layout.tiles.every((tile) => tile.className === '')).toBe(true);
  });

  it('gives the tall tile to trousers among three items and keeps the rest in order', () => {
    const layout = buildMosaicLayout([
      makeItem('shirt', 'shirt'),
      makeItem('shoes', 'shoes'),
      makeItem('pants', 'pants'),
    ]);
    expect(layout.gridClassName).toBe('grid-cols-2 grid-rows-2');
    expect(tileIds(layout)).toEqual(['pants', 'shirt', 'shoes']);
    expect(layout.tiles.map((tile) => tile.className)).toEqual(['row-span-2', '', '']);
  });

  it('keeps the stored order when three items contain no long garment', () => {
    const layout = buildMosaicLayout([
      makeItem('shirt', 'shirt'),
      makeItem('jacket', 'jacket'),
      makeItem('shoes', 'shoes'),
    ]);
    expect(tileIds(layout)).toEqual(['shirt', 'jacket', 'shoes']);
    expect(layout.tiles[0].className).toBe('row-span-2');
  });

  it('prefers a dress over jeans for the tall tile', () => {
    const layout = buildMosaicLayout([
      makeItem('jeans', 'jeans'),
      makeItem('dress', 'dress'),
      makeItem('shoes', 'shoes'),
    ]);
    expect(tileIds(layout)).toEqual(['dress', 'jeans', 'shoes']);
  });

  it('shows four items as a 2x2 grid without a tall tile', () => {
    const layout = buildMosaicLayout([
      makeItem('a', 'shirt'),
      makeItem('b', 'jacket'),
      makeItem('c', 'shoes'),
      makeItem('d', 'hat'),
    ]);
    expect(layout.gridClassName).toBe('grid-cols-2 grid-rows-2');
    expect(tileIds(layout)).toEqual(['a', 'b', 'c', 'd']);
    expect(layout.tiles.every((tile) => tile.className === '')).toBe(true);
    expect(layout.overflow).toBe(0);
  });

  it('shows three items plus an overflow count from five items on, keeping a late long garment visible', () => {
    const layout = buildMosaicLayout([
      makeItem('a', 'shirt'),
      makeItem('b', 'jacket'),
      makeItem('c', 'shoes'),
      makeItem('d', 'hat'),
      makeItem('e', 'jeans'),
      makeItem('f', 'belt'),
    ]);
    expect(layout.gridClassName).toBe('grid-cols-2 grid-rows-2');
    expect(tileIds(layout)).toEqual(['e', 'a', 'b']);
    expect(layout.overflow).toBe(3);
  });
});
