import axios, { AxiosError } from 'axios';
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api', // Adjust if your backend runs on a different port/host
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

export default apiClient;