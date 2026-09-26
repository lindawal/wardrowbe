'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { useDropzone, type FileRejection } from 'react-dropzone';
import { ImageOff, Loader2, Upload, X } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { getErrorMessage } from '@/lib/api';
import { useUploadInspirationLook } from '@/lib/hooks/use-inspiration';
import { PHOTO_ACCEPT, PHOTO_MAX_BYTES, PHOTO_MAX_MB } from '@/lib/lookbook/photo-look';

interface InspirationUploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function InspirationUploadDialog({ open, onOpenChange }: InspirationUploadDialogProps) {
  const t = useTranslations('inspiration.upload');
  const tc = useTranslations('common');
  const router = useRouter();
  const uploadLook = useUploadInspirationLook();

  const [photo, setPhoto] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewFailed, setPreviewFailed] = useState(false);

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

  const pending = uploadLook.isPending;

  const close = () => {
    setPhoto(null);
    onOpenChange(false);
  };

  const handleOpenChange = (next: boolean) => {
    if (next) onOpenChange(true);
    else if (!pending) close();
  };

  const handleUpload = async () => {
    if (!photo) return;
    try {
      const look = await uploadLook.mutateAsync(photo);
      toast.success(t('uploaded'));
      close();
      router.push(`/dashboard/inspiration/${look.id}`);
    } catch (error) {
      toast.error(getErrorMessage(error, t('uploadError')));
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
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

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={pending}>
              {tc('cancel')}
            </Button>
            <Button onClick={handleUpload} disabled={!photo || pending}>
              {pending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t('upload')}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
