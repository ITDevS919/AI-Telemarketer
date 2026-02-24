import React, { useEffect, useState } from 'react';
import { getDialerStatus, startDialer, stopDialer } from '../services/api';

interface DialerStatus {
  running?: boolean;
  initialized?: boolean;
  queued_calls?: number;
  active_calls?: number;
  retry_calls?: number;
  max_concurrent_calls?: number;
}

const DialerControl: React.FC = () => {
  const [status, setStatus] = useState<DialerStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [actionInProgress, setActionInProgress] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' | null }>({ text: '', type: null });

  const fetchStatus = async () => {
    setIsLoading(true);
    setMessage({ text: '', type: null });
    try {
      const res = await getDialerStatus();
      setStatus(res.data);
    } catch (e: any) {
      setStatus(null);
      setMessage({ text: e?.message || 'Failed to fetch dialer status', type: 'error' });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleStart = async () => {
    setActionInProgress(true);
    setMessage({ text: '', type: null });
    try {
      await startDialer();
      setMessage({ text: 'Dialer started successfully.', type: 'success' });
      await fetchStatus();
    } catch (e: any) {
      const detail = e?.response?.data?.detail ?? e?.message ?? 'Unknown error';
      setMessage({ text: `Failed to start dialer: ${detail}`, type: 'error' });
      await fetchStatus();
    } finally {
      setActionInProgress(false);
    }
  };

  const handleStop = async () => {
    setActionInProgress(true);
    setMessage({ text: '', type: null });
    try {
      await stopDialer();
      setMessage({ text: 'Dialer stopped successfully.', type: 'success' });
      await fetchStatus();
    } catch (e: any) {
      const detail = e?.response?.data?.detail ?? e?.message ?? 'Unknown error';
      setMessage({ text: `Failed to stop dialer: ${detail}`, type: 'error' });
      await fetchStatus();
    } finally {
      setActionInProgress(false);
    }
  };

  const running = status?.running === true;
  const disabled = actionInProgress || isLoading;

  return (
    <div className="section dialer-control">
      <h2>Dialer</h2>
      <div className="dialer-control-row">
        <button
          type="button"
          className="dialer-start-btn"
          onClick={handleStart}
          disabled={disabled || running}
          title={running ? 'Dialer is already running' : 'Start the dialer to process queued calls'}
        >
          {actionInProgress && !running ? 'Starting...' : 'Start Dialer'}
        </button>
        <button
          type="button"
          className="dialer-stop-btn"
          onClick={handleStop}
          disabled={disabled || !running}
          title={!running ? 'Dialer is not running' : 'Stop the dialer'}
        >
          {actionInProgress && running ? 'Stopping...' : 'Stop Dialer'}
        </button>
        <button type="button" onClick={fetchStatus} disabled={isLoading}>
          {isLoading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>
      {status && (
        <div className="dialer-status-text">
          {running ? (
            <>Dialer is <strong>running</strong>. Queue: {status.queued_calls ?? 0} · Active: {status.active_calls ?? 0}</>
          ) : (
            <>Dialer is <strong>stopped</strong>. Start the dialer to process calls.</>
          )}
        </div>
      )}
      {message.text && (
        <div className={`status-area ${message.type ? `status-${message.type}` : ''}`}>
          {message.text}
        </div>
      )}
    </div>
  );
};

export default DialerControl;
