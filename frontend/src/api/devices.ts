import api from './client';
import { Device, DeviceHeartbeat, PaginatedResponse } from '@/types';

export interface DevicesParams {
  search?: string;
  status?: string;
  is_online?: boolean;
  page?: number;
  page_size?: number;
}

export async function getDevices(params?: DevicesParams): Promise<PaginatedResponse<Device>> {
  const { data } = await api.get<PaginatedResponse<Device>>('/devices/', { params });
  return data;
}

export async function getDevice(id: string): Promise<Device> {
  const { data } = await api.get<Device>(`/devices/${id}/`);
  return data;
}

export async function getDeviceHeartbeats(id: string): Promise<DeviceHeartbeat[]> {
  const { data } = await api.get<DeviceHeartbeat[]>(`/devices/${id}/heartbeats/`);
  return data;
}

export async function updateDeviceStatus(
  id: string,
  status: string,
  reason?: string
): Promise<Device> {
  const { data } = await api.post<Device>(`/devices/${id}/status/`, { status, reason });
  return data;
}
