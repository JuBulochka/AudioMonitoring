import api from './client';
import { DeviceCommandItem, DeviceCommandDetail } from '@/types';

export interface CommandCatalogEntry {
  key: string;
  label: string;
  description: string;
  category: string;
  timeout: number;
  requires_confirm: boolean;
  icon: string;
}

export interface SendCommandResult {
  id: string;
  command_key: string;
  label: string;
  status: string;
  created_at: string;
}

export async function getCommandCatalog(): Promise<CommandCatalogEntry[]> {
  const { data } = await api.get<CommandCatalogEntry[]>('/commands/catalog/');
  return data;
}

export async function sendCommand(deviceId: string, commandKey: string): Promise<SendCommandResult> {
  const { data } = await api.post<SendCommandResult>('/commands/', {
    device_id: deviceId,
    command_key: commandKey,
  });
  return data;
}

export async function getCommandResult(commandId: string): Promise<DeviceCommandDetail> {
  const { data } = await api.get<DeviceCommandDetail>(`/commands/${commandId}/`);
  return data;
}

/** Returns flat array (not paginated) — last 100 commands for the device. */
export async function getDeviceCommands(deviceId: string): Promise<DeviceCommandItem[]> {
  const { data } = await api.get<DeviceCommandItem[]>('/commands/', {
    params: { device: deviceId },
  });
  return data;
}
