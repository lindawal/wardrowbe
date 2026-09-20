'use client';

import { useState } from 'react';
import { Loader2, Pencil } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { TagInput } from '@/components/lookbook/tag-input';
import { ToggleChips, type ToggleChipOption } from '@/components/lookbook/toggle-chips';
import { getErrorMessage } from '@/lib/api';
import { useLookbookTags, type Outfit } from '@/lib/hooks/use-outfits';
import { usePatchOutfit } from '@/lib/hooks/use-studio';
import { useLookbookSeasons, useWeatherTags } from '@/lib/hooks/use-translated-constants';
import { formatTag } from '@/lib/lookbook/tags';

function labelFor(options: ToggleChipOption[], value: string): string {
  return options.find((o) => o.value === value)?.label ?? value;
}

function AttributeRow({ label, values, empty }: { label: string; values: string[]; empty: string }) {
  return (
    <div className="grid grid-cols-[6rem_1fr] items-start gap-2">
      <dt className="pt-0.5 text-muted-foreground">{label}</dt>
      <dd className="flex flex-wrap gap-1.5">
        {values.length > 0 ? (
          values.map((value) => (
            <Badge key={value} variant="secondary">
              {value}
            </Badge>
          ))
        ) : (
          <span className="text-muted-foreground">{empty}</span>
        )}
      </dd>
    </div>
  );
}

export function LookbookAttributesCard({ outfit }: { outfit: Outfit }) {
  const t = useTranslations('lookbook.attributes');
  const tc = useTranslations('common');
  const seasonOptions = useLookbookSeasons();
  const weatherOptions = useWeatherTags();
  const { data: tagCounts } = useLookbookTags();
  const patchMutation = usePatchOutfit();

  const [editing, setEditing] = useState(false);
  const [tags, setTags] = useState<string[]>([]);
  const [seasons, setSeasons] = useState<string[]>([]);
  const [weatherTags, setWeatherTags] = useState<string[]>([]);
  const pending = patchMutation.isPending;

  const startEditing = () => {
    setTags(outfit.tags);
    setSeasons(outfit.seasons);
    setWeatherTags(outfit.weather_tags);
    setEditing(true);
  };

  const handleSave = async () => {
    try {
      // One request for all three fields keeps edits well under the PATCH rate limit.
      await patchMutation.mutateAsync({
        id: outfit.id,
        payload: { tags, seasons, weather_tags: weatherTags },
      });
      toast.success(t('saved'));
      setEditing(false);
    } catch (error) {
      toast.error(getErrorMessage(error, t('saveError')));
    }
  };

  return (
    <Card>
      <CardContent className="space-y-4 p-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            {t('title')}
          </h2>
          {!editing && (
            <Button variant="ghost" size="sm" onClick={startEditing}>
              <Pencil className="mr-1 h-4 w-4" />
              {tc('edit')}
            </Button>
          )}
        </div>

        {editing ? (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="lookbook-tags">{t('tags')}</Label>
              <TagInput
                id="lookbook-tags"
                value={tags}
                onChange={setTags}
                suggestions={tagCounts?.tags.map((c) => c.tag)}
                disabled={pending}
              />
            </div>
            <div className="space-y-2">
              <Label>{t('seasons')}</Label>
              <ToggleChips
                options={seasonOptions}
                selected={seasons}
                onChange={setSeasons}
                disabled={pending}
              />
            </div>
            <div className="space-y-2">
              <Label>{t('weather')}</Label>
              <ToggleChips
                options={weatherOptions}
                selected={weatherTags}
                onChange={setWeatherTags}
                disabled={pending}
              />
            </div>
            {/* Photo looks have no items to suggest season and weather from. */}
            {!outfit.is_photo_look && (
              <p className="text-xs text-muted-foreground">{t('suggestedHint')}</p>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setEditing(false)} disabled={pending}>
                {tc('cancel')}
              </Button>
              <Button size="sm" onClick={handleSave} disabled={pending}>
                {pending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {tc('save')}
              </Button>
            </div>
          </div>
        ) : (
          <dl className="space-y-3 text-sm">
            <AttributeRow label={t('tags')} values={outfit.tags.map(formatTag)} empty={t('noTags')} />
            <AttributeRow
              label={t('seasons')}
              values={outfit.seasons.map((s) => labelFor(seasonOptions, s))}
              empty={t('noSeasons')}
            />
            <AttributeRow
              label={t('weather')}
              values={outfit.weather_tags.map((w) => labelFor(weatherOptions, w))}
              empty={t('noWeather')}
            />
          </dl>
        )}
      </CardContent>
    </Card>
  );
}
