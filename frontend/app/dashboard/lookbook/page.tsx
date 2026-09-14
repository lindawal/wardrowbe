'use client';

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { BookMarked, Loader2, Plus, Search, X } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { OutfitCard } from '@/components/outfits/outfit-card';
import {
  useLookbookOutfits,
  useLookbookTags,
  type OutfitFilters,
} from '@/lib/hooks/use-outfits';
import { useLookbookSeasons, useWeatherTags } from '@/lib/hooks/use-translated-constants';
import { formatTag } from '@/lib/lookbook/tags';
import {
  buildLookbookQuery,
  hasActiveLookbookFilters,
  parseLookbookParams,
  type LookbookUrlState,
} from '@/lib/lookbook/url-state';
import type { LookbookSeason, WeatherTag } from '@/lib/lookbook/vocab';
import { cn } from '@/lib/utils';

const ALL = 'all';
const SEARCH_DEBOUNCE_MS = 300;
const SEARCH_MAX_LENGTH = 50;

function chipClass(active: boolean) {
  return cn(
    'inline-flex shrink-0 items-center gap-1.5 rounded-full border-2 px-4 py-1.5 text-sm font-medium transition-all',
    active
      ? 'border-primary bg-primary/10 text-primary'
      : 'border-muted bg-background hover:border-muted-foreground/50'
  );
}

function LookbookSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {Array.from({ length: 6 }, (_, i) => (
        <Skeleton key={i} className="aspect-[5/4] rounded-lg" />
      ))}
    </div>
  );
}

function LookbookContent() {
  const t = useTranslations('lookbook');
  const tc = useTranslations('common');
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const seasonOptions = useLookbookSeasons();
  const weatherOptions = useWeatherTags();

  const urlState = useMemo(() => parseLookbookParams(searchParams), [searchParams]);
  const [searchInput, setSearchInput] = useState(urlState.q);

  const updateUrl = useCallback(
    (patch: Partial<LookbookUrlState>) => {
      const query = buildLookbookQuery({ ...urlState, ...patch });
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [pathname, router, urlState]
  );

  useEffect(() => {
    const q = searchInput.trim();
    if (q === urlState.q) return;
    const timer = setTimeout(() => updateUrl({ q }), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [searchInput, updateUrl, urlState.q]);

  const filters = useMemo<OutfitFilters>(
    () => ({
      tags: urlState.tag ? [urlState.tag] : undefined,
      seasons: urlState.season ? [urlState.season] : undefined,
      weather_tags: urlState.weather ? [urlState.weather] : undefined,
      search: urlState.q || undefined,
    }),
    [urlState]
  );

  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useLookbookOutfits(filters);
  const { data: tagData } = useLookbookTags();

  const outfits = data?.pages.flatMap((page) => page.outfits) ?? [];
  const total = data?.pages[0]?.total ?? 0;
  const filtersActive = hasActiveLookbookFilters(urlState);
  const tagChips = tagData?.tags ?? [];
  // A tag from a shared link may no longer exist; still show it so it can be cleared.
  const orphanTag =
    urlState.tag && tagData && !tagChips.some((c) => c.tag === urlState.tag) ? urlState.tag : null;

  const clearFilters = () => {
    setSearchInput('');
    router.replace(pathname, { scroll: false });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <BookMarked className="h-6 w-6 text-primary" />
            {t('title')}
          </h1>
          <p className="text-muted-foreground">{t('subtitle')}</p>
        </div>
        <Button asChild>
          <Link href="/dashboard/outfits/new">
            <Plus className="h-4 w-4 mr-2" />
            {t('newOutfit')}
          </Link>
        </Button>
      </div>

      <div
        role="group"
        aria-label={t('subcategories')}
        className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0"
      >
        <button
          type="button"
          aria-pressed={!urlState.tag}
          onClick={() => updateUrl({ tag: null })}
          className={chipClass(!urlState.tag)}
        >
          {t('all')}
          {tagData && <span className="text-xs opacity-70">{tagData.total}</span>}
        </button>
        {tagChips.map(({ tag, count }) => {
          const active = urlState.tag === tag;
          return (
            <button
              key={tag}
              type="button"
              aria-pressed={active}
              onClick={() => updateUrl({ tag: active ? null : tag })}
              className={chipClass(active)}
            >
              {formatTag(tag)}
              <span className="text-xs opacity-70">{count}</span>
            </button>
          );
        })}
        {orphanTag && (
          <button
            type="button"
            aria-pressed
            onClick={() => updateUrl({ tag: null })}
            className={chipClass(true)}
          >
            {formatTag(orphanTag)}
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full sm:w-64">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder={t('search')}
            className="pl-9"
            maxLength={SEARCH_MAX_LENGTH}
          />
        </div>
        <Select
          value={urlState.season ?? ALL}
          onValueChange={(value) =>
            updateUrl({ season: value === ALL ? null : (value as LookbookSeason) })
          }
        >
          <SelectTrigger className="w-[160px]" aria-label={t('filters.season')}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t('filters.allSeasons')}</SelectItem>
            {seasonOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={urlState.weather ?? ALL}
          onValueChange={(value) =>
            updateUrl({ weather: value === ALL ? null : (value as WeatherTag) })
          }
        >
          <SelectTrigger className="w-[160px]" aria-label={t('filters.weather')}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{t('filters.anyWeather')}</SelectItem>
            {weatherOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {filtersActive && (
          <Button variant="ghost" size="sm" onClick={clearFilters}>
            <X className="h-4 w-4 mr-1" />
            {t('filters.clear')}
          </Button>
        )}
        {data && (
          <Badge variant="secondary" className="sm:ml-auto">
            {t('totalCount', { count: total })}
          </Badge>
        )}
      </div>

      {isError ? (
        <div className="text-center py-8 text-destructive">{t('loadError')}</div>
      ) : isLoading ? (
        <LookbookSkeleton />
      ) : outfits.length === 0 ? (
        filtersActive ? (
          <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
            <p className="text-muted-foreground mb-4">{t('empty.filtered')}</p>
            <Button variant="outline" onClick={clearFilters}>
              {t('filters.clear')}
            </Button>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
            <div className="rounded-full bg-muted p-6 mb-4">
              <BookMarked className="h-12 w-12 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold mb-2">{t('empty.noneTitle')}</h3>
            <p className="text-muted-foreground mb-6 max-w-sm">{t('empty.none')}</p>
            <Button asChild>
              <Link href="/dashboard/outfits/new">
                <Plus className="h-4 w-4 mr-2" />
                {t('newOutfit')}
              </Link>
            </Button>
          </div>
        )
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {outfits.map((outfit) => (
              <OutfitCard
                key={outfit.id}
                outfit={outfit}
                href={`/dashboard/outfits/${outfit.id}?from=lookbook`}
                showTags
              />
            ))}
          </div>
          {hasNextPage && (
            <div className="flex justify-center pt-2">
              <Button
                variant="outline"
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
              >
                {isFetchingNextPage && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                {tc('loadMore')}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function LookbookPage() {
  return (
    <Suspense fallback={<LookbookSkeleton />}>
      <LookbookContent />
    </Suspense>
  );
}
