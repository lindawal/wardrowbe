import { describe, expect, it } from 'vitest';

import { buildMosaicLayout, chooseGrid, type MosaicLayout } from '@/lib/outfits/mosaic-layout';

type TestItem = { id: string; type: string };

function makeItem(id: string, type: string): TestItem {
  return { id, type };
}

function tileIds(layout: MosaicLayout<TestItem>) {
  return layout.tiles.map((tile) => tile.item.id);
}

function heroId(layout: MosaicLayout<TestItem>) {
  return layout.hero?.kind === 'item' ? layout.hero.item.id : layout.hero?.kind ?? null;
}

describe('buildMosaicLayout', () => {
  it('renders nothing for an outfit without items', () => {
    const layout = buildMosaicLayout<TestItem>([]);
    expect(layout.hero).toBeNull();
    expect(layout.tiles).toEqual([]);
  });

  it('lets a single plain item fill the whole area', () => {
    const layout = buildMosaicLayout([makeItem('a', 'shirt')]);
    expect(layout.hero).toBeNull();
    expect(tileIds(layout)).toEqual(['a']);
    expect(layout).toMatchObject({ columns: 1, rows: 1 });
  });

  it('puts two plain items side by side', () => {
    const layout = buildMosaicLayout([makeItem('a', 'shirt'), makeItem('b', 'shoes')]);
    expect(layout).toMatchObject({ columns: 2, rows: 1 });
    expect(tileIds(layout)).toEqual(['a', 'b']);
  });

  it('makes trousers the hero and keeps the rest in order as small tiles', () => {
    const layout = buildMosaicLayout([
      makeItem('shirt', 'shirt'),
      makeItem('shoes', 'shoes'),
      makeItem('pants', 'pants'),
    ]);
    expect(heroId(layout)).toBe('pants');
    expect(tileIds(layout)).toEqual(['shirt', 'shoes']);
    expect(layout).toMatchObject({ columns: 1, rows: 2 });
  });

  it('prefers a dress over jeans for the hero and still shows the jeans', () => {
    const layout = buildMosaicLayout([
      makeItem('jeans', 'jeans'),
      makeItem('dress', 'dress'),
      makeItem('shoes', 'shoes'),
    ]);
    expect(heroId(layout)).toBe('dress');
    expect(tileIds(layout)).toEqual(['jeans', 'shoes']);
  });

  it('treats overalls and skirts as hero garments', () => {
    expect(heroId(buildMosaicLayout([makeItem('a', 'shoes'), makeItem('o', 'overall')]))).toBe('o');
    expect(heroId(buildMosaicLayout([makeItem('a', 'shoes'), makeItem('s', 'skirt')]))).toBe('s');
  });

  it('lets a lone long garment fill the card as hero', () => {
    const layout = buildMosaicLayout([makeItem('d', 'dress')]);
    expect(heroId(layout)).toBe('d');
    expect(layout.tiles).toEqual([]);
  });

  it('shows every item, never an overflow count', () => {
    const items = ['shirt', 'jacket', 'shoes', 'hat', 'jeans', 'belt', 'scarf', 'socks'].map(
      (type, idx) => makeItem(String(idx), type)
    );
    const layout = buildMosaicLayout(items);
    expect(heroId(layout)).toBe('4');
    expect(tileIds(layout)).toEqual(['0', '1', '2', '3', '5', '6', '7']);
    expect(layout.columns * layout.rows).toBeGreaterThanOrEqual(7);
  });

  it('puts a photo in front and keeps all items, the long garment included, as tiles', () => {
    const layout = buildMosaicLayout(
      [makeItem('dress', 'dress'), makeItem('shoes', 'shoes'), makeItem('bag', 'belt')],
      { heroPhoto: '/worn.jpg' }
    );
    expect(layout.hero).toEqual({ kind: 'photo', src: '/worn.jpg' });
    expect(tileIds(layout)).toEqual(['dress', 'shoes', 'bag']);
  });

  it('shows a photo look without items as a lone hero', () => {
    const layout = buildMosaicLayout<TestItem>([], { heroPhoto: '/look.jpg' });
    expect(layout.hero).toEqual({ kind: 'photo', src: '/look.jpg' });
    expect(layout.tiles).toEqual([]);
  });

  it('stretches the last tile over empty cells so the grid has no gaps', () => {
    const layout = buildMosaicLayout([
      makeItem('pants', 'pants'),
      ...['a', 'b', 'c', 'd', 'e'].map((id) => makeItem(id, 'shirt')),
    ]);
    expect(layout).toMatchObject({ columns: 2, rows: 3 });
    expect(layout.tiles.map((tile) => tile.colSpan)).toEqual([1, 1, 1, 1, 2]);
  });
});

describe('chooseGrid', () => {
  it('picks the most square tiles for the narrow side column', () => {
    expect(chooseGrid(1, 2, 4)).toEqual({ columns: 1, rows: 1 });
    expect(chooseGrid(2, 2, 4)).toEqual({ columns: 1, rows: 2 });
    expect(chooseGrid(8, 2, 4)).toEqual({ columns: 2, rows: 4 });
  });

  it('uses a 2x2 grid for four items on the full area', () => {
    expect(chooseGrid(4, 5, 4)).toEqual({ columns: 2, rows: 2 });
  });
});
