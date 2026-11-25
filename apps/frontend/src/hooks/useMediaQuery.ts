import { useState, useEffect } from 'react';

/**
 * CSS 미디어 쿼리 매칭 훅
 * @param query - 미디어 쿼리 문자열 (예: '(max-width: 768px)')
 * @returns 현재 뷰포트가 쿼리에 매칭되는지 여부
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState<boolean>(() => {
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    const mediaQuery = window.matchMedia(query);
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches);

    mediaQuery.addEventListener('change', handler);
    setMatches(mediaQuery.matches);

    return () => mediaQuery.removeEventListener('change', handler);
  }, [query]);

  return matches;
}

export const BREAKPOINTS = {
  mobile: '(max-width: 768px)',
  tablet: '(max-width: 1024px)',
} as const;
