// Mirrors backend/app/utils/lookbook.py; change both sides together.
export const LOOKBOOK_SEASONS = ['spring', 'summer', 'fall', 'winter'] as const;
export const WEATHER_TAGS = ['warm', 'mild', 'cold', 'rain', 'snow'] as const;

export type LookbookSeason = (typeof LOOKBOOK_SEASONS)[number];
export type WeatherTag = (typeof WEATHER_TAGS)[number];

export const MAX_TAGS = 10;
export const MAX_TAG_LENGTH = 30;
