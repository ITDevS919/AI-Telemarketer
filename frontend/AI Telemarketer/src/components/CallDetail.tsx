import React, { useEffect, useState } from 'react';
import { getCallDetails } from '../services/api';

interface CallHistoryEntry {
  speaker: string;
  text: string;
  timestamp: number;
}

interface CallDetails {
  call_sid: string;
  [key: string]: any;
  history?: CallHistoryEntry[];
  qualifiers_met?: Record<string, boolean>;
  recording_url?: string | null;
  script_type?: string | null;
}

interface Props {
  selectedCallId: string | null;
}

const CallDetail: React.FC<Props> = ({ selectedCallId }) => {
  const [details, setDetails] = useState<CallDetails | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [initialLoadDone, setInitialLoadDone] = useState(false);

  useEffect(() => {
    const fetchDetails = async () => {
      if (!selectedCallId) {
        setDetails(null);
        setInitialLoadDone(false);
        return;
      }
      setIsLoading(true);
      setError(null);
      setInitialLoadDone(true);
      try {
        const res = await getCallDetails(selectedCallId);
        setDetails(res.data);
      } catch (e: any) {
        setError(e?.message || 'Error fetching call details');
        setDetails(null);
      } finally {
        setIsLoading(false);
      }
    };
    fetchDetails();
  }, [selectedCallId]);

  const formatKey = (key: string) =>
    key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());

  const formatDateTime = (value: number | string | null, isISO = false) => {
    if (!value) return 'N/A';
    try {
      const date = isISO ? new Date(value as string) : new Date((value as number) * 1000);
      if (isNaN(date.getTime())) return 'Invalid Date';
      return date.toLocaleString();
    } catch {
      return 'Invalid Date';
    }
  };

  const renderValue = (key: string, value: any) => {
    if (value == null) return 'N/A';
    if (['start_time', 'last_update_time', 'created_at'].includes(key)) {
      return formatDateTime(value);
    }
    if (key === 'is_outbound') return value ? 'Yes' : 'No';
    if (key === 'duration') {
      return typeof value === 'number' ? `${value.toFixed(2)} seconds` : 'N/A';
    }
    if (key === 'appointment_time' || key === 'appointment_booked_time') {
      return formatDateTime(value, true);
    }
    return value;
  };

  if (isLoading) {
    return (
      <div className="section call-details-section">
        <h2>Call Details</h2>
        <div className="loading-message">Loading details...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="section call-details-section">
        <h2>Call Details</h2>
        <div className="status-area status-error">{error}</div>
      </div>
    );
  }

  if (!details && !initialLoadDone) {
    return (
      <div className="section call-details-section">
        <h2>Call Details</h2>
        <div className="no-selection-message">
          <p>Select a call from the list to view details.</p>
        </div>
      </div>
    );
  }

  if (!details && initialLoadDone) {
    return (
      <div className="section call-details-section">
        <h2>Call Details</h2>
        <div className="no-selection-message">
          <p>Call details not found or not loaded.</p>
        </div>
      </div>
    );
  }

  const { history, qualifiers_met, recording_url, script_type, call_sid, ...rest } = details!;

  return (
    <div className="section call-details-section">
      <h2>Call Details</h2>
      <h3>Call SID: {call_sid}</h3>
      {script_type && (
        <div className="script-badge">
          Script Type:{' '}
          <span
            className={
              script_type === 'MM'
                ? 'mm-badge'
                : script_type === 'SM'
                ? 'sm-badge'
                : undefined
            }
          >
            {script_type}
          </span>
        </div>
      )}

      <ul className="details-list">
        {Object.entries(rest).map(([key, value]) => (
          <li key={key}>
            <b>{formatKey(key)}:</b> {renderValue(key, value)}
          </li>
        ))}
      </ul>

      <h4>Qualifiers Met:</h4>
      {qualifiers_met && Object.keys(qualifiers_met).length > 0 ? (
        <ul className="details-list">
          {Object.entries(qualifiers_met).map(([key, value]) => (
            <li key={key}>
              <b>{key}:</b> {value ? 'Yes' : 'No'}
            </li>
          ))}
        </ul>
      ) : (
        <p>None recorded.</p>
      )}

      <h4>Conversation History:</h4>
      {history && history.length > 0 ? (
        <div className="history-container">
          {history.map((entry, idx) => (
            <div key={idx} className="history-entry">
              <strong>{entry.speaker || 'unknown'}:</strong>
              <p>{entry.text || ''}</p>
              <small>({formatDateTime(entry.timestamp)})</small>
            </div>
          ))}
        </div>
      ) : (
        <p>No history recorded.</p>
      )}

      {recording_url && (
        <div className="recording-player">
          <h4>Call Recording:</h4>
          <audio controls src={recording_url}>
            Your browser does not support the audio element.
          </audio>
          <a href={recording_url} target="_blank" rel="noreferrer" className="recording-link">
            Open Recording in New Tab
          </a>
        </div>
      )}
    </div>
  );
};

export default CallDetail;

