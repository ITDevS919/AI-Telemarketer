import React from 'react';
import HealthStatus from '../components/HealthStatus';
import SingleCallForm from '../components/SingleCallForm';
import ControlPanel from '../components/ControlPanel';
import RegulationChecker from '../components/RegulationChecker';

const DashboardPage: React.FC = () => {
  return (
    <div className="dashboard">
      <div className="welcome-message">
        <h1>Welcome to AI Telemarketer v2!</h1>
        <p>
          Monitor system health, check regulatory compliance, and make calls using the controls
          below.
        </p>
      </div>

      <HealthStatus />

      <div className="regulations-section">
        <RegulationChecker />
      </div>

      <div className="calls-grid">
        <SingleCallForm />
        <ControlPanel />
      </div>
    </div>
  );
};

export default DashboardPage;

