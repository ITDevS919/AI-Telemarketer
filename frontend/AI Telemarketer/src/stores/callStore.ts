import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import apiService from '../services/api'

// --- Interfaces/Types based on backend API responses --- 

interface CallSummary {
  call_sid: string;
  to_number: string | null;
  state: string | null;
  lead_status: string | null;
  start_time: number | null; // Assuming timestamp float
  duration: number | null;
  // Add other summary fields if needed
}

interface CallHistoryEntry {
    speaker: string;
    text: string;
    timestamp: number; // Assuming timestamp float
}

interface CallDetails extends CallSummary {
  // Inherits fields from CallSummary
  from_number: string | null;
  is_outbound: boolean;
  script_name: string | null;
  business_type: string | null;
  owner_name: string | null;
  gatekeeper_name: string | null;
  agent_name: string | null;
  client_name: string | null;
  qualifiers_met: Record<string, boolean> | null; // Deserialized object
  highlighted_problem: string | null;
  appointment_time: string | null; // ISO string
  contact_mobile: string | null;
  contact_email: string | null;
  additional_decision_makers: string | null;
  recording_url: string | null;
  created_at: number | null; // Assuming timestamp float
  last_update_time: number | null; // Assuming timestamp float
  history: CallHistoryEntry[] | null; // Deserialized array
  appointment_booked_time: string | null;
  contact_mobile_collected: string | null;
  contact_email_collected: string | null;
  // lead_status already in CallSummary
}

interface StatusMessage {
    message: string;
    type: 'success' | 'error' | 'info' | 'clear';
}

interface StartCallDetail {
    phone_number: string;
    call_sid?: string;
    status: 'initiated' | 'blocked' | 'error';
    reason?: string;
}

interface StartCallsResponse {
    initiated_calls: number;
    blocked_calls: number;
    details: StartCallDetail[];
}

// Define type for Dialer Settings
interface DialerSettings {
    max_concurrent_calls: number;
    max_retries: number;
    retry_delay_seconds: number;
}

// Add this function to handle API errors
function handleApiError(error: any): string {
    if (error.response) {
        // The request was made and the server responded with a status code
        // that falls out of the range of 2xx
        if (error.response.data && error.response.data.detail) {
            return typeof error.response.data.detail === 'string' 
                ? error.response.data.detail 
                : JSON.stringify(error.response.data.detail);
        }
        return `Server error: ${error.response.status}`;
    } else if (error.request) {
        // The request was made but no response was received
        return 'No response from server. Please check your connection.';
    } else {
        // Something happened in setting up the request that triggered an Error
        return error.message || 'An unknown error occurred';
    }
}

// --- Store Definition --- 

export const useCallStore = defineStore('calls', () => {
    // --- State --- 
    const calls = ref<CallSummary[]>([]);
    const selectedCallDetails = ref<CallDetails | null>(null);
    const isLoadingList = ref(false);
    const isLoadingDetails = ref(false);
    const listError = ref<string | null>(null);
    const detailError = ref<string | null>(null);
    const controlPanelStatus = ref<StatusMessage>({ message: '', type: 'clear' });

    // --- NEW Dialer Settings State ---
    const dialerSettings = ref<DialerSettings | null>(null);
    const isLoadingSettings = ref(false);
    const settingsError = ref<string | null>(null);
    const settingsUpdateStatus = ref<StatusMessage>({ message: '', type: 'clear' });
    // --- END NEW Dialer Settings State ---

    // Base URL (Consider moving to environment variables in a real app)
    const API_BASE_URL = 'http://localhost:8000';

    // --- Actions --- 

    /**
     * Fetches recent calls from the backend.
     */
    async function fetchRecentCalls(limit: number = 50, offset: number = 0) {
        isLoadingList.value = true;
        listError.value = null;
        calls.value = []; // Clear previous calls
        console.log(`Fetching calls with limit=${limit}, offset=${offset}`);
        try {
            const result = await apiService.getRecentCalls(limit, offset);
            calls.value = result.calls || [];
            console.log(`Fetched ${calls.value.length} calls.`);
        } catch (error: any) {
            console.error('Error fetching calls:', error);
            listError.value = `Error fetching calls: ${error.message}`;
        } finally {
            isLoadingList.value = false;
        }
    }

    /**
     * Fetches details for a specific call.
     */
    async function fetchCallDetails(callSid: string) {
        isLoadingDetails.value = true;
        detailError.value = null;
        selectedCallDetails.value = null; // Clear previous details
        console.log(`Fetching details for ${callSid}`);

        try {
            const details = await apiService.getCallDetails(callSid);
            selectedCallDetails.value = details;
            console.log(`Fetched details for ${callSid}`);
        } catch (error: any) {
            console.error(`Error fetching details for ${callSid}:`, error);
            detailError.value = `Error fetching details: ${error.message}`;
        } finally {
            isLoadingDetails.value = false;
        }
    }

    /**
     * Initiates calls via the /start_calls endpoint.
     */
    async function startCalls(callData: Array<{ phone_number: string; business_type: string }>) {
        controlPanelStatus.value = { message: `Initiating ${callData.length} calls...`, type: 'info' };
        let success = false;

        try {
            const result = await apiService.startCalls(callData);
            let summary = `Request processed: ${result.initiated_calls} initiated, ${result.blocked_calls} blocked.`;
            result.details.forEach((d: { phone_number: string; status: string; reason?: string }) => {
                 summary += `\n  - ${d.phone_number}: ${d.status}${d.reason ? ' (' + d.reason + ')' : ''}`; 
            });
            controlPanelStatus.value = { message: summary, type: 'success' };
            success = true;
            // Refresh the call list after successfully starting calls
            fetchRecentCalls(); 

        } catch (error: any) {
            console.error('Error starting calls:', error);
            controlPanelStatus.value = { message: `Error starting calls: ${error.message}`, type: 'error' };
        } 
        return success;
    }

    /**
     * Makes a single call via the /make_call endpoint.
     */
    async function makeCall(toNumber: string, businessType: string) {
        controlPanelStatus.value = { message: `Initiating call to ${toNumber}...`, type: 'info' };
        let success = false;

        try {
            const result = await apiService.makeCall(toNumber, businessType);
            controlPanelStatus.value = { 
                message: `Call initiated successfully. Call SID: ${result.call_sid}`, 
                type: 'success' 
            };
            success = true;
            // Refresh the call list after successfully making a call
            fetchRecentCalls();
        } catch (error: any) {
            console.error('Error making call:', error);
            controlPanelStatus.value = { message: `Error making call: ${error.message}`, type: 'error' };
        }
        return success;
    }

    /**
     * Checks the health status of the telemarketer v2 service.
     */
    async function checkHealth() {
        try {
            const result = await apiService.checkHealth();
            console.log('Health check result:', result);
            return result;
        } catch (error: any) {
            console.error('Health check failed:', error);
            return null;
        }
    }

    /**
     * Checks if a phone number complies with UK calling regulations.
     * @param phoneNumber The phone number to check
     * @param callerId The caller ID to use for the check
     */
    async function checkRegulations(phoneNumber: string, callerId: string = '+441234567890') {
        try {
            const result = await apiService.checkRegulations(phoneNumber, callerId);
            console.log('Regulations check result:', result);
            return result;
        } catch (error: any) {
            console.error('Regulations check failed:', error);
            throw error;
        }
    }

    /**
     * Gets the status of the regulations system.
     */
    async function getRegulationsStatus() {
        try {
            const result = await apiService.getRegulationsStatus();
            console.log('Regulations status:', result);
            return result;
        } catch (error: any) {
            console.error('Getting regulations status failed:', error);
            return null;
        }
    }

    /**
     * Gets regulations history for a phone number.
     * @param phoneNumber The phone number to get history for
     * @param days Number of days to look back
     */
    async function getRegulationsHistory(phoneNumber: string, days: number = 30) {
        try {
            const result = await apiService.getRegulationsHistory(phoneNumber, days);
            console.log('Regulations history:', result);
            return result;
        } catch (error: any) {
            console.error('Getting regulations history failed:', error);
            return [];
        }
    }

    // --- NEW Dialer Settings Actions ---

    /**
     * Fetches current dialer settings from the backend.
     */
    async function fetchDialerSettings() {
        isLoadingSettings.value = true;
        settingsError.value = null;
        settingsUpdateStatus.value = { message: '', type: 'clear' }; // Clear update status
        console.log('Fetching dialer settings...');
        try {
            const response = await apiService.getDialerSettings();
            dialerSettings.value = response.data;
            console.log('Fetched dialer settings:', response.data);
        } catch (error: any) {
            console.error('Error fetching dialer settings:', error);
            settingsError.value = `Error fetching settings: ${error.message}`;
        } finally {
            isLoadingSettings.value = false;
        }
    }

    /**
     * Updates dialer settings on the backend.
     * @param {DialerSettings} settingsToUpdate The new settings values.
     */
    async function updateDialerSettings(settingsToUpdate: DialerSettings) {
        isLoadingSettings.value = true; // Use same flag for update operation
        settingsError.value = null;
        settingsUpdateStatus.value = { message: 'Updating settings...', type: 'info' };
        console.log('Updating dialer settings:', settingsToUpdate);
        try {
            const response = await apiService.updateDialerSettings(settingsToUpdate);
            // Backend returns settings directly, not wrapped in current_settings
            dialerSettings.value = response.data;
            settingsUpdateStatus.value = { message: 'Settings updated successfully.', type: 'success' };
            console.log('Dialer settings updated:', dialerSettings.value);

        } catch (error: any) {
            console.error('Error updating dialer settings:', error);
            settingsError.value = `Error updating settings: ${error.message}`;
            settingsUpdateStatus.value = { message: `Error: ${error.message}`, type: 'error' };
        } finally {
            isLoadingSettings.value = false;
        }
    }

    // --- END NEW Dialer Settings Actions ---

    // --- Return --- 
    return {
        // State
        calls,
        selectedCallDetails,
        isLoadingList,
        isLoadingDetails,
        listError,
        detailError,
        controlPanelStatus,

        // Dialer Settings State
        dialerSettings,
        isLoadingSettings,
        settingsError,
        settingsUpdateStatus,

        // Actions
        fetchRecentCalls,
        fetchCallDetails,
        startCalls,
        makeCall,
        checkHealth,
        
        // Regulation Actions
        checkRegulations,
        getRegulationsStatus,
        getRegulationsHistory,

        // Dialer Settings Actions
        fetchDialerSettings,
        updateDialerSettings,
    }
})