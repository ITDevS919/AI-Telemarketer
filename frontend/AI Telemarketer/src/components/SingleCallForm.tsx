import React, { useState } from 'react';
import { addCall } from '../services/api';

const SingleCallForm: React.FC = () => {
  const [phoneNumber, setPhoneNumber] = useState('');
  const [businessType, setBusinessType] = useState('(m)');
  const [isMakingCall, setIsMakingCall] = useState(false);
  const [status, setStatus] = useState<{ message: string; type: 'success' | 'error' | 'info' | null }>({
    message: '',
    type: null,
  });

  const handleSubmit = async () => {
    if (!phoneNumber.trim()) {
      setStatus({ message: 'Please enter a valid phone number', type: 'error' });
      return;
    }
    setIsMakingCall(true);
    setStatus({ message: 'Initiating call...', type: 'info' });
    try {
      const res = await addCall({
        phone_number: phoneNumber.trim(),
        business_type: businessType,
      });
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

