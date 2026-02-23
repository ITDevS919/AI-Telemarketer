import axios, { AxiosError } from 'axios';
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios';

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '');
const apiClient = axios.create({
  baseURL: `${API_BASE}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor (optional, but good for debugging)
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // You can log requests here or add auth tokens dynamically
    // console.log('Starting Request', config.method, config.url);
    return config;
  },
  (error: AxiosError) => {
    console.error('Request Error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for global error handling
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response, // Simply return the response if it's successful
  (error: AxiosError) => {
    console.error(
      'API Call Failed:',
      error.response?.status,
      error.response?.data || error.message
    );
    // Optionally, you could have a global error state/notification system here
    return Promise.reject(error); // Important to re-throw the error for component-level handling
  }
);

// --- Dialer Endpoints ---
export const getDialerStatus = () => apiClient.get('/dialer/status');
export const startDialer = () => apiClient.post('/dialer/start');
export const stopDialer = () => apiClient.post('/dialer/stop');
export const getDialerSettings = () => apiClient.get('/dialer/settings');
export const updateDialerSettings = (settings: Record<string, any>) =>
  apiClient.put('/dialer/settings', settings);

// --- Call Management Endpoints ---
export interface AddCallPayload {
  phone_number: string;
  business_type: string;
  caller_id?: string;
}

export const addCall = (payload: AddCallPayload) =>
  apiClient.post('/calls', payload);

export const addBatchCalls = (calls: AddCallPayload[]) =>
  apiClient.post('/calls/batch', calls);

export const getRecentCalls = (limit: number = 50, offset: number = 0) =>
  apiClient.get(`/calls/recent?limit=${limit}&offset=${offset}`);

export const getCallDetails = (callId: string) =>
  apiClient.get(`/calls/${callId}`);

// --- Lead Management Endpoints ---
export const getLeads = (limit: number = 50, offset: number = 0) =>
  apiClient.get(`/leads?limit=${limit}&offset=${offset}`);

export const getLeadDetails = (leadId: string) =>
  apiClient.get(`/leads/${leadId}`);

// --- Regulations Endpoints ---
export interface CheckRegulationsPayload {
  phone_number: string;
  caller_id?: string;
}

export interface RegulationsCheckResponse {
  permitted: boolean;
  reason?: string;
  violation_type?: string;
}

export interface RegulationsStatusResponse {
  initialized: boolean;
  database_path?: string;
  tps_enabled?: boolean;
}

export interface RegulationsHistoryResponse {
  phone_number: string;
  calls: Array<{
    call_sid: string;
    timestamp: number;
    status: string;
    violation_type?: string;
  }>;
}

export const checkRegulations = (payload: CheckRegulationsPayload) =>
  apiClient.post<RegulationsCheckResponse>('/regulations/check', payload);

export const getRegulationsStatus = () =>
  apiClient.get<RegulationsStatusResponse>('/regulations/status');

export const getRegulationsHistory = (phoneNumber: string, days: number = 30) =>
  apiClient.get<RegulationsHistoryResponse>(`/regulations/history/${encodeURIComponent(phoneNumber)}?days=${days}`);

// --- Voice Management Endpoints (ElevenLabs) ---
export interface VoiceInfo {
  name: string;
  source_audio?: string;
  language: string;
  created_at?: string;
  elevenlabs_voice_id?: string;
  description?: string;
}

export const cloneVoice = (file: File, voiceName: string, language: string = 'en') => {
  const formData = new FormData();
  const ext = file.name?.match(/\.(wav|mp3|mpeg)$/i)?.[1]?.toLowerCase()
    || (file.type?.includes('mpeg') || file.type?.includes('mp3') ? 'mp3' : 'wav');
  const safeName = file.name?.trim() && /\.(wav|mp3|mpeg)$/i.test(file.name)
    ? file.name
    : `audio.${ext}`;
  formData.append('file', file, safeName);
  formData.append('voice_name', voiceName);
  formData.append('language', language);
  return apiClient.post<{ message: string; voice_name: string; language: string }>(
    '/voices/clone',
    formData,
    {
      headers: { 'Content-Type': undefined } as unknown as Record<string, string>,
    }
  );
};

export const listVoices = () => apiClient.get<VoiceInfo[]>('/voices');

export const getVoiceDetails = (voiceName: string) =>
  apiClient.get<VoiceInfo>(`/voices/${encodeURIComponent(voiceName)}`);

export const deleteVoice = (voiceName: string) =>
  apiClient.delete<{ message: string }>(`/voices/${encodeURIComponent(voiceName)}`);

export const synthesizeClonedVoice = (
  voiceName: string,
  text: string,
  language: string = 'en',
) => {
  return apiClient.post(
    '/voices/synthesize',
    {
      voice_name: voiceName,
      text,
      language,
    },
    {
      responseType: 'blob',
    },
  );
};

export default apiClient;