// created by ARES team [2026-04-28]
import { useRef, useState, useEffect } from 'react';

interface UseScrollFadeOptions {
  // mount 시점과 콘텐츠 크기 변화 시 자동 측정 여부
  eager?: boolean;
}

export function useScrollFade<T extends HTMLElement = HTMLDivElement>(
  threshold = 10,
  options: UseScrollFadeOptions = {}
) {
  const { eager = false } = options;
  const ref = useRef<T>(null);
  const [showTopFade, setShowTopFade] = useState(false);
  const [showBottomFade, setShowBottomFade] = useState(false);

  const handleScroll = () => {
    const el = ref.current;
    if (!el) return;
    const { scrollTop, scrollHeight, clientHeight } = el;
    setShowTopFade(scrollTop > threshold);
    setShowBottomFade(scrollTop + clientHeight < scrollHeight - threshold);
  };

  useEffect(() => {
    if (!eager) return;
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const { scrollTop, scrollHeight, clientHeight } = el;
      setShowTopFade(scrollTop > threshold);
      setShowBottomFade(scrollTop + clientHeight < scrollHeight - threshold);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    Array.from(el.children).forEach(child => observer.observe(child));
    return () => observer.disconnect();
  }, [eager, threshold]);

  return { ref, showTopFade, showBottomFade, handleScroll };
}
