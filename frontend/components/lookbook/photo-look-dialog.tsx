'use client';

import { useCallback, useEffect, useState } from 'react';
import Image from 'next/image';
import { useDropzone, type FileRejection } from 'react-dropzone';
import { ImageOff, Loader2, Upload, X } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { toast } from 'sonner';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { TagInput } from '@/components/lookbook/tag-input';
import { ToggleChips } from '@/components/lookbook/toggle-chips';
import { OccasionChips } from '@/components/shared/occasion-chips';
import { getErrorMessage } from '@/lib/api';
import { useCreatePhotoLook, useLookbookTags } from '@/lib/hooks/use-outfits';
import { useLookbookSeasons, useWeatherTags } from '@/lib/hooks/use-translated-constants';
import { PHOTO_ACCEPT, PHOTO_MAX_BYTES, PHOTO_MAX_MB } from '@/lib/lookbook/photo-look';

const NAME_MAX_LENGTH = 100;

interface PhotoLookDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function PhotoLookDialog({ open, onOpenChange }: PhotoLookDialogProps) {
  const t = useTranslations('lookbook.photo');
  const ta = useTranslations('lookbook.attributes');
  const tc = useTranslations('common');
  const seasonOptions = useLookbookSeasons();
  const weatherOptions = useWeatherTags();
  const { data: tagCounts } = useLookbookTags();
  const createPhotoLook = useCreatePhotoLook();

  const [photo, setPhoto] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewFailed, setPreviewFailed] = useState(false);
  const [name, setName] = useState('');
  const [occasion, setOccasion] = useState<string | null>(null);
  const [tags, setTags] = useState<string[]>([]);
  const [seasons, setSeasons] = useState<string[]>([]);
  const [weatherTags, setWeatherTags] = useState<string[]>([]);
  const [confirmDiscard, setConfirmDiscard] = useState(false);

  useEffect(() => {
    if (!photo) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(photo);
    setPreviewUrl(url);
    setPreviewFailed(false);
    return () => URL.revokeObjectURL(url);
  }, [photo]);

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) setPhoto(accepted[0]);
  }, []);

  const onDropRejected = useCallback(
    (rejections: FileRejection[]) => {
      const tooLarge = rejections.some((r) => r.errors.some((e) => e.code === 'file-too-large'));
      toast.error(tooLarge ? t('tooLarge', { maxMb: PHOTO_MAX_MB }) : t('invalidType'));
    },
    [t]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected,
    accept: PHOTO_ACCEPT,
    maxFiles: 1,
    multiple: false,
    maxSize: PHOTO_MAX_BYTES,
  });

  const pending = createPhotoLook.isPending;
  const canSave = Boolean(photo && name.trim() && occasion) && !pending;
  const hasInput = Boolean(photo || name.trim() || tags.length > 0);

  const close = () => {
    setPhoto(null);
    setName('');
    setOccasion(null);
    setTags([]);
    setSeasons([]);
    setWeatherTags([]);
    setConfirmDiscard(false);
    onOpenChange(false);
  };

  const handleOpenChange = (next: boolean) => {
    if (next) {
      onOpenChange(true);
    } else if (!pending) {
      if (hasInput) setConfirmDiscard(true);
      else close();
    }
  };

  const handleSave = async () => {
    if (!photo || !occasion || !name.trim()) return;
    try {
      await createPhotoLook.mutateAsync({
        photo,
        name,
        occasion,
        tags,
        seasons,
        weather_tags: weatherTags,
      });
      toast.success(t('saved'));
      close();
    } catch (error) {
      toast.error(getErrorMessage(error, t('saveError')));
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t('title')}</DialogTitle>
            <DialogDescription>{t('description')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-5">
            {!photo ? (
              <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                  isDragActive
                    ? 'border-primary bg-primary/5'
                    : 'border-muted-foreground/25 hover:border-primary/50'
                }`}
              >
                <input {...getInputProps()} />
                <Upload className="mx-auto h-12 w-12 text-muted-foreground" />
                <p className="mt-2 text-sm text-muted-foreground">
                  {isDragActive ? t('dropzoneActive') : t('dropzone')}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {t('formatHint', { maxMb: PHOTO_MAX_MB })}
                </p>
              </div>
            ) : (
              <div className="relative h-64 w-full overflow-hidden rounded-lg bg-muted">
                {previewUrl && !previewFailed ? (
                  <Image
                    src={previewUrl}
                    alt={t('previewAlt')}
                    fill
                    unoptimized
                    className="object-contain"
                    onError={() => setPreviewFailed(true)}
                  />
                ) : (
                  // HEIC photos cannot be previewed outside Safari but upload fine.
                  <div className="flex h-full flex-col items-center justify-center gap-2 px-4 text-center text-sm text-muted-foreground">
                    <ImageOff className="h-8 w-8" />
                    {t('previewUnavailable', { name: photo.name })}
                  </div>
                )}
                <Button
                  type="button"
                  variant="destructive"
                  size="icon"
                  className="absolute top-2 right-2 h-8 w-8"
                  onClick={() => setPhoto(null)}
                  disabled={pending}
                  aria-label={t('removePhoto')}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="photo-look-name">{t('name')}</Label>
              <Input
                id="photo-look-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('namePlaceholder')}
                maxLength={NAME_MAX_LENGTH}
                disabled={pending}
              />
            </div>

            <div className="space-y-2">
              <Label>{t('occasion')}</Label>
              <OccasionChips selected={occasion} onSelect={setOccasion} />
            </div>

            <div className="space-y-2">
              <Label htmlFor="photo-look-tags">{ta('tags')}</Label>
              <TagInput
                id="photo-look-tags"
                value={tags}
                onChange={setTags}
                suggestions={tagCounts?.tags.map((c) => c.tag)}
                disabled={pending}
              />
            </div>

            <div className="space-y-2">
              <Label>{ta('seasons')}</Label>
              <ToggleChips
                options={seasonOptions}
                selected={seasons}
                onChange={setSeasons}
                disabled={pending}
              />
            </div>

            <div className="space-y-2">
              <Label>{ta('weather')}</Label>
              <ToggleChips
                options={weatherOptions}
                selected={weatherTags}
                onChange={setWeatherTags}
                disabled={pending}
              />
            </div>

            <div className="space-y-2">
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={pending}>
                  {tc('cancel')}
                </Button>
                <Button onClick={handleSave} disabled={!canSave}>
                  {pending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {t('save')}
                </Button>
              </div>
              {!canSave && !pending && (
                <p className="text-right text-xs text-muted-foreground">{t('missingFields')}</p>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={confirmDiscard} onOpenChange={setConfirmDiscard}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('discardTitle')}</AlertDialogTitle>
            <AlertDialogDescription>{t('discardDescription')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('keepEditing')}</AlertDialogCancel>
            <AlertDialogAction onClick={close}>{t('discard')}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
