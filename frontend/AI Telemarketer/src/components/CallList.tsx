import React, { useEffect, useState } from 'react';
import { getRecentCalls } from '../services/api';

interface CallSummary {
  call_sid: string;
  to_number: string | null;
  state: string | null;
  lead_status: string | null;
  start_time: number | null;
  duration: number | null;
}

interface Props {
  onCallSelected: (id: string | null) => void;
  selectedId: string | null;
}

const CallList: React.FC<Props> = ({ onCallSelected, selectedId }) => {
  const [calls, setCalls] = useState<CallSummary[]>([]);
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const formatTime = (ts: number | null) => {
    if (!ts) return 'N/A';
    try {
      return new Date(ts * 1000).toLocaleString();
    } catch {
      return 'Invalid Date';
    }
  };

  const refresh = async () => {
    setIsLoading(true);
    setError(null);
    setCalls([]);
    onCallSelected(null);
    try {
      const res = await getRecentCalls(limit, offset);
      const data = res.data;
      setCalls(Array.isArray(data) ? data : data.calls || []);
    } catch (e: any) {
      setError(e?.message || 'Error fetching calls');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="section call-list-section">
      <h2>Recent Calls</h2>
      <div className="controls">
        <button onClick={refresh} disabled={isLoading}>
          {isLoading ? 'Refreshing...' : 'Refresh List'}
        </button>
        <div className="pagination">
          <label htmlFor="limit">Limit:</label>
          <input
            id="limit"
            type="number"
            min={1}
            max={100}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            disabled={isLoading}
          />
          <label htmlFor="offset">Offset:</label>
          <input
            id="offset"
            type="number"
            min={0}
            step={50}
            value={offset}
            onChange={(e) => setOffset(Number(e.target.value))}
            disabled={isLoading}
          />
        </div>
      </div>

      {error && <div className="status-area status-error">{error}</div>}

      {!isLoading && !error && calls.length > 0 && (
        <ul className="call-list">
          {calls.map((call) => (
            <li
              key={call.call_sid}
              onClick={() => onCallSelected(call.call_sid)}
              className={call.call_sid === selectedId ? 'selected' : ''}
            >
              <span>
                <b>SID:</b> {call.call_sid}
              </span>
              <span>
                <b>To:</b> {call.to_number || 'N/A'}
              </span>
              <span>
                <b>State:</b> {call.state || 'N/A'}
              </span>
              <span>
                <b>Lead:</b> {call.lead_status || 'N/A'}
              </span>
              <span>
                <b>Start:</b> {formatTime(call.start_time)}
              </span>
              <span>
                <b>Duration:</b>{' '}
                {call.duration != null ? `${call.duration.toFixed(1)}s` : 'N/A'}
              </span>
            </li>
          ))}
        </ul>
      )}

      {isLoading && <div className="loading-message">Loading calls...</div>}
      {!isLoading && !error && calls.length === 0 && (
        <div className="no-calls-message">No calls found.</div>
      )}
    </div>
  );
};

export default CallList;

