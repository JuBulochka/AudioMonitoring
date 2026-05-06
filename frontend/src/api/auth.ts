import axios from 'axios';
import { UserProfile, AuthTokens } from '@/types';
import api from './client';

export async function login(username: string, password: string): Promise<AuthTokens> {
  const { data } = await axios.post<AuthTokens>('/api/v1/auth/token/', { username, password });
  return data;
}

export async function getProfile(): Promise<UserProfile> {
  const { data } = await api.get<UserProfile>('/devices/me/');
  return data;
}
