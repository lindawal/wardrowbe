'use client';

import Link from 'next/link';
import Image from 'next/image';
import { formatDistanceToNow, parseISO } from 'date-fns';
import {
  BookmarkCheck,
  Bot,
  Camera,
  Layers,
  RefreshCw,
  Shirt,
  Shuffle,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { cn } from '@/lib/utils';
import { useAcceptOutfit, useRejectOutfit, useSkipOutfit, type Outfit } from '@/lib/hooks/use-outfits';
import { formatTag } from '@/lib/lookbook/tags';
import { buildMosaicLayout } from '@/lib/outfits/mosaic-layout';
import { useTranslations } from 'next-intl';
import { useClothingTypes, useItemDisplayName } from '@/lib/hooks/use-translated-constants';

const MAX_VISIBLE_TAGS = 3;

interface OutfitCardProps {
  outfit: Outfit;
  onClick?: () => void;
  selectMode?: boolean;
  selected?: boolean;
  onSelect?: (id: string, checked: boolean) => void;
  // Link target when the card navigates; defaults to the outfit detail page.
  href?: string;
  showTags?: boolean;
}

function getSourceBadge(outfit: Outfit, t: any): {
  label: string;
  icon: React.ReactNode;
  className: string;
} | null {
  if (outfit.is_photo_look) {
    return {
      label: t('photo'),
      icon: <Camera className="h-3 w-3" />,
      className: 'bg-pink-100 text-pink-700 border-pink-200',
    };
  }
  if (outfit.replaces_outfit_id) {
    return {
      label: t('replacement'),
      icon: <RefreshCw className="h-3 w-3" />,
      className: 'bg-orange-100 text-orange-700 border-orange-200',
    };
  }
  if (
    outfit.cloned_from_outfit_id &&
    outfit.source === 'manual' &&
    outfit.scheduled_for
  ) {
    return {
      label: t('worn'),
      icon: <BookmarkCheck className="h-3 w-3" />,
      className: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    };
  }
  if (outfit.source === 'manual') {
    return {
      label: t('studio'),
      icon: <Shirt className="h-3 w-3" />,
      className: 'bg-purple-100 text-purple-700 border-purple-200',
    };
  }
  if (outfit.source === 'pairing') {
    return {
      label: t('pairing'),
      icon: <Layers className="h-3 w-3" />,
      className: 'bg-amber-100 text-amber-700 border-amber-200',
    };
  }
  if (outfit.source === 'external') {
    return {
      label: t('external'),
      icon: <Bot className="h-3 w-3" />,
      className: 'bg-teal-100 text-teal-700 border-teal-200',
    };
  }
  return {
    label: t('ai'),
    icon: <Sparkles className="h-3 w-3" />,
    className: 'bg-blue-100 text-blue-700 border-blue-200',
  };
}

function getCardTitle(outfit: Outfit, t: any): string {
  if (outfit.name) return outfit.name;
  if (outfit.reasoning) return outfit.reasoning;
  if (outfit.highlights && outfit.highlights.length > 0) {
    return outfit.highlights[0];
  }
  const occasion =
    outfit.occasion.charAt(0).toUpperCase() + outfit.occasion.slice(1);
  return t('outfitFallback', { occasion });
}
function getMetaLabel(outfit: Outfit, t: any): string {
  if (!outfit.scheduled_for) return t('lookbookTemplate');
  try {
    return formatDistanceToNow(parseISO(outfit.scheduled_for), {
      addSuffix: true,
    });
  } catch {
    return outfit.scheduled_for;
  }
}

export function OutfitCard({
  outfit,
  onClick,
  selectMode,
  selected,
  onSelect,
  href,
  showTags,
}: OutfitCardProps) {
  const t = useTranslations('outfits.cards');
  const ta = useTranslations('outfits.actions');
  const clothingTypes = useClothingTypes();
  const itemDisplayName = useItemDisplayName();
  const badge = getSourceBadge(outfit, t);
  const mosaic = buildMosaicLayout(outfit.items);
  const tags = showTags ? outfit.tags ?? [] : [];
  // The 400px thumbnail of a portrait photo looks soft at card size, so prefer the medium image.
  const photoSrc = outfit.is_photo_look ? outfit.photo_medium_url || outfit.photo_url : null;
  // Still awaiting a decision: offer quick review actions right on the card.
  const isPendingReview =
    outfit.status === 'pending' || outfit.status === 'sent' || outfit.status === 'viewed';
  const acceptOutfit = useAcceptOutfit();
  const rejectOutfit = useRejectOutfit();
  const skipOutfit = useSkipOutfit();

  const handleCheckboxClick = (e: React.MouseEvent) => {
    e.stopPropagation();
  };

  const handleAccept = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await acceptOutfit.mutateAsync(outfit.id);
      toast.success(ta('accepted'));
    } catch {
      toast.error(ta('acceptError'));
    }
  };

  const handleReject = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await rejectOutfit.mutateAsync(outfit.id);
      toast.success(ta('rejected'));
    } catch {
      toast.error(ta('rejectError'));
    }
  };

  const handleSkip = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await skipOutfit.mutateAsync(outfit.id);
      toast.success(ta('skipped'));
    } catch {
      toast.error(ta('skipError'));
    }
  };

  const handleCardClick = selectMode
    ? () => onSelect?.(outfit.id, !selected)
    : onClick;

  const content = (
    <Card
      className={cn(
        'overflow-hidden transition-all hover:shadow-md',
        handleCardClick && 'cursor-pointer',
        selectMode && selected && 'ring-2 ring-primary shadow-md'
      )}
      onClick={handleCardClick}
    >
      <CardContent className="p-0">
        <div className="relative aspect-[5/4] bg-muted">
          {selectMode && (
            <div
              className="absolute top-2 left-2 z-10"
              onClick={handleCheckboxClick}
            >
              <Checkbox
                checked={!!selected}
                onCheckedChange={(checked) => onSelect?.(outfit.id, checked === true)}
                className="bg-background/80 backdrop-blur-sm"
              />
            </div>
          )}
          {photoSrc ? (
            <Image
              src={photoSrc}
              alt={getCardTitle(outfit, t)}
              fill
              className="object-contain"
              sizes="(max-width: 768px) 100vw, 33vw"
              loading="lazy"
            />
          ) : (
            <div className={cn('absolute inset-0 grid gap-0.5 p-2', mosaic.gridClassName)}>
              {mosaic.tiles.map(({ item, className }, idx) => (
                <div
                  key={`${item.id}-${idx}`}
                  className={cn('relative rounded overflow-hidden bg-background', className)}
                >
                  {item.thumbnail_url || item.image_url ? (
                    <Image
                      src={(item.thumbnail_url || item.image_url)!}
                      alt={itemDisplayName(item)}
                      fill
                      className="object-cover"
                      sizes="(max-width: 768px) 50vw, 25vw"
                      loading="lazy"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <span className="text-[10px] text-muted-foreground">
                        {clothingTypes.find((ct) => ct.value === item.type)?.label ?? item.type}
                      </span>
                    </div>
                  )}
                </div>
              ))}
              {mosaic.overflow > 0 && (
                <div className="relative rounded overflow-hidden bg-background flex items-center justify-center">
                  <span className="text-sm font-medium text-muted-foreground">
                    +{mosaic.overflow}
                  </span>
                </div>
              )}
            </div>
          )}
          {badge && (
            <div
              className={cn(
                'absolute top-2 right-2 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium',
                badge.className
              )}
            >
              {badge.icon}
              <span>{badge.label}</span>
            </div>
          )}
        </div>
        <div className="p-3 space-y-1">
          <h3 className="text-sm font-semibold leading-tight truncate">
            {getCardTitle(outfit, t)}
          </h3>
          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {tags.slice(0, MAX_VISIBLE_TAGS).map((tag) => (
                <Badge key={tag} variant="secondary" className="px-1.5 py-0 text-[10px]">
                  {formatTag(tag)}
                </Badge>
              ))}
              {tags.length > MAX_VISIBLE_TAGS && (
                <Badge variant="outline" className="px-1.5 py-0 text-[10px]">
                  +{tags.length - MAX_VISIBLE_TAGS}
                </Badge>
              )}
            </div>
          )}
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <Badge variant="outline" className="capitalize">
              {outfit.occasion}
            </Badge>
            <span>{getMetaLabel(outfit, t)}</span>
          </div>
          {isPendingReview && !selectMode && (
            <div className="flex gap-1.5 pt-1">
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="flex-1 h-7 px-0"
                onClick={handleReject}
                disabled={rejectOutfit.isPending}
                aria-label={ta('reject')}
                title={ta('reject')}
              >
                <ThumbsDown className="h-3.5 w-3.5" />
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="flex-1 h-7 px-0"
                onClick={handleSkip}
                disabled={skipOutfit.isPending}
                aria-label={ta('skip')}
                title={ta('skip')}
              >
                <Shuffle className="h-3.5 w-3.5" />
              </Button>
              <Button
                type="button"
                size="sm"
                className="flex-1 h-7 px-0"
                onClick={handleAccept}
                disabled={acceptOutfit.isPending}
                aria-label={ta('accept')}
                title={ta('accept')}
              >
                <ThumbsUp className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );

  if (selectMode || onClick) return content;
  return (
    <Link href={href ?? `/dashboard/outfits/${outfit.id}`} className="block">
      {content}
    </Link>
  );
}
