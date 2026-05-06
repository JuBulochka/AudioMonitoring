import api from './client';
import { AudioPacket, PaginatedResponse } from '@/types';

export interface PacketsParams {
  device?: string;
  severity?: string;
  has_anomaly?: boolean;
  from_date?: string;
  to_date?: string;
  dominant_class?: string;
  page?: number;
  page_size?: number;
}

export async function getPackets(params?: PacketsParams): Promise<PaginatedResponse<AudioPacket>> {
  const { data } = await api.get<PaginatedResponse<AudioPacket>>('/packets/', { params });
  return data;
}

export async function getPacket(id: string): Promise<AudioPacket> {
  const { data } = await api.get<AudioPacket>(`/packets/${id}/`);
  return data;
}

export async function updatePacketStatus(
  id: string,
  operator_status: string,
  notes?: string
): Promise<AudioPacket> {
  const { data } = await api.patch<AudioPacket>(`/packets/${id}/`, { operator_status, notes });
  return data;
}
