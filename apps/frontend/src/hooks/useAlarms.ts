// created by ARES team [2026-04-17]
import { useState, useEffect, useCallback } from 'react';
import { getAlarms, readAlarm, readAllAlarms, deleteAlarm, type AlarmItem } from '../services/alarm.service';
import { useFeedbackModal } from '../contexts/FeedbackModalContext';

interface UseAlarmsParams {
  navigate: (path: string) => void;
}

interface UseAlarmsReturn {
  alarmItems: AlarmItem[];
  notificationCount: number;
  alarmError: string | null;
  clearAlarmError: () => void;
  handleNotificationClick: () => void;
  handleReadAllAlarms: () => Promise<void>;
  handleReadAlarm: (alarmId: string) => Promise<void>;
  handleDeleteAlarm: (alarmId: string) => Promise<void>;
}

export function useAlarms({ navigate }: UseAlarmsParams): UseAlarmsReturn {
  const [alarmItems, setAlarmItems] = useState<AlarmItem[]>([]);
  const [notificationCount, setNotificationCount] = useState(0);
  const [alarmError, setAlarmError] = useState<string | null>(null);
  const { openModalWithPost } = useFeedbackModal();

  const clearAlarmError = useCallback(() => setAlarmError(null), []);

  const fetchAlarms = useCallback(async () => {
    try {
      const res = await getAlarms();
      setAlarmItems(res.data.items);
      setNotificationCount(res.data.items.filter(item => item.isRead === 'N').length);
    } catch {
      // 알림 조회 실패 시 무시
    }
  }, []);

  useEffect(() => {
    fetchAlarms();

    const intervalId = setInterval(fetchAlarms, 30000);

    const handleVisibilityChange = (): void => {
      if (document.visibilityState === 'visible') {
        fetchAlarms();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      clearInterval(intervalId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [fetchAlarms]);

  const handleReadAllAlarms = useCallback(async () => {
    setAlarmError(null);
    try {
      await readAllAlarms();
      await fetchAlarms();
    } catch {
      setAlarmError('읽음 처리에 실패했습니다.');
    }
  }, [fetchAlarms]);

  const handleDeleteAlarm = useCallback(async (alarmId: string) => {
    setAlarmError(null);
    try {
      await deleteAlarm(alarmId);
      await fetchAlarms();
    } catch {
      setAlarmError('알림 삭제에 실패했습니다.');
    }
  }, [fetchAlarms]);

  const handleReadAlarm = useCallback(async (alarmId: string) => {
    setAlarmError(null);
    const target = alarmItems.find(item => item.id === alarmId);
    try {
      await readAlarm(alarmId);
      await fetchAlarms();
      // postId 가 있으면 피드백 모달, documentId 가 있으면 문서함, 둘 다 없으면 무동작
      if (target?.postId) {
        await openModalWithPost(target.postId);
      } else if (target?.documentId) {
        navigate('/documents');
      }
    } catch {
      setAlarmError('알림 읽음 처리에 실패했습니다.');
      throw new Error('READ_ALARM_FAILED');
    }
  }, [alarmItems, fetchAlarms, navigate, openModalWithPost]);

  const handleNotificationClick = useCallback((): void => {
    fetchAlarms();
  }, [fetchAlarms]);

  return {
    alarmItems,
    notificationCount,
    alarmError,
    clearAlarmError,
    handleNotificationClick,
    handleReadAllAlarms,
    handleReadAlarm,
    handleDeleteAlarm,
  };
}
