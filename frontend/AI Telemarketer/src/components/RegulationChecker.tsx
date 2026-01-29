import React, { useState } from 'react';
import { checkRegulations, getRegulationsStatus, getRegulationsHistory } from '../services/api';
import type {
  RegulationsCheckResponse,
  RegulationsStatusResponse,
  RegulationsHistoryResponse,
} from '../services/api';

const RegulationChecker: React.FC = () => {
  const [phoneNumber, setPhoneNumber] = useState('');
  const [callerId, setCallerId] = useState('+441234567890');
  const [checkResult, setCheckResult] = useState<RegulationsCheckResponse | null>(null);
  const [status, setStatus] = useState<RegulationsStatusResponse | null>(null);
  const [history, setHistory] = useState<RegulationsHistoryResponse | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [isLoadingStatus, setIsLoadingStatus] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCheck = async () => {
    if (!phoneNumber.trim()) {
      setError('Please enter a phone number');
      return;
    }
    setIsChecking(true);
    setError(null);
    setCheckResult(null);
    try {
      const res = await checkRegulations({
        phone_number: phoneNumber.trim(),
        caller_id: callerId.trim() || undefined,
      });
      setCheckResult(res.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to check regulations');
      setCheckResult(null);
    } finally {
      setIsChecking(false);
    }
  };

  const handleGetStatus = async () => {
    setIsLoadingStatus(true);
    setError(null);
    try {
      const res = await getRegulationsStatus();
      setStatus(res.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to get regulations status');
      setStatus(null);
    } finally {
      setIsLoadingStatus(false);
    }
  };

  const handleGetHistory = async () => {
    if (!phoneNumber.trim()) {
      setError('Please enter a phone number');
      return;
    }
    setIsLoadingHistory(true);
    setError(null);
    try {
      const res = await getRegulationsHistory(phoneNumber.trim());
      setHistory(res.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to get regulations history');
      setHistory(null);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  return (
    <div className="section regulation-checker">
      <h2>UK Regulations Compliance Check</h2>

      <div className="form-group">
        <label htmlFor="phone-number-check">Phone Number:</label>
        <input
          id="phone-number-check"
          type="text"
          value={phoneNumber}
          onChange={(e) => setPhoneNumber(e.target.value)}
          placeholder="e.g., +447123456789"
        />
      </div>

      <div className="form-group">
        <label htmlFor="caller-id-check">Caller ID (optional):</label>
        <input
          id="caller-id-check"
          type="text"
          value={callerId}
          onChange={(e) => setCallerId(e.target.value)}
          placeholder="e.g., +441234567890"
        />
      </div>

      <div className="button-group">
        <button onClick={handleCheck} disabled={isChecking || !phoneNumber.trim()}>
          {isChecking ? 'Checking...' : 'Check Compliance'}
        </button>
        <button onClick={handleGetStatus} disabled={isLoadingStatus}>
          {isLoadingStatus ? 'Loading...' : 'Get Status'}
        </button>
        <button onClick={handleGetHistory} disabled={isLoadingHistory || !phoneNumber.trim()}>
          {isLoadingHistory ? 'Loading...' : 'Get History'}
        </button>
      </div>

      {error && <div className="status-area status-error">{error}</div>}

      {checkResult && (
        <div className={`status-area ${checkResult.permitted ? 'status-success' : 'status-error'}`}>
          <strong>Compliance Check Result:</strong>
          <p>Permitted: {checkResult.permitted ? 'Yes' : 'No'}</p>
          {checkResult.reason && <p>Reason: {checkResult.reason}</p>}
          {checkResult.violation_type && <p>Violation Type: {checkResult.violation_type}</p>}
        </div>
      )}

      {status && (
        <div className="status-area status-info">
          <strong>Regulations System Status:</strong>
          <p>Initialized: {status.initialized ? 'Yes' : 'No'}</p>
          {status.database_path && <p>Database: {status.database_path}</p>}
          {status.tps_enabled !== undefined && (
            <p>TPS Enabled: {status.tps_enabled ? 'Yes' : 'No'}</p>
          )}
        </div>
      )}

      {history && (
        <div className="status-area status-info">
          <strong>Call History for {history.phone_number}:</strong>
          {history.calls && history.calls.length > 0 ? (
            <ul style={{ marginTop: '0.5rem', paddingLeft: '1.5rem' }}>
              {history.calls.map((call, idx) => (
                <li key={idx} style={{ marginBottom: '0.5rem' }}>
                  <strong>Call SID:</strong> {call.call_sid}
                  <br />
                  <strong>Time:</strong>{' '}
                  {new Date(call.timestamp * 1000).toLocaleString()}
                  <br />
                  <strong>Status:</strong> {call.status}
                  {call.violation_type && (
                    <>
                      <br />
                      <strong>Violation:</strong> {call.violation_type}
                    </>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p>No call history found for this number.</p>
          )}
        </div>
      )}
    </div>
  );
};

export default RegulationChecker;
