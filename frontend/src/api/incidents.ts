import api from './client';
import { Incident, IncidentComment, PaginatedResponse } from '@/types';

export interface IncidentsParams {
  status?: string;
  severity?: string;
  incident_type?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

export async function getIncidents(params?: IncidentsParams): Promise<PaginatedResponse<Incident>> {
  const { data } = await api.get<PaginatedResponse<Incident>>('/incidents/', { params });
  return data;
}

export async function getIncident(id: string): Promise<Incident> {
  const { data } = await api.get<Incident>(`/incidents/${id}/`);
  return data;
}

export async function updateIncidentStatus(
  id: string,
  status: string,
  comment?: string,
  resolution_notes?: string
): Promise<{ success: boolean; new_status: string }> {
  const { data } = await api.patch<{ success: boolean; new_status: string }>(
    `/incidents/${id}/status/`,
    { status, comment: comment || '', resolution_notes: resolution_notes || '' }
  );
  return data;
}

export async function getIncidentComments(id: string): Promise<IncidentComment[]> {
  const { data } = await api.get<IncidentComment[]>(`/incidents/${id}/comments/`);
  return data;
}

export async function addIncidentComment(id: string, text: string): Promise<IncidentComment> {
  const { data } = await api.post<IncidentComment>(`/incidents/${id}/comments/`, { text });
  return data;
}
