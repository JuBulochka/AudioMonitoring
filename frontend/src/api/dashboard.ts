import api from './client';
import { DashboardSummary } from '@/types';

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const { data } = await api.get<DashboardSummary>('/dashboard/summary/');
  return data;
}
