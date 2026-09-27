'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Loader2 } from 'lucide-react';
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
import { useClothingColors, useClothingTypes } from '@/lib/hooks/use-translated-constants';
import {
  useAddInspirationLookItem,
  type InspirationLookItemCreate,
} from '@/lib/hooks/use-inspiration';
import { getErrorMessage } from '@/lib/api';

interface AddLookItemDialogProps {
  lookId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Add a piece the AI missed. Only type, main color and a description here -- the
 * remaining tags are edited on the new card like any AI-found piece.
 */
export function AddLookItemDialog({ lookId, open, onOpenChange }: AddLookItemDialogProps) {
  const t = useTranslations('inspiration.addItem');
  const clothingTypes = useClothingTypes();
  const clothingColors = useClothingColors();
  const addItem = useAddInspirationLookItem();

  const [type, setType] = useState('');
  const [primaryColor, setPrimaryColor] = useState('');
  const [description, setDescription] = useState('');

  const reset = () => {
    setType('');
    setPrimaryColor('');
    setDescription('');
  };

  const handleOpenChange = (next: boolean) => {
    if (!next) reset();
    onOpenChange(next);
  };

  const handleSubmit = async () => {
    if (!type) return;
    const item: InspirationLookItemCreate = { type };
    if (primaryColor) item.primary_color = primaryColor;
    if (description.trim()) item.description = description.trim();

    try {
      await addItem.mutateAsync({ lookId, item });
      toast.success(t('added'));
      handleOpenChange(false);
    } catch (error) {
      toast.error(getErrorMessage(error, t('error')));
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t('title')}</DialogTitle>
          <DialogDescription>{t('description')}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>{t('type')}</Label>
            <Select value={type} onValueChange={setType}>
              <SelectTrigger aria-label={t('type')}>
                <SelectValue placeholder={t('typePlaceholder')} />
              </SelectTrigger>
              <SelectContent>
                {clothingTypes.map((ct) => (
                  <SelectItem key={ct.value} value={ct.value}>
                    {ct.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>{t('primaryColor')}</Label>
            <Select value={primaryColor} onValueChange={setPrimaryColor}>
              <SelectTrigger aria-label={t('primaryColor')}>
                <SelectValue placeholder={t('colorPlaceholder')} />
              </SelectTrigger>
              <SelectContent>
                {clothingColors.map((c) => (
                  <SelectItem key={c.value} value={c.value}>
                    <div className="flex items-center gap-2">
                      <div
                        className="h-3 w-3 rounded-full border"
                        style={{ backgroundColor: c.hex }}
                      />
                      {c.name}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="add-look-item-description">{t('descriptionLabel')}</Label>
            <Input
              id="add-look-item-description"
              value={description}
              maxLength={200}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t('descriptionPlaceholder')}
            />
          </div>
        </div>

        <DialogFooter>
          <Button onClick={handleSubmit} disabled={!type || addItem.isPending}>
            {addItem.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {t('submit')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
