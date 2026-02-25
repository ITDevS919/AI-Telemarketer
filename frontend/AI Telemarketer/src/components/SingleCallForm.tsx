import React, { useState, useEffect } from 'react';
import { addCall, listVoices } from '../services/api';
import type { VoiceInfo } from '../services/api';

type CallMode = 'A' | 'B';

const SingleCallForm: React.FC = () => {
  const [phoneNumber, setPhoneNumber] = useState('');
  const [businessType, setBusinessType] = useState('MM');
  const [mode, setMode] = useState<CallMode>('B');
  const [clonedVoiceName, setClonedVoiceName] = useState<string>('');
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [isMakingCall, setIsMakingCall] = useState(false);
  const [status, setStatus] = useState<{ message: string; type: 'success' | 'error' | 'info' | null }>({
    message: '',
    type: null,
  });

  useEffect(() => {
    listVoices()
      .then((res) => setVoices(Array.isArray(res.data) ? res.data : []))
      .catch(() => setVoices([]));
  }, []);

  const handleSubmit = async () => {
    if (!phoneNumber.trim()) {
      setStatus({ message: 'Please enter a valid phone number', type: 'error' });
      return;
    }
    setIsMakingCall(true);
    setStatus({ message: 'Initiating call...', type: 'info' });
    try {
      const payload: Parameters<typeof addCall>[0] = {
        phone_number: phoneNumber.trim(),
        business_type: businessType,
      };
      payload.scripted = mode === 'A';
      if (mode === 'A' && clonedVoiceName.trim()) {
        payload.voice_name = clonedVoiceName.trim();
      }
      const res = await addCall(payload);
      const data = res.data;
      setStatus({
        message: `Call queued successfully. Call ID: ${data.call_id}`,
        type: 'success',
      });
      setPhoneNumber('');
    } catch (e: any) {
      setStatus({
        message: `Error making call: ${e?.message || 'Unknown error'}`,
        type: 'error',
      });
    } finally {
      setIsMakingCall(false);
    }
  };

  return (
    <div className="section single-call-form">
      <h2>Make a Single Call</h2>
      <div className="form-row">
        <div className="form-group">
          <label htmlFor="phone-number">Phone Number:</label>
          <input
            id="phone-number"
            type="text"
            value={phoneNumber}
            disabled={isMakingCall}
            placeholder="e.g., +447123456789"
            onChange={(e) => setPhoneNumber(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label htmlFor="business-type">Business Type:</label>
          <select
            id="business-type"
            value={businessType}
            disabled={isMakingCall}
            onChange={(e) => setBusinessType(e.target.value)}
          >
            <option value="MM">Making Money (MM)</option>
            <option value="SM">Saving Money (SM)</option>
          </select>
        </div>
      </div>
      <div className="form-row">
        <div className="form-group">
          <label htmlFor="call-mode">Mode:</label>
          <select
            id="call-mode"
            value={mode}
            disabled={isMakingCall}
            onChange={(e) => setMode(e.target.value as CallMode)}
            title="Version A = scripted 5-step; Version B = interactive LLM"
          >
            <option value="B">Version B (Interactive)</option>
            <option value="A">Version A (Scripted)</option>
          </select>
        </div>
        {mode === 'A' && (
          <div className="form-group">
            <label htmlFor="cloned-voice">Cloned voice (optional):</label>
            <select
              id="cloned-voice"
              value={clonedVoiceName}
              disabled={isMakingCall}
              onChange={(e) => setClonedVoiceName(e.target.value)}
              title="Use a cloned voice for Version A, or leave default for Piper"
            >
              <option value="">— Default (Piper) —</option>
              {voices.map((v) => (
                <option key={v.name} value={v.name}>
                  {v.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
      <button onClick={handleSubmit} disabled={isMakingCall || !phoneNumber.trim()}>
        {isMakingCall ? 'Calling...' : 'Make Call'}
      </button>
      {status.message && (
        <div className={`status-area ${status.type ? `status-${status.type}` : ''}`}>
          {status.message}
        </div>
      )}
    </div>
  );
};

export default SingleCallForm;

