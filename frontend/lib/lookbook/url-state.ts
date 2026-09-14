import { normalizeTag } from '@/lib/lookbook/tags';
import {
  LOOKBOOK_SEASONS,
  WEATHER_TAGS,
  type LookbookSeason,
  type WeatherTag,
} from '@/lib/lookbook/vocab';

export interface LookbookUrlState {
  tag: string | null;
  season: LookbookSeason | null;
  weather: WeatherTag | null;
  q: string;
}

function oneOf<T extends string>(values: readonly T[], raw: string | null): T | null {
  return raw !== null && (values as readonly string[]).includes(raw) ? (raw as T) : null;
}

export function parseLookbookParams(params: URLSearchParams): LookbookUrlState {
  return {
    tag: normalizeTag(params.get('tag') ?? ''),
    season: oneOf(LOOKBOOK_SEASONS, params.get('season')),
    weather: oneOf(WEATHER_TAGS, params.get('weather')),
    q: params.get('q')?.trim() ?? '',
  };
}

export function buildLookbookQuery(state: LookbookUrlState): string {
  const params = new URLSearchParams();
  if (state.tag) params.set('tag', state.tag);
  if (state.season) params.set('season', state.season);
  if (state.weather) params.set('weather', state.weather);
  if (state.q) params.set('q', state.q);
  return params.toString();
}

export function hasActiveLookbookFilters(state: LookbookUrlState): boolean {
  return Boolean(state.tag || state.season || state.weather || state.q);
}
