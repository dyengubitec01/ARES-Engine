// created by ARES team [2026-04-28]
import { useState } from 'react';

export function usePersistedToggle(storageKey: string, defaultValue: boolean | (() => boolean)) {
  const [isOpen, setIsOpen] = useState<boolean>(() => {
    const stored = localStorage.getItem(storageKey);
    if (stored !== null) return stored === 'true';
    return typeof defaultValue === 'function' ? defaultValue() : defaultValue;
  });

  const toggle = (): void => {
    setIsOpen((prev) => {
      const next = !prev;
      localStorage.setItem(storageKey, String(next));
      return next;
    });
  };

  return { isOpen, toggle };
}