import React, { useEffect, useState } from 'react';

interface HealthResponse {
  status: string;
  service: string;
  timestamp: string;
}

export const App: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/health')
      .then((res) => {
        if (!res.ok) {
          throw new Error(`Health check failed with status: ${res.status}`);
        }
        return res.json();
      })
      .then((data: HealthResponse) => {
        setHealth(data);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <div style={{ maxWidth: '800px', margin: '60px auto', padding: '0 24px' }}>
      <header style={{ marginBottom: '32px', borderBottom: '1px solid #e2e8f0', paddingBottom: '20px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: '700', color: '#0f172a' }}>
          UK Wind Forecast Dashboard
        </h1>
        <p style={{ color: '#64748b', marginTop: '6px', fontSize: '15px' }}>
          Day-ahead purchase decision support and forecast accuracy evaluation
        </p>
      </header>

      <main>
        <section
          style={{
            background: '#ffffff',
            borderRadius: '12px',
            border: '1px solid #e2e8f0',
            padding: '28px',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: '600', color: '#1e293b' }}>
              Phase 1: Environment & API Health Check
            </h2>
            <span
              style={{
                fontSize: '12px',
                fontWeight: '600',
                padding: '4px 10px',
                borderRadius: '9999px',
                backgroundColor: loading ? '#fef3c7' : error ? '#fee2e2' : '#dcfce7',
                color: loading ? '#92400e' : error ? '#991b1b' : '#166534',
              }}
            >
              {loading ? 'Checking...' : error ? 'Error' : 'Operational'}
            </span>
          </div>

          <p style={{ color: '#475569', fontSize: '14px', marginBottom: '20px' }}>
            Testing communication between Vite frontend and FastAPI backend proxy (<code>/api/health</code>).
          </p>

          {loading && (
            <div style={{ padding: '20px', textAlign: 'center', color: '#64748b' }}>
              Connecting to backend service...
            </div>
          )}

          {error && (
            <div
              style={{
                backgroundColor: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: '8px',
                padding: '16px',
                color: '#b91c1c',
                fontSize: '14px',
              }}
            >
              <strong>Connection Error:</strong> {error}
            </div>
          )}

          {health && (
            <div
              style={{
                backgroundColor: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
                padding: '20px',
              }}
            >
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                <tbody>
                  <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '8px 0', color: '#64748b', fontWeight: '500' }}>Status:</td>
                    <td style={{ padding: '8px 0', color: '#0f172a', fontWeight: '600' }}>{health.status}</td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '8px 0', color: '#64748b', fontWeight: '500' }}>Service:</td>
                    <td style={{ padding: '8px 0', color: '#0f172a' }}>{health.service}</td>
                  </tr>
                  <tr>
                    <td style={{ padding: '8px 0', color: '#64748b', fontWeight: '500' }}>Timestamp (UTC):</td>
                    <td style={{ padding: '8px 0', color: '#0f172a', fontFamily: 'monospace' }}>
                      {health.timestamp}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  );
};

export default App;
