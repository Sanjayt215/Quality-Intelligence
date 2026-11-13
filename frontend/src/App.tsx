// frontend/src/App.tsx - Quality Intelligence Main App Shell

import React, { useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import { AnalysisProvider } from './context/AnalysisContext';
import { Sidebar } from './components/Sidebar';
import { Navbar } from './components/Navbar';
import { ActiveRepoBar } from './components/ActiveRepoBar';

import { OverviewPage } from './pages/OverviewPage';
import { QueuePage } from './pages/QueuePage';
import { AnalysisPage } from './pages/AnalysisPage';
import { InsightsPage } from './pages/InsightsPage';
import { ReliabilityPage } from './pages/ReliabilityPage';
import { ModelCenterPage } from './pages/ModelCenterPage';
import { ReportsPage } from './pages/ReportsPage';
import { DeveloperPage } from './pages/DeveloperPage';

export const App: React.FC = () => {
  const [currentPolicy, setCurrentPolicy] = useState<string>('Balanced Policy (Default)');
  const [currentThreshold, setCurrentThreshold] = useState<number>(0.50);

  const handlePolicyChange = (name: string, threshold: number) => {
    setCurrentPolicy(name);
    setCurrentThreshold(threshold);
  };

  return (
    <AnalysisProvider>
      <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: '#090d16', color: '#f8fafc' }}>
        {/* Navigation Sidebar */}
        <Sidebar />

        {/* Main Content Area */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          {/* Top Operational Bar */}
          <Navbar
            currentPolicy={currentPolicy}
            onPolicyChange={handlePolicyChange}
          />

          {/* Router Pages */}
          <main style={{ flex: 1, padding: '1.75rem', maxWidth: '1440px', width: '100%', margin: '0 auto', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <ActiveRepoBar />
            <Routes>
              <Route path="/" element={<OverviewPage currentPolicy={currentPolicy} currentThreshold={currentThreshold} />} />
              <Route path="/queue" element={<QueuePage currentPolicy={currentPolicy} currentThreshold={currentThreshold} />} />
              <Route path="/analyze" element={<AnalysisPage currentPolicy={currentPolicy} currentThreshold={currentThreshold} />} />
              <Route path="/insights" element={<InsightsPage />} />
              <Route path="/reliability" element={<ReliabilityPage currentPolicy={currentPolicy} currentThreshold={currentThreshold} onSelectPolicy={handlePolicyChange} />} />
              <Route path="/model" element={<ModelCenterPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/developer" element={<DeveloperPage currentPolicy={currentPolicy} currentThreshold={currentThreshold} />} />
            </Routes>
          </main>
        </div>
      </div>
    </AnalysisProvider>
  );
};

export default App;
