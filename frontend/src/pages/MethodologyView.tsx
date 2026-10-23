import React from 'react';
import { Database, Clock, Scale, AlertOctagon, Cpu } from 'lucide-react';

export const MethodologyView: React.FC = () => {
  return (
    <div className="container" style={{ maxWidth: '960px' }}>
      <div className="page-header">
        <h1 className="page-title">Methodology, Market Context & Data Architecture</h1>
        <p className="page-subtitle">
          Operational principles and mathematical foundations supporting the day-ahead power trading desk
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* Section 1: Business Context */}
        <div className="chart-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <div className="brand-icon" style={{ width: 32, height: 32 }}>
              <Scale size={18} />
            </div>
            <h2 className="chart-title">1. Day-Ahead Wholesale Power Buying</h2>
          </div>
          <p style={{ color: '#cbd5e1', fontSize: 14, lineHeight: 1.7, marginBottom: 14 }}>
            In the UK electricity wholesale market, electricity suppliers must balance their consumers' expected demand with procured power. Day-ahead purchase decisions for delivery day <strong>D</strong> are legally committed on day <strong>D-1</strong> through day-ahead power exchanges (EPEX Spot UK and N2EX).
          </p>
          <p style={{ color: '#cbd5e1', fontSize: 14, lineHeight: 1.7 }}>
            Because wind power operates with near-zero marginal cost, it is dispatched first in the merit order. Trading desks must forecast how much wind will be generated so they know how much remaining power must be procured from thermal plants (e.g. CCGT) or wholesale auctions to satisfy demand.
          </p>
        </div>

        {/* Section 2: Decision Cutoff Logic */}
        <div className="chart-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <div className="brand-icon" style={{ width: 32, height: 32 }}>
              <Clock size={18} />
            </div>
            <h2 className="chart-title">2. Decision-Time Cutoff & Forecast Selection</h2>
          </div>
          <p style={{ color: '#cbd5e1', fontSize: 14, lineHeight: 1.7, marginBottom: 14 }}>
            Day-ahead power exchange gate closures occur between <strong>11:00 and 12:00</strong> London time on day D-1. Commercial trading desks therefore require an internal cut-off time (defaulted in this dashboard to <strong>09:00 London local time</strong>) to run optimization models, clear risk limits, and submit auction bid curves.
          </p>
          <div style={{ backgroundColor: 'var(--bg-page)', padding: 16, borderRadius: 8, border: '1px solid var(--border-card)', marginBottom: 14 }}>
            <div style={{ color: '#38bdf8', fontWeight: 600, fontSize: 13, marginBottom: 6 }}>Selection Formula:</div>
            <code style={{ color: '#f8fafc', fontSize: 13, fontFamily: 'var(--font-mono)' }}>
              Selected Forecast(t) = latest row with publishTime &le; (Target Date D - 1 day at Cutoff London Time, UTC converted)
            </code>
          </div>
          <p style={{ color: '#94a3b8', fontSize: 13, lineHeight: 1.6 }}>
            <strong>Integrity Guarantee:</strong> Forecasts published after the decision cutoff are strictly excluded from the decision forecast line, ensuring no retrospective foresight or look-ahead bias. Any half-hour without an eligible broadcast remains strictly <code>NaN</code> and is never artificially interpolated.
          </p>
        </div>

        {/* Section 3: Error Definition */}
        <div className="chart-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <div className="brand-icon" style={{ width: 32, height: 32 }}>
              <AlertOctagon size={18} />
            </div>
            <h2 className="chart-title">3. Error Definition & Commercial Risk Asymmetry</h2>
          </div>
          <div style={{ backgroundColor: 'var(--bg-page)', padding: 16, borderRadius: 8, border: '1px solid var(--border-card)', marginBottom: 16 }}>
            <code style={{ color: '#f59e0b', fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
              Forecast Error = Forecast Generation - Actual Generation
            </code>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginBottom: 14 }}>
            <div style={{ backgroundColor: '#2a1515', border: '1px solid #7f1d1d', padding: 16, borderRadius: 8 }}>
              <h3 style={{ color: '#f87171', fontSize: 14, fontWeight: 600, marginBottom: 6 }}>
                Positive Error (+) &rarr; Over-Forecast Risk
              </h3>
              <p style={{ color: '#fca5a5', fontSize: 13, lineHeight: 1.5 }}>
                The forecast promised more wind power than actually materialized. The buyer consequently under-buys market power, creating a short position that must be covered at high imbalance cashout prices (System Buy Price) or peak intraday prices.
              </p>
            </div>
            <div style={{ backgroundColor: '#0f2942', border: '1px solid #0369a1', padding: 16, borderRadius: 8 }}>
              <h3 style={{ color: '#38bdf8', fontSize: 14, fontWeight: 600, marginBottom: 6 }}>
                Negative Error (-) &rarr; Under-Forecast Buffer
              </h3>
              <p style={{ color: '#bae6fd', fontSize: 13, lineHeight: 1.5 }}>
                Actual wind generation exceeded expectations. The utility holds surplus generation (long position), which can be spilled or sold in balancing markets at prevailing System Sell Prices.
              </p>
            </div>
          </div>
        </div>

        {/* Section 4: Data Sources & Snapshot Architecture */}
        <div className="chart-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <div className="brand-icon" style={{ width: 32, height: 32 }}>
              <Database size={18} />
            </div>
            <h2 className="chart-title">4. Elexon BMRS Datasets & Precomputed Snapshots</h2>
          </div>
          <ul style={{ color: '#cbd5e1', fontSize: 14, lineHeight: 1.8, paddingLeft: 20, marginBottom: 16 }}>
            <li>
              <strong>FUELHH Stream:</strong> Half-hourly outturn generation by fuel type across Great Britain. Only records where <code>fuelType == "WIND"</code> are retained (1,488 half-hours across January 2026 delivery dates).
            </li>
            <li>
              <strong>WINDFOR Stream:</strong> National wind power forecasts published by the Electricity System Operator (ESO). Retains all revisions published between 2025-12-31 and 2026-01-31 with lead horizons between 0 and 48 hours.
            </li>
          </ul>
          <p style={{ color: '#94a3b8', fontSize: 13, lineHeight: 1.6 }}>
            <strong>Deployment Architecture:</strong> The application relies on deterministic, precomputed gzipped CSV snapshots (<code>data/actuals.csv.gz</code> and <code>data/forecasts.csv.gz</code>) loaded directly into memory at startup. The web service never calls external APIs at request time, ensuring zero external downtime risk and single-digit millisecond response latency.
          </p>
        </div>

        {/* Section 5: Limitations */}
        <div className="chart-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <div className="brand-icon" style={{ width: 32, height: 32 }}>
              <Cpu size={18} />
            </div>
            <h2 className="chart-title">5. Limitations & Future Development Roadmap</h2>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
            <div style={{ padding: 14, backgroundColor: 'var(--bg-page)', borderRadius: 8, border: '1px solid var(--border-card)' }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: '#f8fafc', marginBottom: 6 }}>National Scope Only</h3>
              <p style={{ fontSize: 13, color: '#94a3b8', lineHeight: 1.5 }}>
                Current data reflects aggregate national generation. Future versions will incorporate transmission boundary constraints (B6 Scottish export boundary) and BM unit-level wind park availability.
              </p>
            </div>
            <div style={{ padding: 14, backgroundColor: 'var(--bg-page)', borderRadius: 8, border: '1px solid var(--border-card)' }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: '#f8fafc', marginBottom: 6 }}>Demand & Price Coupling</h3>
              <p style={{ fontSize: 13, color: '#94a3b8', lineHeight: 1.5 }}>
                Integrating national demand forecasts (INDO/ITSDO) and day-ahead wholesale price feeds will allow calculating financial Value-at-Risk (&pound; cashout loss) in addition to volumetric MW exposure.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
