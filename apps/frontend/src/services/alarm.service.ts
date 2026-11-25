// created by ARES team [2026-04-14]
import apiClient from '../lib/apiClient';

// ============================================
// 타입 정의
// ============================================

export interface AlarmItem {
  id: string;
  documentId: string | null;
  postId: string | null;
  message: string;
  isRead: 'Y' | 'N';
  createdAt: string;
}

export interface AlarmMeta {
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export interface GetAlarmsResponse {
  success: boolean;
  code: string;
  message: string;
  data: {
    items: AlarmItem[];
    meta: AlarmMeta;
  };
}

export interface ReadAllAlarmsResponse {
  success: boolean;
  code: string;
  message: string;
}

// ============================================
// API 함수
// ============================================

export async function getAlarms(page = 1, limit = 20): Promise<GetAlarmsResponse> {
  const response = await apiClient.get<GetAlarmsResponse>('/alarms', {
    params: { page, limit }
  });
  return response.data;
}

export async function readAllAlarms(): Promise<ReadAllAlarmsResponse> {
  const response = await apiClient.patch<ReadAllAlarmsResponse>('/alarms/read-all');
  return response.data;
}

export async function readAlarm(alarmId: string): Promise<ReadAllAlarmsResponse> {
  const response = await apiClient.patch<ReadAllAlarmsResponse>(`/alarms/${alarmId}/read`);
  return response.data;
}

export async function deleteAlarm(alarmId: string): Promise<ReadAllAlarmsResponse> {
  const response = await apiClient.delete<ReadAllAlarmsResponse>(`/alarms/${alarmId}`);
  return response.data;
}
