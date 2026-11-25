// created by ARES team [2026-03-25]
import { useState, useRef, useEffect, useCallback } from 'react';
import { toggleDocumentReference } from '../../services/document.service';

const DEBOUNCE_MS = 2000;

/**
 * AI 지식 활용 토글 훅
 * - 서버 isEnabled 값을 초기 상태로 사용
 * - debounce(2초) 후 변경된 항목만 배치 API 호출
 * - 창 종료, 라우트 이동, visibilitychange 시 즉시 flush
 */
export function useKnowledgeToggle(onFlushed?: () => void) {
  // 로컬 토글 상태 (docId → boolean)
  const [toggleState, setToggleState] = useState<Record<string, boolean>>({});
  // 서버에 반영되지 않은 변경 목록 (contentId → 최종 isEnabled)
  const pendingChanges = useRef<Map<string, boolean>>(new Map());
  // 사용자가 직접 토글한 docId (탭 이동 시 서버 값으로 덮어쓰기 방지)
  const modifiedDocIds = useRef<Set<string>>(new Set());
  // debounce 타이머
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // flush 진행 중 여부 (중복 방지)
  const flushingRef = useRef(false);
  // API base URL (sendBeacon 용)
  const baseUrl = useRef(
    (import.meta.env.VITE_API_URL as string | undefined) || '/api'
  );

  /** pending 변경사항을 서버에 전송 */
  const flush = useCallback(async () => {
    if (pendingChanges.current.size === 0 || flushingRef.current) return;
    flushingRef.current = true;

    const entries = Array.from(pendingChanges.current.entries());
    pendingChanges.current.clear();

    try {
      await Promise.allSettled(
        entries.map(([contentId]) => toggleDocumentReference(contentId))
      );
      onFlushed?.();
    } catch {
      // apiClient 인터셉터에서 로깅됨
    } finally {
      flushingRef.current = false;
    }
  }, [onFlushed]);

  /** sendBeacon으로 즉시 전송 (페이지 종료 시) */
  const flushWithBeacon = useCallback(() => {
    if (pendingChanges.current.size === 0) return;

    const entries = Array.from(pendingChanges.current.entries());
    pendingChanges.current.clear();

    for (const [contentId] of entries) {
      navigator.sendBeacon(
        `${baseUrl.current}/documents/versions/${contentId}/reference`,
        new Blob([], { type: 'application/json' })
      );
    }
  }, []);

  // 창 종료 / visibility 변경 방어
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      flushWithBeacon();
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        if (timerRef.current) clearTimeout(timerRef.current);
        flushWithBeacon();
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      // 컴포넌트 언마운트 (라우트 이동) 시 flush
      if (timerRef.current) clearTimeout(timerRef.current);
      flush();
    };
  }, [flush, flushWithBeacon]);

  /** 서버에서 받은 문서 목록으로 초기 상태 동기화 */
  const initFromDocuments = useCallback(
    (docs: { id: string; latestContent?: { isEnabled?: boolean; status?: string } }[]) => {
      setToggleState((prev) => {
        const next = { ...prev };
        for (const doc of docs) {
          // 사용자가 직접 토글한 문서는 서버 값으로 덮어쓰지 않음
          if (modifiedDocIds.current.has(doc.id)) continue;

          if (doc.id in prev) {
            if (doc.latestContent?.isEnabled !== undefined) {
              next[doc.id] = doc.latestContent.isEnabled;
            }
          } else {
            // 최초 로드: 서버 값 우선, 없으면 completed면 ON
            next[doc.id] = doc.latestContent?.isEnabled ?? (doc.latestContent?.status === 'completed');
          }
        }
        return next;
      });
    },
    []
  );

  /** 토글 클릭 핸들러 */
  const toggle = useCallback(
    (docId: string, contentId: string) => {
      setToggleState((prev) => {
        const newValue = !prev[docId];
        const next = { ...prev, [docId]: newValue };

        // 사용자가 직접 변경한 문서로 기록
        modifiedDocIds.current.add(docId);
        // pending에 추가
        pendingChanges.current.set(contentId, newValue);

        // debounce 리셋
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => {
          flush();
        }, DEBOUNCE_MS);

        return next;
      });
    },
    [flush]
  );

  /** 질문 전 호출 — pending을 즉시 flush하고 완료 대기 */
  const flushBeforeChat = useCallback(async () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    await flush();
  }, [flush]);

  return {
    toggleState,
    toggle,
    initFromDocuments,
    flushBeforeChat,
  };
}
