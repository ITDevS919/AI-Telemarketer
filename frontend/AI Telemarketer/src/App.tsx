import React from 'react';
import { NavLink, Route, Routes } from 'react-router-dom';
import DashboardPage from './pages/DashboardPage';
import CallsPage from './pages/CallsPage';
import SettingsPage from './pages/SettingsPage';
import VoiceManager from './components/VoiceManager';
import './assets/base.css';
import './assets/main.css';
import './assets/app-styles.css';

const App: React.FC = () => {
  return (
    <div className="app-layout">
      <header className="app-header">
        AI Telemarketing
      </header>

      <div className="app-body">
        <nav className="app-nav">
          <NavLink to="/" end className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            Dashboard
          </NavLink>
          <NavLink to="/calls" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            Calls
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            Settings
          </NavLink>
          <NavLink to="/voices" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            Voices
          </NavLink>
        </nav>

        <main className="app-content">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/calls" element={<CallsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/voices" element={<VoiceManager />} />
          </Routes>
        </main>
      </div>
    </div>
  );
};

export default App;

