'use client';

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import {
  List as ListIcon,
  CalendarDays,
  Camera,
  Plus,
  Search,
  CheckSquare,
  Shirt,
  Sparkles,
  X,
} from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { OutfitCard } from '@/components/outfits/outfit-card';
import { OutfitCalendar } from '@/components/outfit-calendar';
import { BulkActionToolbar, BulkSelection } from '@/components/bulk-action-toolbar';
import { GeneratePairingsDialog } from '@/components/generate-pairings-dialog';
import { PhotoLookDialog } from '@/components/lookbook/photo-look-dialog';
import { ItemPicker } from '@/components/shared/item-picker';
import {
  useBulkDeleteOutfits,
  useCalendarOutfits,
  useLookbookTags,
  useOutfits,
  type BulkOutfitOperationParams,
  type Outfit,
  type OutfitFilters,
} from '@/lib/hooks/use-outfits';
import { useItem } from '@/lib/hooks/use-items';
import {
  useItemDisplayName,
  useLookbookSeasons,
  useWeatherTags,
} from '@/lib/hooks/use-translated-constants';
import { formatTag } from '@/lib/lookbook/tags';
import { parseLookbookParams } from '@/lib/lookbook/url-state';
import type { LookbookSeason, WeatherTag } from '@/lib/lookbook/vocab';
import { cn } from '@/lib/utils';

const ALL = 'all';
// URL params that only make sense on the Lookbook chip; dropped when switching chips.
const LOOKBOOK_ONLY_PARAMS = ['tag', 'season', 'weather'] as const;

interface MonthRef {
  year: number;
  month: number;
}

function currentMonthRef(): MonthRef {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

function formatDateKey(y: number, m: number, d: number): string {
  return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

function formatMonthParam(ref: MonthRef): string {
  return `${ref.year}-${String(ref.month).padStart(2, '0')}`;
}

function parseMonthParam(val: string | null): MonthRef | null {
  if (!val) return null;
  const [y, m] = val.split('-').map(Number);
  if (!y || !m || m < 1 || m > 12) return null;
  return { year: y, month: m };
}

function shiftMonth(ref: MonthRef, delta: number): MonthRef {
  const d = new Date(ref.year, ref.month - 1 + delta, 1);
  return { year: d.getFullYear(), month: d.getMonth() + 1 };
}

function outfitDateSet(outfits: Outfit[]): Set<string> {
  const set = new Set<string>();
  for (const o of outfits) {
    if (o.scheduled_for) set.add(o.scheduled_for);
  }
  return set;
}

function outfitsByDate(outfits: Outfit[]): Map<string, Outfit[]> {
  const map = new Map<string, Outfit[]>();
  for (const o of outfits) {
    if (!o.scheduled_for) continue;
    const arr = map.get(o.scheduled_for) ?? [];
    arr.push(o);
    map.set(o.scheduled_for, arr);
  }
  return map;
}

type FilterChip =
  | 'all'
  | 'pending'
  | 'my-looks'
  | 'worn'
  | 'pairings'
  | 'replacements'
  | 'ai';

type ViewMode = 'list' | 'calendar';

const CHIP_ORDER: FilterChip[] = [
  'all',
  'pending',
  'my-looks',
  'worn',
  'pairings',
  'replacements',
  'ai',
];

const CHIP_KEYS: Record<FilterChip, string> = {
  all: 'filters.all',
  pending: 'filters.pending',
  'my-looks': 'filters.lookbook',
  worn: 'filters.worn',
  pairings: 'filters.pairings',
  replacements: 'filters.replacements',
  ai: 'filters.ai',
};

const EMPTY_KEYS: Record<FilterChip, string> = {
  all: 'empty.all',
  pending: 'empty.pending',
  'my-looks': 'empty.myLooks',
  worn: 'empty.worn',
  pairings: 'empty.pairings',
  replacements: 'empty.replacements',
  ai: 'empty.ai',
};

interface ExtraFilters {
  search: string;
  // Clothing item id: only outfits containing it. Applies to every chip.
  item: string | null;
  // Lookbook-only sub-filters; ignored on the other chips.
  tag: string | null;
  season: LookbookSeason | null;
  weather: WeatherTag | null;
}

function chipToFilters(chip: FilterChip, extra: ExtraFilters): OutfitFilters {
  const filters: OutfitFilters = {};
  if (extra.search) filters.search = extra.search;
  if (extra.item) filters.item_id = extra.item;
  switch (chip) {
    case 'pending':
      // Still awaiting a decision, whether or not it has been sent/viewed yet.
      filters.status = 'pending,sent,viewed';
      return filters;
    case 'my-looks':
      filters.is_lookbook = true;
      if (extra.tag) filters.tags = [extra.tag];
      if (extra.season) filters.seasons = [extra.season];
      if (extra.weather) filters.weather_tags = [extra.weather];
      return filters;
    case 'worn':
      filters.is_lookbook = false;
      filters.status = 'accepted';
      return filters;
    case 'pairings':
      filters.has_source_item = true;
      return filters;
    case 'replacements':
      filters.is_replacement = true;
      return filters;
    case 'ai':
      filters.source = 'scheduled,on_demand';
      return filters;
    case 'all':
    default:
      return filters;
  }
}

function OutfitsPageContent() {
  const t = useTranslations('outfits');
  const tc = useTranslations('common');
  const tl = useTranslations('lookbook');
  const router = useRouter();
  const searchParams = useSearchParams();
  const seasonOptions = useLookbookSeasons();
  const weatherOptions = useWeatherTags();
  const itemDisplayName = useItemDisplayName();
  // Reuses the lookbook URL parser for tag/season/weather/q/item validation.
  const urlExtra = useMemo(() => parseLookbookParams(searchParams), [searchParams]);
  const rawFilter = (searchParams.get('filter') as FilterChip) || 'all';
  const urlView: ViewMode = searchParams.get('view') === 'calendar' ? 'calendar' : 'list';
  const urlFilter: FilterChip =
    urlView === 'calendar' && rawFilter === 'my-looks' ? 'all' : rawFilter;
  const chip: FilterChip = urlFilter;
  const view: ViewMode = urlView;
  const urlMonth = parseMonthParam(searchParams.get('month'));

  const [search, setSearch] = useState(urlExtra.q);
  const [debouncedSearch, setDebouncedSearch] = useState(urlExtra.q);
  const [itemPickerOpen, setItemPickerOpen] = useState(false);
  const [pairingsDialogOpen, setPairingsDialogOpen] = useState(false);
  const [photoDialogOpen, setPhotoDialogOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [defaultChecked, setDefaultChecked] = useState(false);
  const [monthRef, setMonthRef] = useState<MonthRef>(urlMonth ?? currentMonthRef());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [selectMode, setSelectMode] = useState(false);
  const [selection, setSelection] = useState<BulkSelection>({
    mode: 'none',
    selectedIds: new Set(),
    excludedIds: new Set(),
  });

  useEffect(() => {
    if (urlMonth && (urlMonth.year !== monthRef.year || urlMonth.month !== monthRef.month)) {
      setMonthRef(urlMonth);
    }
  }, [urlMonth, monthRef.year, monthRef.month]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const itemFilter = urlExtra.item;
  const isLookbook = chip === 'my-looks';
  const filters = useMemo(
    () =>
      chipToFilters(chip, {
        search: debouncedSearch,
        item: itemFilter,
        tag: urlExtra.tag,
        season: urlExtra.season,
        weather: urlExtra.weather,
      }),
    [chip, debouncedSearch, itemFilter, urlExtra.tag, urlExtra.season, urlExtra.weather],
  );
  const { data: filterItem } = useItem(itemFilter ?? '');
  const filterItemName = filterItem ? itemDisplayName(filterItem) : tl('filters.itemFallback');
  const { data: tagData } = useLookbookTags();
  const tagChips = tagData?.tags ?? [];
  // A tag from a shared link may no longer exist; still show it so it can be cleared.
  const orphanTag =
    urlExtra.tag && tagData && !tagChips.some((c) => c.tag === urlExtra.tag)
      ? urlExtra.tag
      : null;
  const lookbookFiltersActive = Boolean(urlExtra.tag || urlExtra.season || urlExtra.weather);
  const anyFilterActive = Boolean(itemFilter || debouncedSearch || (isLookbook && lookbookFiltersActive));

  const listQuery = useOutfits(filters, page, 24);
  const bulkDeleteOutfits = useBulkDeleteOutfits();

  // Clear selection when filters change (but not page - allow cross-page selection)
  useEffect(() => {
    setSelection({ mode: 'none', selectedIds: new Set(), excludedIds: new Set() });
  }, [filters]);

  useEffect(() => {
    if (view === 'calendar') {
      setSelectMode(false);
    }
  }, [view]);

  const calendarQuery = useCalendarOutfits(
    monthRef.year,
    monthRef.month,
    view === 'calendar' ? filters : {},
  );

  const lookbookProbe = useOutfits({ is_lookbook: true }, 1, 1);

  useEffect(() => {
    if (defaultChecked) return;
    if (urlFilter !== 'all' || urlView === 'calendar' || itemFilter) {
      setDefaultChecked(true);
      return;
    }
    if (lookbookProbe.data) {
      if (lookbookProbe.data.total === 0) {
        const params = new URLSearchParams(searchParams.toString());
        params.set('filter', 'my-looks');
        router.replace(`/dashboard/outfits?${params.toString()}`);
      }
      setDefaultChecked(true);
    }
  }, [defaultChecked, lookbookProbe.data, urlFilter, urlView, itemFilter, searchParams, router]);

  const replaceParams = useCallback(
    (mutate: (params: URLSearchParams) => void) => {
      const params = new URLSearchParams(searchParams.toString());
      mutate(params);
      router.replace(`/dashboard/outfits${params.toString() ? `?${params}` : ''}`, {
        scroll: false,
      });
    },
    [router, searchParams],
  );

  const setParam = useCallback(
    (key: string, value: string | null) => {
      setPage(1);
      setSelectedDate(null);
      replaceParams((params) => {
        if (value) params.set(key, value);
        else params.delete(key);
      });
    },
    [replaceParams],
  );

  const clearFilters = () => {
    setSearch('');
    setDebouncedSearch('');
    setPage(1);
    replaceParams((params) => {
      for (const key of [...LOOKBOOK_ONLY_PARAMS, 'q', 'item']) params.delete(key);
    });
  };

  const updateQuery = useCallback(
    (next: {
      filter?: FilterChip;
      view?: ViewMode;
      month?: MonthRef | null;
    }) => {
      const params = new URLSearchParams(searchParams.toString());

      if ('filter' in next) {
        if (!next.filter || next.filter === 'all') {
          params.delete('filter');
        } else {
          params.set('filter', next.filter);
        }
      }

      if ('view' in next) {
        if (!next.view || next.view === 'list') {
          params.delete('view');
        } else {
          params.set('view', next.view);
        }
      }

      if ('month' in next) {
        if (!next.month) {
          params.delete('month');
        } else {
          params.set('month', formatMonthParam(next.month));
        }
      }

      router.replace(
        `/dashboard/outfits${params.toString() ? `?${params}` : ''}`,
      );
    },
    [router, searchParams],
  );

  const handleChipClick = (next: FilterChip) => {
    const params = new URLSearchParams(searchParams.toString());
    if (next !== 'my-looks') {
      for (const key of LOOKBOOK_ONLY_PARAMS) params.delete(key);
    }
    if (next === 'all') {
      params.delete('filter');
    } else {
      params.set('filter', next);
    }
    setPage(1);
    setSelectedDate(null);
    router.replace(
      `/dashboard/outfits${params.toString() ? `?${params}` : ''}`,
    );
  };

  const handleViewChange = (next: ViewMode) => {
    setSelectedDate(null);
    const params = new URLSearchParams(searchParams.toString());
    if (next === 'calendar') {
      params.set('view', 'calendar');
      if (params.get('filter') === 'my-looks') {
        params.delete('filter');
      }
    } else {
      params.delete('view');
    }
    router.replace(
      `/dashboard/outfits${params.toString() ? `?${params}` : ''}`,
    );
  };

  const handleMonthChange = (year: number, month: number) => {
    const nextRef = { year, month };
    setMonthRef(nextRef);
    setSelectedDate(null);
    updateQuery({ month: nextRef });
  };

  const handleShiftMonth = (delta: number) => {
    const nextRef = shiftMonth(monthRef, delta);
    setMonthRef(nextRef);
    setSelectedDate(null);
    updateQuery({ month: nextRef });
  };

  const calendarOutfits: Outfit[] = calendarQuery.data?.outfits ?? [];
  const dateSet = useMemo(() => outfitDateSet(calendarOutfits), [calendarOutfits]);
  const dateMap = useMemo(() => outfitsByDate(calendarOutfits), [calendarOutfits]);
  const selectedDayOutfits: Outfit[] = selectedDate
    ? dateMap.get(selectedDate) ?? []
    : [];

  const outfits = listQuery.data?.outfits ?? [];
  const total = listQuery.data?.total ?? 0;
  const hasMore = listQuery.data?.has_more ?? false;
  const listLoading = listQuery.isLoading;
  const listError = listQuery.isError;
  const calendarLoading = calendarQuery.isLoading;
  const calendarError = calendarQuery.isError;

  const handleToggleSelectMode = () => {
    setSelectMode((prev) => {
      if (prev) {
        setSelection({ mode: 'none', selectedIds: new Set(), excludedIds: new Set() });
      }
      return !prev;
    });
  };

  const handleSelect = (id: string, checked: boolean) => {
    setSelection((prev) => {
      if (prev.mode === 'all') {
        const next = new Set(prev.excludedIds);
        if (checked) {
          next.delete(id);
        } else {
          next.add(id);
        }
        return { ...prev, excludedIds: next };
      }
      const next = new Set(prev.selectedIds);
      if (checked) {
        next.add(id);
      } else {
        next.delete(id);
      }
      return { mode: next.size > 0 ? 'some' : 'none', selectedIds: next, excludedIds: new Set() };
    });
  };

  const handleSelectPage = () => {
    setSelection((prev) => {
      const pageFullySelected =
        (prev.mode === 'all' && prev.excludedIds.size === 0) ||
        (prev.mode === 'some' && prev.selectedIds.size === outfits.length && outfits.length > 0);
      if (pageFullySelected) {
        return { mode: 'none', selectedIds: new Set(), excludedIds: new Set() };
      }
      return { mode: 'some', selectedIds: new Set(outfits.map((o) => o.id)), excludedIds: new Set() };
    });
  };

  const handleSelectAllMatching = () => {
    setSelection({ mode: 'all', selectedIds: new Set(), excludedIds: new Set() });
  };

  const handleClearSelection = () => {
    setSelection({ mode: 'none', selectedIds: new Set(), excludedIds: new Set() });
  };

  const getBulkParams = (): BulkOutfitOperationParams => {
    if (selection.mode === 'all') {
      return {
        select_all: true,
        excluded_ids: Array.from(selection.excludedIds),
        filters,
      };
    }
    return { outfit_ids: Array.from(selection.selectedIds) };
  };

  const handleBulkDelete = async () => {
    const params = getBulkParams();
    try {
      const result = await bulkDeleteOutfits.mutateAsync(params);
      toast.success(t('bulkActions.deleteSuccess', { count: result.deleted }));
      if (result.failed > 0) {
        toast.error(t('bulkActions.deletePartialFailed', { count: result.failed }));
      }
      handleClearSelection();
    } catch {
      toast.error(t('bulkActions.deleteError'));
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('title')}</h1>
          <p className="text-muted-foreground">{t('subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          <div
            className="inline-flex rounded-full border-2 border-muted overflow-hidden"
            role="group"
            aria-label={t('viewToggle')}
          >
            <button
              type="button"
              onClick={() => handleViewChange('list')}
              aria-pressed={view === 'list'}
              className={cn(
                'inline-flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium transition-colors',
                view === 'list'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-background text-muted-foreground hover:text-foreground',
              )}
            >
              <ListIcon className="h-3.5 w-3.5" />
              {t('viewList')}
            </button>
            <button
              type="button"
              onClick={() => handleViewChange('calendar')}
              aria-pressed={view === 'calendar'}
              className={cn(
                'inline-flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium transition-colors border-l-2 border-muted',
                view === 'calendar'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-background text-muted-foreground hover:text-foreground',
              )}
            >
              <CalendarDays className="h-3.5 w-3.5" />
              {t('viewCalendar')}
            </button>
          </div>
          {view === 'list' && (
            <Button
              variant={selectMode ? 'secondary' : 'outline'}
              onClick={handleToggleSelectMode}
            >
              <CheckSquare className="h-4 w-4 mr-2" />
              {selectMode ? tc('cancel') : t('bulkActions.select')}
            </Button>
          )}
          {isLookbook && view === 'list' && (
            <Button variant="outline" onClick={() => setPhotoDialogOpen(true)}>
              <Camera className="h-4 w-4 mr-2" />
              {tl('photo.upload')}
            </Button>
          )}
          <Button asChild>
            <Link href="/dashboard/outfits/new">
              <Plus className="h-4 w-4 mr-2" />
              {t('newOutfit')}
            </Link>
          </Button>
        </div>
      </div>

      {view === 'list' && (
        <div className="flex flex-wrap gap-2">
          {CHIP_ORDER.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => handleChipClick(c)}
              aria-pressed={chip === c}
              className={cn(
                'inline-flex items-center rounded-full border-2 px-4 py-1.5 text-sm font-medium transition-all',
                chip === c
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-muted bg-background hover:border-muted-foreground/50',
              )}
            >
              {t(CHIP_KEYS[c])}
            </button>
          ))}
        </div>
      )}

      {view === 'list' && isLookbook && (tagChips.length > 0 || orphanTag) && (
        <div
          role="group"
          aria-label={tl('subcategories')}
          className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0"
        >
          <button
            type="button"
            aria-pressed={!urlExtra.tag}
            onClick={() => setParam('tag', null)}
            className={subChipClass(!urlExtra.tag)}
          >
            {tl('all')}
            {tagData && <span className="text-xs opacity-70">{tagData.total}</span>}
          </button>
          {tagChips.map(({ tag, count }) => {
            const active = urlExtra.tag === tag;
            return (
              <button
                key={tag}
                type="button"
                aria-pressed={active}
                onClick={() => setParam('tag', active ? null : tag)}
                className={subChipClass(active)}
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
              onClick={() => setParam('tag', null)}
              className={subChipClass(true)}
            >
              {formatTag(orphanTag)}
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        {view === 'list' && (
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder={t('search')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-9"
              maxLength={50}
            />
          </div>
        )}

        {itemFilter ? (
          <button
            type="button"
            onClick={() => setParam('item', null)}
            className={cn(subChipClass(true), 'max-w-full')}
            aria-label={tl('filters.removeItem')}
            title={tl('filters.removeItem')}
          >
            {filterItem?.thumbnail_url || filterItem?.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={filterItem.thumbnail_url || filterItem.image_url}
                alt=""
                className="h-5 w-5 rounded-full object-cover"
              />
            ) : (
              <Shirt className="h-4 w-4" />
            )}
            <span className="truncate">{tl('filters.item', { name: filterItemName })}</span>
            <X className="h-3.5 w-3.5 shrink-0" />
          </button>
        ) : (
          <Button variant="outline" size="sm" className="h-9" onClick={() => setItemPickerOpen(true)}>
            <Shirt className="h-4 w-4 mr-2" />
            {t('itemFilter.pick')}
          </Button>
        )}

        {view === 'list' && isLookbook && (
          <>
            <Select
              value={urlExtra.season ?? ALL}
              onValueChange={(value) => setParam('season', value === ALL ? null : value)}
            >
              <SelectTrigger className="w-[160px] h-9" aria-label={tl('filters.season')}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>{tl('filters.allSeasons')}</SelectItem>
                {seasonOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={urlExtra.weather ?? ALL}
              onValueChange={(value) => setParam('weather', value === ALL ? null : value)}
            >
              <SelectTrigger className="w-[160px] h-9" aria-label={tl('filters.weather')}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>{tl('filters.anyWeather')}</SelectItem>
                {weatherOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        )}

        {view === 'list' && anyFilterActive && (
          <Button variant="ghost" size="sm" onClick={clearFilters}>
            <X className="h-4 w-4 mr-1" />
            {tl('filters.clear')}
          </Button>
        )}

        {view === 'list' && listQuery.data && (
          <Badge variant="outline" className="sm:ml-auto">
            {t('totalCount', { count: listQuery.data.total })}
          </Badge>
        )}
      </div>

      {view === 'list' ? (
        <>
          {listError ? (
            <div className="text-center py-8 text-destructive">{t('loadError')}</div>
          ) : listLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="aspect-[5/4] rounded-lg" />
              ))}
            </div>
          ) : outfits.length === 0 && itemFilter ? (
            <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
              <p className="text-muted-foreground mb-6 max-w-sm">
                {t('itemFilter.empty', { name: filterItemName })}
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {filterItem?.status === 'ready' && (
                  <Button onClick={() => setPairingsDialogOpen(true)}>
                    <Sparkles className="h-4 w-4 mr-2" />
                    {t('itemFilter.generate')}
                  </Button>
                )}
                <Button variant="outline" onClick={clearFilters}>
                  {tl('filters.clear')}
                </Button>
              </div>
            </div>
          ) : outfits.length === 0 && anyFilterActive ? (
            <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
              <p className="text-muted-foreground mb-4">{tl('empty.filtered')}</p>
              <Button variant="outline" onClick={clearFilters}>
                {tl('filters.clear')}
              </Button>
            </div>
          ) : outfits.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
              <p className="text-muted-foreground mb-6 max-w-sm">{t(EMPTY_KEYS[chip])}</p>
              {chip === 'my-looks' && (
                <Button asChild>
                  <Link href="/dashboard/outfits/new">
                    <Plus className="h-4 w-4 mr-2" />
                    {t('newOutfit')}
                  </Link>
                </Button>
              )}
            </div>
          ) : (
            <>
              {itemFilter && filterItem?.status === 'ready' && (
                <div className="flex justify-end -mt-2">
                  <Button variant="ghost" size="sm" onClick={() => setPairingsDialogOpen(true)}>
                    <Sparkles className="h-4 w-4 mr-2 text-primary" />
                    {t('itemFilter.generateMore')}
                  </Button>
                </div>
              )}
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {outfits.map((outfit) => {
                  const isSelected = selection.mode === 'all'
                    ? !selection.excludedIds.has(outfit.id)
                    : selection.selectedIds.has(outfit.id);
                  return (
                    <OutfitCard
                      key={outfit.id}
                      outfit={outfit}
                      href={isLookbook ? `/dashboard/outfits/${outfit.id}?from=lookbook` : undefined}
                      showTags={isLookbook}
                      selectMode={selectMode}
                      selected={isSelected}
                      onSelect={handleSelect}
                    />
                  );
                })}
              </div>
              {hasMore && (
                <div className="flex justify-center pt-4">
                  <Button variant="outline" onClick={() => setPage((p) => p + 1)}>
                    {t('loadMore')}
                  </Button>
                </div>
              )}
            </>
          )}
        </>
      ) : (
        <div className="grid lg:grid-cols-[360px_1fr] gap-6">
          <Card className="h-fit">
            <CardContent className="p-4">
              {calendarLoading ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between mb-4">
                    <Skeleton className="h-8 w-8" />
                    <Skeleton className="h-6 w-32" />
                    <Skeleton className="h-8 w-8" />
                  </div>
                  <div className="grid grid-cols-7 gap-1">
                    {Array.from({ length: 35 }).map((_, i) => (
                      <Skeleton key={i} className="h-10 w-full rounded-md" />
                    ))}
                  </div>
                </div>
              ) : (
                <OutfitCalendar
                  year={monthRef.year}
                  month={monthRef.month}
                  outfits={calendarOutfits}
                  selectedDate={selectedDate ? parseYmd(selectedDate) : null}
                  onSelectDate={(d: Date) =>
                    setSelectedDate(formatDateKey(d.getFullYear(), d.getMonth() + 1, d.getDate()))
                  }
                  onMonthChange={handleMonthChange}
                />
              )}
            </CardContent>
          </Card>

          <div className="space-y-4">
            {calendarError ? (
              <div className="text-center py-8 text-destructive">{t('loadError')}</div>
            ) : calendarLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="aspect-[5/4] rounded-lg" />
                ))}
              </div>
            ) : selectedDate && selectedDayOutfits.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
                <CalendarDays className="h-8 w-8 text-muted-foreground mb-2" />
                <p className="text-sm text-muted-foreground">
                  {t('calendar.noOutfitsOnDay')}
                </p>
              </div>
            ) : (
              <>
                {selectedDate && (
                  <div className="border-b pb-3">
                    <h2 className="text-lg font-semibold">
                      {formatReadableDate(selectedDate)}
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      {t('calendar.outfitCount', { count: selectedDayOutfits.length })}
                    </p>
                  </div>
                )}
                {!selectedDate && (
                  <p className="text-sm text-muted-foreground">
                    {t('calendar.monthlyCount', { count: calendarOutfits.length })}
                  </p>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {(selectedDate ? selectedDayOutfits : calendarOutfits).map((outfit) => (
                    <OutfitCard key={outfit.id} outfit={outfit} />
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      <Dialog open={itemPickerOpen} onOpenChange={setItemPickerOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t('itemFilter.dialogTitle')}</DialogTitle>
            <DialogDescription>{t('itemFilter.dialogDescription')}</DialogDescription>
          </DialogHeader>
          <ItemPicker
            selectedIds={new Set(itemFilter ? [itemFilter] : [])}
            hideNeedsWash={false}
            onToggle={(item) => {
              setItemPickerOpen(false);
              setParam('item', item.id === itemFilter ? null : item.id);
            }}
          />
        </DialogContent>
      </Dialog>

      <GeneratePairingsDialog
        item={filterItem ?? null}
        open={pairingsDialogOpen}
        onOpenChange={setPairingsDialogOpen}
      />

      <PhotoLookDialog open={photoDialogOpen} onOpenChange={setPhotoDialogOpen} />

      {selectMode && (
        <BulkActionToolbar
          selection={selection}
          totalItems={total}
          pageItems={outfits.length}
          onSelectAll={handleSelectPage}
          onSelectAllMatching={handleSelectAllMatching}
          onClear={handleClearSelection}
          onDelete={handleBulkDelete}
          isDeleting={bulkDeleteOutfits.isPending}
          variant="outfits"
          page={page}
          pageSize={24}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}

function subChipClass(active: boolean) {
  return cn(
    'inline-flex shrink-0 items-center gap-1.5 rounded-full border-2 px-3 py-1 text-sm font-medium transition-all',
    active
      ? 'border-primary bg-primary/10 text-primary'
      : 'border-muted bg-background hover:border-muted-foreground/50',
  );
}

function parseYmd(dateKey: string): Date {
  const [y, m, d] = dateKey.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function formatReadableDate(dateKey: string): string {
  return parseYmd(dateKey).toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
}

export default function OutfitsPage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-6">
          <Skeleton className="h-10 w-48" />
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="aspect-[5/4] rounded-lg" />
            ))}
          </div>
        </div>
      }
    >
      <OutfitsPageContent />
    </Suspense>
  );
}
