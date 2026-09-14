'use client';

import { cn } from '@/lib/utils';

export interface ToggleChipOption {
  value: string;
  label: string;
}

interface ToggleChipsProps {
  options: ToggleChipOption[];
  selected: string[];
  onChange: (selected: string[]) => void;
  disabled?: boolean;
}

export function ToggleChips({ options, selected, onChange, disabled }: ToggleChipsProps) {
  const toggle = (value: string) => {
    const next = selected.includes(value)
      ? selected.filter((v) => v !== value)
      : [...selected, value];
    // Keep the options' order so saved values stay canonical.
    onChange(options.map((o) => o.value).filter((v) => next.includes(v)));
  };

  return (
    <div className="flex flex-wrap gap-2">
      {options.map((option) => {
        const active = selected.includes(option.value);
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            disabled={disabled}
            onClick={() => toggle(option.value)}
            className={cn(
              'inline-flex items-center rounded-full border-2 px-3 py-1 text-sm font-medium transition-all disabled:opacity-50',
              active
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-muted bg-background hover:border-muted-foreground/50'
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
