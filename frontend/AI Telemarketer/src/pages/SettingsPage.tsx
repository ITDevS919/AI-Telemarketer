import React, { useEffect, useState } from 'react';
import { getDialerSettings, updateDialerSettings } from '../services/api';

interface DialerSettings {
  max_concurrent_calls: number;
  max_retries: number;
  retry_delay_seconds: number;
  call_timeout_seconds: number;
}

const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<DialerSettings | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [statusType, setStatusType] = useState<'success' | 'error' | 'info' | null>(null);

  useEffect(() => {
    const fetchSettings = async () => {
      setIsLoading(true);
      setError(null);
      setStatusMessage(null);
      try {
        const res = await getDialerSettings();
        setSettings(res.data);
      } catch (e: any) {
        setError(e?.message || 'Failed to load settings');
      } finally {
        setIsLoading(false);
      }
    };
    fetchSettings();
  }, []);

  const handleChange =
    (key: keyof DialerSettings) => (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!settings) return;
      const value = Number(e.target.value);
      setSettings({ ...settings, [key]: value });
    };

  const handleSave = async () => {
    if (!settings) return;
    if (
      settings.max_concurrent_calls < 1 ||
      settings.max_retries < 0 ||
      settings.retry_delay_seconds < 0
    ) {
      setStatusMessage('Invalid input. Please ensure values are positive (or 0 for retries).');
      setStatusType('error');
      setError('Validation error');
      return;
    }
    setIsLoading(true);
    setError(null);
    setStatusMessage('Updating settings...');
    setStatusType('info');
    try {
      const res = await updateDialerSettings(settings);
      setSettings(res.data);
      setStatusMessage('Settings updated successfully.');
      setStatusType('success');
    } catch (e: any) {
      setError(e?.message || 'Failed to update settings');
      setStatusMessage(`Error: ${e?.message || 'Failed to update settings'}`);
      setStatusType('error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="settings-view">
      <h1>Settings</h1>

      {isLoading && !settings && <div className="loading-message">Loading settings...</div>}
      {error && !settings && <div className="status-area status-error">{error}</div>}
      {!isLoading && !error && !settings && (
        <div className="loading-message">Could not load settings.</div>
      )}

      {settings && (
        <div className="settings-form section">
          <h2>Dialer Configuration</h2>

          <div className="form-group">
            <label htmlFor="max-concurrent">Max Concurrent Calls:</label>
            <input
              id="max-concurrent"
              type="number"
              min={1}
              value={settings.max_concurrent_calls}
              onChange={handleChange('max_concurrent_calls')}
            />
            <small>Maximum number of simultaneous outbound calls.</small>
          </div>

          <div className="form-group">
            <label htmlFor="max-retries">Max Retries:</label>
            <input
              id="max-retries"
              type="number"
              min={0}
              value={settings.max_retries}
              onChange={handleChange('max_retries')}
            />
            <small>Maximum number of retry attempts for failed calls (0 to disable retries).</small>
          </div>

          <div className="form-group">
            <label htmlFor="retry-delay">Retry Delay (seconds):</label>
            <input
              id="retry-delay"
              type="number"
              min={0}
              value={settings.retry_delay_seconds}
              onChange={handleChange('retry_delay_seconds')}
            />
            <small>Delay in seconds before retrying a failed call.</small>
          </div>

          <button onClick={handleSave} disabled={isLoading}>
            {isLoading ? 'Saving...' : 'Save Settings'}
          </button>

          {statusMessage && (
            <div className={`status-area ${statusType ? `status-${statusType}` : ''}`}>
              {statusMessage}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SettingsPage;

