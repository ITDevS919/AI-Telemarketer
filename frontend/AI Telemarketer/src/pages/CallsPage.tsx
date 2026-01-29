import React, { useState } from 'react';
import CallList from '../components/CallList';
import CallDetail from '../components/CallDetail';

const CallsPage: React.FC = () => {
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null);

  return (
    <div className="calls-view">
      <h1>Call Management</h1>
      <div className="layout-container">
        <div className="call-list-container">
          <CallList onCallSelected={setSelectedCallId} selectedId={selectedCallId} />
        </div>
        <div className="call-detail-container">
          <CallDetail selectedCallId={selectedCallId} />
        </div>
      </div>
    </div>
  );
};

export default CallsPage;

