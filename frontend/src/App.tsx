import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Navbar } from './components/Navbar';
import { DecisionView } from './pages/DecisionView';
import { AccuracyView } from './pages/AccuracyView';
import { MethodologyView } from './pages/MethodologyView';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 15, // 15 minutes in-memory cache
      retry: 1,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
          <Navbar />
          <main style={{ flex: 1 }}>
            <Routes>
              <Route path="/" element={<DecisionView />} />
              <Route path="/accuracy" element={<AccuracyView />} />
              <Route path="/methodology" element={<MethodologyView />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
          <footer
            style={{
              borderTop: '1px solid var(--border-card)',
              padding: '24px 20px',
              textAlign: 'center',
              fontSize: '12px',
              color: 'var(--text-tertiary)',
              backgroundColor: '#0b0f19',
            }}
          >
            UK Wind Forecast Decision Support • Elexon BMRS Ingestion • January 2026 Procurement Window
          </footer>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;
