'use client';

import { useCallback } from 'react';
import Image from 'next/image';
import { useDropzone, type FileRejection } from 'react-dropzone';
import { Camera, Loader2, RefreshCw, Trash2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { getErrorMessage } from '@/lib/api';
import type { Outfit } from '@/lib/hooks/use-outfits';
import { useDeleteWornPhoto, useUploadWornPhoto } from '@/lib/hooks/use-outfits';
import { localUrisToLightboxImages } from '@/lib/lightbox-adapters';
import { useLightbox } from '@/lib/lightbox-context';
import { PHOTO_ACCEPT, PHOTO_MAX_BYTES, PHOTO_MAX_MB } from '@/lib/lookbook/photo-look';

interface WornPhotoCardProps {
  outfit: Outfit;
}

export function WornPhotoCard({ outfit }: WornPhotoCardProps) {
  const t = useTranslations('outfits.detail');
  const lightbox = useLightbox();
  const uploadWornPhoto = useUploadWornPhoto();
  const deleteWornPhoto = useDeleteWornPhoto();

  const pending = uploadWornPhoto.isPending || deleteWornPhoto.isPending;

  const upload = useCallback(
    async (photo: File) => {
      try {
        await uploadWornPhoto.mutateAsync({ outfitId: outfit.id, photo });
        toast.success(t('wornPhotoUploaded'));
      } catch (error) {
        toast.error(getErrorMessage(error, t('wornPhotoUploadError')));
      }
    },
    [outfit.id, uploadWornPhoto, t]
  );

  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted[0]) void upload(accepted[0]);
    },
    [upload]
  );

  const onDropRejected = useCallback(
    (rejections: FileRejection[]) => {
      const tooLarge = rejections.some((r) => r.errors.some((e) => e.code === 'file-too-large'));
      toast.error(tooLarge ? t('wornPhotoTooLarge', { maxMb: PHOTO_MAX_MB }) : t('wornPhotoInvalid'));
    },
    [t]
  );

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    onDropRejected,
    accept: PHOTO_ACCEPT,
    maxFiles: 1,
    multiple: false,
    maxSize: PHOTO_MAX_BYTES,
    noClick: !!outfit.worn_photo_url,
    disabled: pending,
  });

  const handleDelete = async () => {
    if (!confirm(t('wornPhotoDeleteConfirm'))) return;
    try {
      await deleteWornPhoto.mutateAsync(outfit.id);
      toast.success(t('wornPhotoRemoved'));
    } catch (error) {
      toast.error(getErrorMessage(error, t('wornPhotoDeleteError')));
    }
  };

  const photoUrl = outfit.worn_photo_url;

  return (
    <Card>
      <CardContent className="p-4">
        <h2 className="text-sm font-semibold text-muted-foreground mb-3 uppercase tracking-wide">
          {t('wornPhoto')}
        </h2>

        {photoUrl ? (
          <div className="space-y-3">
            <button
              type="button"
              aria-label={t('viewWornPhoto')}
              onClick={() =>
                lightbox.open(
                  localUrisToLightboxImages([outfit.worn_photo_medium_url || photoUrl]).images,
                  0
                )
              }
              className="relative block h-64 w-full overflow-hidden rounded-md bg-muted"
            >
              <Image
                src={outfit.worn_photo_medium_url || photoUrl}
                alt={t('wornPhoto')}
                fill
                className="object-cover"
                sizes="(max-width: 896px) 100vw, 896px"
              />
            </button>
            <div className="flex gap-2" {...getRootProps()}>
              <input {...getInputProps()} />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={open}
                disabled={pending}
              >
                {uploadWornPhoto.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4 mr-2" />
                )}
                {t('wornPhotoReplace')}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="text-destructive hover:text-destructive"
                onClick={handleDelete}
                disabled={pending}
              >
                {deleteWornPhoto.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4 mr-2" />
                )}
                {t('wornPhotoRemove')}
              </Button>
            </div>
          </div>
        ) : (
          <div
            {...getRootProps()}
            className={`flex flex-col items-center justify-center gap-2 rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground transition-colors ${
              isDragActive ? 'border-primary bg-muted' : ''
            } ${pending ? 'opacity-60' : 'cursor-pointer hover:bg-muted/50'}`}
          >
            <input {...getInputProps()} />
            {uploadWornPhoto.isPending ? (
              <Loader2 className="h-6 w-6 animate-spin" />
            ) : (
              <Camera className="h-6 w-6" />
            )}
            <span>{t('wornPhotoAdd')}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
