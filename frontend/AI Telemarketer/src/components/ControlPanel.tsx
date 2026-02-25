import React, { useState, useEffect } from 'react';
import { addBatchCalls, listVoices } from '../services/api';
import type { VoiceInfo } from '../services/api';

type CallMode = 'A' | 'B';

interface StatusMessage {
  message: string;
  type: 'success' | 'error' | 'info' | null;
}

const ControlPanel: React.FC = () => {
  const [input, setInput] = useState('');
  const [mode, setMode] = useState<CallMode>('B');
  const [clonedVoiceName, setClonedVoiceName] = useState<string>('');
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [isStarting, setIsStarting] = useState(false);
  const [status, setStatus] = useState<StatusMessage>({ message: '', type: null });

  useEffect(() => {
    listVoices()
      .then((res) => setVoices(Array.isArray(res.data) ? res.data : []))
      .catch(() => setVoices([]));
  }, []);

  const parseLines = () => {
    setStatus({ message: '', type: null });
    const lines = input.trim().split('\n');
    const requests: { phone_number: string; business_type: string; scripted?: boolean; voice_name?: string }[] = [];
    let error: string | null = null;

    lines.forEach((line, idx) => {
      const trimmed = line.trim();
      if (!trimmed) return;
      const parts = trimmed.split(',');
      if (parts.length !== 2) {
        error = `Error parsing line ${idx + 1}: Expected format 'phone_number, business_type'.`;
        return;
      }
      const phone = parts[0].trim();
      const bt = parts[1].trim();
      if (!phone || !bt) {
        error = `Error parsing line ${idx + 1}: Invalid format or empty values.`;
        return;
      }
      const req: { phone_number: string; business_type: string; scripted?: boolean; voice_name?: string } = {
        phone_number: phone,
        business_type: bt,
      };
      req.scripted = mode === 'A';
      if (mode === 'A' && clonedVoiceName.trim()) req.voice_name = clonedVoiceName.trim();
      requests.push(req);
    });

    if (error) {
      setStatus({ message: error, type: 'error' });
      return null;
    }
    if (requests.length === 0) {
      setStatus({
        message:
          'Please enter call requests in the format: phone_number, business_type (one per line).',
        type: 'error',
      });
      return null;
    }
    return requests;
  };

  const handleStart = async () => {
    const data = parseLines();
    if (!data) return;

    setIsStarting(true);
    setStatus({ message: `Initiating ${data.length} calls...`, type: 'info' });
    try {
      const res = await addBatchCalls(data);
      const result = res.data;
      let summary = `Request processed: ${result.queued} queued, ${result.blocked} blocked.`;
      if (Array.isArray(result.details)) {
        for (const d of result.details) {
          summary += `\n  - ${d.phone_number}: ${d.status}${d.reason ? ' (' + d.reason + ')' : ''}`;
        }
      }
      setStatus({ message: summary, type: 'success' });
      setInput('');
    } catch (e: any) {
      setStatus({
        message: `Error starting calls: ${e?.message || 'Unknown error'}`,
        type: 'error',
      });
    } finally {
      setIsStarting(false);
    }
  };

  return (
    <div className="section control-panel">
      <h2>Control Panel</h2>
      <div className="form-row">
        <div className="form-group">
          <label htmlFor="batch-mode">Mode (for all calls):</label>
          <select
            id="batch-mode"
            value={mode}
            disabled={isStarting}
            onChange={(e) => setMode(e.target.value as CallMode)}
            title="Version A = scripted; Version B = interactive LLM"
          >
            <option value="B">Version B (Interactive)</option>
            <option value="A">Version A (Scripted)</option>
          </select>
        </div>
        {mode === 'A' && (
          <div className="form-group">
            <label htmlFor="batch-voice">Cloned voice (optional):</label>
            <select
              id="batch-voice"
              value={clonedVoiceName}
              disabled={isStarting}
              onChange={(e) => setClonedVoiceName(e.target.value)}
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
      <label htmlFor="call-requests">Enter Calls (Phone Number, Business Type - one per line):</label>
      <textarea
        id="call-requests"
        rows={10}
        placeholder={'e.g.,\n+447123456789, MM\n+442079460000, SM\n...'}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        disabled={isStarting}
      />
      <button id="start-calls-btn" onClick={handleStart} disabled={isStarting}>
        {isStarting ? 'Starting...' : 'Start Calls'}
      </button>
      {status.message && (
        <div className={`status-area ${status.type ? `status-${status.type}` : ''}`}>
          {status.message}
        </div>
      )}
    </div>
  );
};

export default ControlPanel;

