import { describe, expect, it } from 'vitest';

import { buildPhotoLookFormData } from '@/lib/lookbook/photo-look';

describe('buildPhotoLookFormData', () => {
  it('sends list values as repeated fields and trims the name', () => {
    const photo = new File(['x'], 'look.jpg', { type: 'image/jpeg' });
    const data = buildPhotoLookFormData({
      photo,
      name: '  Sunday brunch ',
      occasion: 'casual',
      tags: ['work', 'date night'],
      seasons: ['summer'],
      weather_tags: [],
    });

    expect(data.get('name')).toBe('Sunday brunch');
    expect(data.get('occasion')).toBe('casual');
    expect(data.getAll('tags')).toEqual(['work', 'date night']);
    expect(data.getAll('seasons')).toEqual(['summer']);
    expect(data.has('weather_tags')).toBe(false);
    expect((data.get('image') as File).name).toBe('look.jpg');
  });
});
