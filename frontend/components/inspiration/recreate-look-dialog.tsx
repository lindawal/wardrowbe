'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Loader2, Sparkles } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useOccasions } from '@/lib/hooks/use-translated-constants';
import { useRecreateInspirationLook } from '@/lib/hooks/use-inspiration';
import { getErrorMessage } from '@/lib/api';

const DEFAULT_OCCASION = 'casual';

interface RecreateLookDialogProps {
  lookId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Ask for the occasion (and an optional name), create the outfit, open it. */
export function RecreateLookDialog({ lookId, open, onOpenChange }: RecreateLookDialogProps) {
  const t = useTranslations('inspiration.recreate');
  const router = useRouter();
  const occasions = useOccasions();
  const recreate = useRecreateInspirationLook();

  const [occasion, setOccasion] = useState(DEFAULT_OCCASION);
  const [name, setName] = useState('');

  const handleCreate = async () => {
    try {
      const outfit = await recreate.mutateAsync({ lookId, occasion, name });
      toast.success(t('created'));
      onOpenChange(false);
      router.push(`/dashboard/outfits/${outfit.id}`);
    } catch (error) {
      toast.error(getErrorMessage(error, t('error')));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            {t('title')}
          </DialogTitle>
          <DialogDescription>{t('description')}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>{t('occasion')}</Label>
            <Select value={occasion} onValueChange={setOccasion}>
              <SelectTrigger aria-label={t('occasion')}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {occasions.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="recreate-look-name">{t('name')}</Label>
            <Input
              id="recreate-look-name"
              value={name}
              maxLength={100}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('namePlaceholder')}
            />
          </div>
        </div>

        <DialogFooter>
          <Button onClick={handleCreate} disabled={recreate.isPending}>
            {recreate.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {t('create')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
