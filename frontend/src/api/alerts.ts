import api from './client';
import { Notification, PaginatedResponse } from '@/types';

export async function getNotifications(params?: {
  is_read?: boolean;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<Notification>> {
  const { data } = await api.get<PaginatedResponse<Notification>>('/alerts/notifications/', { params });
  return data;
}

export async function markRead(id: string): Promise<void> {
  await api.post(`/alerts/notifications/${id}/read/`);
}

export async function markAllRead(): Promise<void> {
  await api.post('/alerts/notifications/read-all/');
}

export async function getUnreadCount(): Promise<number> {
  const { data } = await api.get<{ count: number }>('/alerts/notifications/unread-count/');
  return data.count;
}
