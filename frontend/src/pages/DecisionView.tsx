import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import { Calendar, Clock, Layers, ArrowUpRight, ArrowDownRight, RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import { KpiCard } from '../components/KpiCard';
import { InsightBanner } from '../components/InsightBanner';
import { HalfHourForecast } from '../types/api';

const CUTOFF_OPTIONS = [
  { value: '06:00', label: '06:00 (Early Morning)' },
  { value: '08:00', label: '08:00 (Pre-auction)' },
  { value: '09:00', label: '09:00 (Default Gate Closure)' },
  { value: '10:00', label: '10:00 (Post-auction run)' },
  { value: '11:00', label: '11:00 (Mid-day)' },
  { value: '12:00', label: '12:00 (EPEX Day-Ahead Closure)' },
];

export const DecisionView: React.FC = () => {
  // 1. Fetch metadata to get available days and default cutoff
  const { data: meta, isLoading: metaLoading } = useQuery({
    queryKey: ['meta'],
    queryFn: api.getMeta,
  });

  const availableDays = meta?.delivery_days || [];
  const defaultDay = availableDays.length > 13 ? availableDays[13] : availableDays[0] || '2026-01-15';

  const [selectedDate, setSelectedDate] = useState<string>('');
  const [selectedCutoff, setSelectedCutoff] = useState<string>('09:00');
  const [showVintages, setShowVintages] = useState<boolean>(false);
  const [showTable, setShowTable] = useState<boolean>(false);

  // Set initial selected date once meta loads
  React.useEffect(() => {
    if (!selectedDate && defaultDay) {
      setSelectedDate(defaultDay);
    }
  }, [defaultDay, selectedDate]);

  // 2. Fetch decision-time forecast for the selected day and cutoff
  const {
    data: decisionData,
    isLoading: decisionLoading,
    error: decisionError,
  } = useQuery({
    queryKey: ['decision', selectedDate, selectedCutoff],
    queryFn: () => api.getDecisionForecast(selectedDate, selectedCutoff),
    enabled: Boolean(selectedDate),
  });

  // 3. Fetch earlier vintages if toggle is active
  const { data: vintagesData, isLoading: vintagesLoading } = useQuery({
    queryKey: ['vintages', selectedDate],
    queryFn: () => api.getVintages(selectedDate),
    enabled: Boolean(selectedDate && showVintages),
  });

  // 4. Fetch month-wide accuracy to contextualize P90 risk buffer
  const { data: accuracyData } = useQuery({
    queryKey: ['accuracy-summary-month', selectedCutoff],
    queryFn: () => api.getAccuracySummary(undefined, undefined, selectedCutoff),
  });

  // Prepare chart series data
  const chartData = useMemo(() => {
    if (!decisionData?.intervals) return [];

    // Group vintages by distinct publishTime if toggle is on
    const vintagePublishTimes = vintagesData?.vintages
      ? Array.from(new Set(vintagesData.vintages.map((v) => v.publishTime))).sort()
      : [];

    return decisionData.intervals.map((interval: HalfHourForecast) => {
      // Format London time label (e.g. "14:00")
      const dt = new Date(interval.startTime);
      const timeLabel = dt.toLocaleTimeString('en-GB', {
        timeZone: 'Europe/London',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });

      const point: Record<string, any> = {
        startTime: interval.startTime,
        timeLabel,
        actual_mw: interval.actual_mw,
        forecast_mw: interval.forecast_mw,
        error: interval.error,
        horizon_hours: interval.horizon_hours,
        publishTime: interval.publishTime,
      };

      // Add vintages values
      if (showVintages && vintagesData?.vintages) {
        for (const pt of vintagePublishTimes) {
          const match = vintagesData.vintages.find(
            (v) => v.startTime === interval.startTime && v.publishTime === pt
          );
          if (match) {
            point[`vintage_${pt}`] = match.forecast_mw;
          }
        }
      }

      return point;
    });
  }, [decisionData, vintagesData, showVintages]);

  // Dynamic plain-English insight generator
  const insightText = useMemo(() => {
    if (!decisionData?.summary) return 'Loading forecast analysis...';
    const s = decisionData.summary;
    const peakAct = s.actual_peak_mw ?? 0;
    const peakFc = s.forecast_peak_mw ?? 0;
    const bias = s.bias ?? 0;
    const mae = s.mae ?? 0;

    let narrative = `On ${selectedDate}, delivery actuals peaked at ${peakAct.toLocaleString('en-GB')} MW (forecast peak was ${peakFc.toLocaleString('en-GB')} MW). `;
    if (bias > 100) {
      narrative += `At the ${selectedCutoff} D-1 cutoff, the forecast was on average ${Math.round(bias).toLocaleString('en-GB')} MW above actual generation (over-forecast bias), meaning the desk was exposed to under-procurement cashout risk.`;
    } else if (bias < -100) {
      narrative += `At the ${selectedCutoff} D-1 cutoff, the forecast was on average ${Math.abs(Math.round(bias)).toLocaleString('en-GB')} MW below actuals (under-forecast), providing a safety generation buffer.`;
    } else {
      narrative += `The forecast closely tracked actual generation with a low net bias of ${Math.round(bias)} MW and an average absolute deviation of ${Math.round(mae)} MW.`;
    }
    return narrative;
  }, [decisionData, selectedDate, selectedCutoff]);

  const p90Risk = accuracyData?.p90 ?? decisionData?.summary?.p90_error ?? 0;

  if (metaLoading || (!selectedDate && decisionLoading)) {
    return (
      <div className="container">
        <div className="state-container">
          <div className="spinner" />
          <p style={{ color: 'var(--text-secondary)' }}>Loading trading environment metadata...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      {/* Header and Controls */}
      <div className="page-header">
        <h1 className="page-title">Day-Ahead Power Purchase Decision Desk</h1>
        <p className="page-subtitle">
          National wind generation forecast available at decision cutoff vs actual delivery
        </p>

        <div className="controls-bar">
          <div className="control-group">
            <Calendar size={18} color="#0284c7" />
            <span className="control-label">Delivery Day (D):</span>
            <select
              className="select-input tabular-nums"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
            >
              {availableDays.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>

          <div className="control-group">
            <Clock size={18} color="#d97706" />
            <span className="control-label">Decision Cutoff (D-1):</span>
            <select
              className="select-input tabular-nums"
              value={selectedCutoff}
              onChange={(e) => setSelectedCutoff(e.target.value)}
            >
              {CUTOFF_OPTIONS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          <div className="control-group">
            <div
              className="toggle-wrapper"
              onClick={() => setShowVintages(!showVintages)}
              title="Overlay previous forecast updates"
            >
              <div className={`toggle-switch ${showVintages ? 'active' : ''}`}>
                <div className="toggle-knob" />
              </div>
              <span className="control-label" style={{ cursor: 'pointer' }}>
                <Layers size={14} style={{ display: 'inline', marginRight: 4 }} />
                Overlay Vintages {vintagesLoading && <RefreshCw size={12} className="spinner" />}
              </span>
            </div>
          </div>
        </div>
      </div>

      {decisionError && (
        <div className="state-container" style={{ borderColor: '#ef4444' }}>
          <p style={{ color: '#f87171' }}>Error loading decision forecast: {(decisionError as Error).message}</p>
        </div>
      )}

      {/* KPI Cards */}
      <div className="kpi-grid">
        <KpiCard
          title="Forecast Energy (Day D)"
          value={decisionData?.summary?.forecast_mwh}
          unit="MWh"
          subtitle={`At ${selectedCutoff} D-1 cutoff`}
          highlight="orange"
        />
        <KpiCard
          title="Actual Delivered Energy"
          value={decisionData?.summary?.actual_mwh}
          unit="MWh"
          subtitle="Total wind generation delivered"
          highlight="blue"
        />
        <KpiCard
          title="Forecast Peak Output"
          value={decisionData?.summary?.forecast_peak_mw}
          unit="MW"
          subtitle={`Forecast min: ${decisionData?.summary?.forecast_min_mw?.toLocaleString() ?? '—'} MW`}
        />
        <KpiCard
          title="Actual Peak Output"
          value={decisionData?.summary?.actual_peak_mw}
          unit="MW"
          subtitle={`Actual min: ${decisionData?.summary?.actual_min_mw?.toLocaleString() ?? '—'} MW`}
        />
        <KpiCard
          title="P90 Risk Buffer"
          value={p90Risk}
          unit="MW"
          subtitle="Recommended reserve procurement"
          highlight="risk"
        />
      </div>

      {/* Insight Line */}
      <InsightBanner insight={insightText} showRiskNote={true} />

      {/* Main Line Chart */}
      <div className="chart-card">
        <div className="chart-header">
          <div className="chart-title-group">
            <h2 className="chart-title">Wind Generation: Actual vs Decision Forecast</h2>
            <span className="chart-caption">
              30-minute delivery periods for {selectedDate} (London Local Time) • Decision cutoff at {selectedCutoff} D-1
            </span>
          </div>

          <div className="chart-legend">
            <div className="legend-item">
              <span className="legend-color-dot" style={{ backgroundColor: 'var(--color-actual)' }} />
              <span>Actual Wind (MW)</span>
            </div>
            <div className="legend-item">
              <span className="legend-color-dot" style={{ backgroundColor: 'var(--color-forecast)' }} />
              <span>Decision Forecast (MW)</span>
            </div>
            {showVintages && (
              <div className="legend-item">
                <span className="legend-color-dot" style={{ backgroundColor: 'var(--color-vintage)' }} />
                <span>Earlier Vintages</span>
              </div>
            )}
          </div>
        </div>

        <div className="chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.6} />
              <XAxis
                dataKey="timeLabel"
                stroke="#94a3b8"
                tick={{ fontSize: 12, fill: '#94a3b8' }}
                interval={3}
                label={{ value: 'London Time (HH:MM)', position: 'insideBottom', offset: -12, fill: '#94a3b8', fontSize: 12 }}
              />
              <YAxis
                stroke="#94a3b8"
                tick={{ fontSize: 12, fill: '#94a3b8' }}
                unit=" MW"
                domain={['auto', 'auto']}
                label={{ value: 'Generation (MW)', angle: -90, position: 'insideLeft', offset: 0, fill: '#94a3b8', fontSize: 12 }}
              />
              <Tooltip content={<CustomDecisionTooltip />} />

              {/* Faint lines for earlier vintages */}
              {showVintages &&
                vintagesData?.vintages &&
                Array.from(new Set(vintagesData.vintages.map((v) => v.publishTime))).map((pt) => (
                  <Line
                    key={pt}
                    type="monotone"
                    dataKey={`vintage_${pt}`}
                    stroke="#64748b"
                    strokeWidth={1}
                    strokeDasharray="2 2"
                    opacity={0.35}
                    dot={false}
                    name={`Published ${pt.slice(11, 16)}Z`}
                    isAnimationActive={false}
                  />
                ))}

              {/* Primary Decision Forecast (Amber) */}
              <Line
                type="monotone"
                dataKey="forecast_mw"
                stroke="var(--color-forecast)"
                strokeWidth={2.5}
                dot={{ r: 3, fill: 'var(--color-forecast)' }}
                activeDot={{ r: 6 }}
                name="Decision Forecast"
              />

              {/* Primary Actual Delivery (Blue) */}
              <Line
                type="monotone"
                dataKey="actual_mw"
                stroke="var(--color-actual)"
                strokeWidth={2.5}
                dot={false}
                activeDot={{ r: 6 }}
                name="Delivered Actual"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Interval Details Toggle & Table */}
      <div style={{ marginTop: 20 }}>
        <button
          onClick={() => setShowTable(!showTable)}
          style={{
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-card)',
            color: 'var(--text-main)',
            padding: '10px 18px',
            borderRadius: 'var(--radius-sm)',
            cursor: 'pointer',
            fontSize: 13,
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          {showTable ? 'Hide Half-Hourly Table' : 'Show Half-Hourly Data & Imbalance Table'}
        </button>

        {showTable && decisionData?.intervals && (
          <div className="data-table-container">
            <table className="data-table tabular-nums">
              <thead>
                <tr>
                  <th>Period</th>
                  <th>London Time</th>
                  <th>Forecast (MW)</th>
                  <th>Actual (MW)</th>
                  <th>Error (Forecast - Actual)</th>
                  <th>Lead Horizon</th>
                  <th>Published (UTC)</th>
                  <th>Trading Imbalance Position</th>
                </tr>
              </thead>
              <tbody>
                {decisionData.intervals.map((row, idx) => {
                  const dt = new Date(row.startTime);
                  const timeStr = dt.toLocaleTimeString('en-GB', {
                    timeZone: 'Europe/London',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false,
                  });
                  const err = row.error;
                  const isOverForecast = err !== null && err > 0;
                  const isUnderForecast = err !== null && err < 0;

                  return (
                    <tr key={row.startTime}>
                      <td>SP {idx + 1}</td>
                      <td>{timeStr}</td>
                      <td style={{ color: 'var(--color-forecast)', fontWeight: 600 }}>
                        {row.forecast_mw !== null ? `${row.forecast_mw.toLocaleString()} MW` : '—'}
                      </td>
                      <td style={{ color: 'var(--color-actual)', fontWeight: 600 }}>
                        {row.actual_mw !== null ? `${row.actual_mw.toLocaleString()} MW` : '—'}
                      </td>
                      <td style={{ color: isOverForecast ? '#ea580c' : isUnderForecast ? '#38bdf8' : 'inherit' }}>
                        {err !== null ? (
                          <span>
                            {err > 0 ? `+${err.toLocaleString()}` : err.toLocaleString()} MW
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td>{row.horizon_hours !== null ? `${row.horizon_hours} h` : '—'}</td>
                      <td style={{ fontSize: 11, color: '#94a3b8' }}>
                        {row.publishTime ? row.publishTime.replace('T', ' ').slice(0, 16) + 'Z' : '—'}
                      </td>
                      <td>
                        {isOverForecast ? (
                          <span style={{ color: '#ea580c', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                            <ArrowUpRight size={14} /> Short (Under-procured)
                          </span>
                        ) : isUnderForecast ? (
                          <span style={{ color: '#38bdf8', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                            <ArrowDownRight size={14} /> Long (Surplus)
                          </span>
                        ) : (
                          <span style={{ color: '#94a3b8', fontSize: 12 }}>Balanced</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

// Custom Recharts Tooltip with London Local Time and Error Explanation
const CustomDecisionTooltip: React.FC<any> = ({ active, payload }) => {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0].payload;
  const err = data.error;

  return (
    <div className="custom-tooltip">
      <div className="tooltip-time">
        {data.timeLabel} London Local ({new Date(data.startTime).toISOString().slice(0, 10)})
      </div>
      <div className="tooltip-row" style={{ color: 'var(--color-actual)' }}>
        <span>Actual Wind:</span>
        <strong className="tabular-nums">
          {data.actual_mw !== null && data.actual_mw !== undefined ? `${data.actual_mw.toLocaleString()} MW` : '—'}
        </strong>
      </div>
      <div className="tooltip-row" style={{ color: 'var(--color-forecast)' }}>
        <span>Decision Forecast:</span>
        <strong className="tabular-nums">
          {data.forecast_mw !== null && data.forecast_mw !== undefined ? `${data.forecast_mw.toLocaleString()} MW` : '—'}
        </strong>
      </div>
      {err !== null && err !== undefined && (
        <div
          className="tooltip-row"
          style={{
            borderTop: '1px solid #334155',
            paddingTop: 4,
            marginTop: 4,
            color: err > 0 ? '#ea580c' : '#38bdf8',
          }}
        >
          <span>Error (Forecast - Actual):</span>
          <strong className="tabular-nums">
            {err > 0 ? `+${err.toLocaleString()}` : err.toLocaleString()} MW
          </strong>
        </div>
      )}
      {data.horizon_hours !== null && data.horizon_hours !== undefined && (
        <div className="tooltip-row" style={{ fontSize: 11, color: '#94a3b8' }}>
          <span>Lead Time:</span>
          <span>{data.horizon_hours} h</span>
        </div>
      )}
      {err > 0 && (
        <div style={{ fontSize: 11, color: '#fca5a5', marginTop: 4 }}>
          ⚠️ Over-forecast: buy buffer needed to cover shortfall
        </div>
      )}
    </div>
  );
};
