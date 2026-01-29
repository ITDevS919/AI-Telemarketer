import React, { useEffect, useState } from 'react';
import { getDialerStatus } from '../services/api';

interface DialerStatus {
  queued_calls: number;
  active_calls: number;
  retry_calls: number;
  max_concurrent_calls: number;
  running?: boolean;
  initialized?: boolean;
}

const HealthStatus: React.FC = () => {
  const [status, setStatus] = useState<DialerStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  const refresh = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getDialerStatus();
      setStatus(res.data);
      setLastChecked(new Date().toLocaleTimeString());
    } catch (e: any) {
      setError(e?.message || 'Failed to fetch status');
      setStatus(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="health-status-container">
      <h2>System Health</h2>
      <div className="refresh-control">
        <button onClick={refresh} disabled={isLoading}>
          {isLoading ? 'Checking...' : 'Check Health'}
        </button>
        {lastChecked && <div className="last-checked">Last checked: {lastChecked}</div>}
      </div>

      {error && <div className="health-error">Error checking health: {error}</div>}

      {!error && status && (
        <div className="health-indicators">
          <div
            className={`health-status-indicator overall ${
              status.initialized ? 'status-ok' : 'status-error'
            }`}
          >
            {status.initialized && (
              <div className="indicator-icon">
                <svg viewBox="0 0 20 20">
                  <path d="M5 10l3 3 7-7" />
                </svg>
              </div>
            )}
            <div className="indicator-content">
              <span className="indicator-label">Overall Status:</span>
              <span className="indicator-value">
                {status.initialized ? 'ok' : 'not initialized'}
              </span>
            </div>
          </div>
          <div className="status-grid">
            <div className="health-status-indicator status-ok">
              <div className="indicator-icon">
                <svg viewBox="0 0 20 20">
                  <path d="M5 10l3 3 7-7" />
                </svg>
              </div>
              <div className="indicator-content">
                <span className="indicator-label">Queued Calls:</span>
                <span className="indicator-value">{status.queued_calls}</span>
              </div>
            </div>
            <div className="health-status-indicator status-ok">
              <div className="indicator-icon">
                <svg viewBox="0 0 20 20">
                  <path d="M5 10l3 3 7-7" />
                </svg>
              </div>
              <div className="indicator-content">
                <span className="indicator-label">Active Calls:</span>
                <span className="indicator-value">{status.active_calls}</span>
              </div>
            </div>
            <div className="health-status-indicator status-ok">
              <div className="indicator-icon">
                <svg viewBox="0 0 20 20">
                  <path d="M5 10l3 3 7-7" />
                </svg>
              </div>
              <div className="indicator-content">
                <span className="indicator-label">Retry Calls:</span>
                <span className="indicator-value">{status.retry_calls}</span>
              </div>
            </div>
            <div className="health-status-indicator status-ok">
              <div className="indicator-icon">
                <svg viewBox="0 0 20 20">
                  <path d="M5 10l3 3 7-7" />
                </svg>
              </div>
              <div className="indicator-content">
                <span className="indicator-label">Max Concurrent:</span>
                <span className="indicator-value">{status.max_concurrent_calls}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {!error && !status && !isLoading && (
        <div className="no-data-message">Click \"Check Health\" to verify system status.</div>
      )}
    </div>
  );
};

export default HealthStatus;

