'use client';

import { useCallback, useMemo } from 'react';
import { useTranslations } from 'next-intl';
import {
  CLOTHING_TYPES,
  CLOTHING_COLORS,
  OCCASIONS,
} from '@/lib/types';
import { LOOKBOOK_SEASONS, WEATHER_TAGS } from '@/lib/lookbook/vocab';

const STYLE_VALUES = ['bold', 'casual', 'formal', 'minimalist', 'sporty'] as const;
const WEATHER_CONDITION_VALUES = ['clear', 'cloudy', 'rain', 'snow'] as const;

export function useClothingTypes() {
  const t = useTranslations('constants.types');

  return useMemo(() => CLOTHING_TYPES.map((ct) => ({
    ...ct,
    label: t(ct.value),
  })), [t]);
}

// Falls back to the raw stored value for a type that predates the current
// vocabulary (removed or renamed clothing type) and so has no translation.
export function useItemDisplayName() {
  const clothingTypes = useClothingTypes();

  return useCallback(
    (item: { name?: string | null; type: string }) => {
      if (item.name) return item.name;
      const typeInfo = clothingTypes.find((ct) => ct.value === item.type);
      return typeInfo ? typeInfo.label : item.type;
    },
    [clothingTypes]
  );
}

export function useClothingColors() {
  const t = useTranslations('constants.colors');

  return useMemo(() => CLOTHING_COLORS.map((cc) => ({
    ...cc,
    name: t(cc.value),
  })), [t]);
}

export function useOccasions() {
  const t = useTranslations('constants.occasions');

  return useMemo(() => OCCASIONS.map((o) => ({
    ...o,
    label: t(o.value),
  })), [t]);
}

export function useStyles() {
  const t = useTranslations('constants.styles');

  return useMemo(() => STYLE_VALUES.map((value) => ({
    value,
    label: t(value),
  })), [t]);
}

export function useWeatherConditions() {
  const t = useTranslations('constants.weatherConditions');

  return useMemo(() => WEATHER_CONDITION_VALUES.map((value) => ({
    value,
    label: t(value),
  })), [t]);
}

export function useLookbookSeasons() {
  const t = useTranslations('constants.seasons');

  return useMemo(() => LOOKBOOK_SEASONS.map((value) => ({
    value,
    label: t(value),
  })), [t]);
}

export function useWeatherTags() {
  const t = useTranslations('constants.weatherTags');

  return useMemo(() => WEATHER_TAGS.map((value) => ({
    value,
    label: t(value),
  })), [t]);
}

// Simple value -> translated label lookups for item-tagging vocabularies that
// come from the backend's dynamic TagOptions (see backend VALID_FORMALITY /
// VALID_MATERIALS / VALID_PATTERNS / VALID_FIT / VALID_STYLES / VALID_SEASONS)
// rather than a hardcoded frontend array. t.has() falls back to the raw stored
// value so an item tagged before a vocabulary change still displays instead of
// disappearing.
export function useFormalityLabel() {
  const t = useTranslations('constants.formality');
  return useCallback((value: string) => (t.has(value) ? t(value) : value), [t]);
}

export function useMaterialLabel() {
  const t = useTranslations('constants.materials');
  return useCallback((value: string) => (t.has(value) ? t(value) : value), [t]);
}

export function usePatternLabel() {
  const t = useTranslations('constants.patterns');
  return useCallback((value: string) => (t.has(value) ? t(value) : value), [t]);
}

export function useFitLabel() {
  const t = useTranslations('constants.fits');
  return useCallback((value: string) => (t.has(value) ? t(value) : value), [t]);
}

export function useItemStyleLabel() {
  const t = useTranslations('constants.itemStyles');
  return useCallback((value: string) => (t.has(value) ? t(value) : value), [t]);
}

export function useSeasonLabel() {
  const t = useTranslations('constants.seasons');
  return useCallback((value: string) => (t.has(value) ? t(value) : value), [t]);
}
