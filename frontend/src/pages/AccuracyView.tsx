import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
  Line,
  ComposedChart,
} from 'recharts';
import { Calendar, Clock } from 'lucide-react';
import { api } from '../api/client';
import { KpiCard } from '../components/KpiCard';
import { InsightBanner } from '../components/InsightBanner';

export const AccuracyView: React.FC = () => {
  const { data: meta } = useQuery({
    queryKey: ['meta'],
    queryFn: api.getMeta,
  });

  const availableDays = meta?.delivery_days || [];
  const defaultFrom = availableDays[0] || '2026-01-02';
  const defaultTo = availableDays[availableDays.length - 1] || '2026-02-01';

  const [fromDate, setFromDate] = useState<string>('');
  const [toDate, setToDate] = useState<string>('');
  const [cutoff, setCutoff] = useState<string>('09:00');

  React.useEffect(() => {
    if (!fromDate && defaultFrom) setFromDate(defaultFrom);
    if (!toDate && defaultTo) setToDate(defaultTo);
  }, [defaultFrom, defaultTo, fromDate, toDate]);

  // 1. Fetch Summary Metrics
  const {
    data: summary,
    isLoading: summaryLoading,
  } = useQuery({
    queryKey: ['accuracy-summary', fromDate, toDate, cutoff],
    queryFn: () => api.getAccuracySummary(fromDate, toDate, cutoff),
    enabled: Boolean(fromDate && toDate),
  });

  // 2. Fetch Error by Horizon
  const {
    data: horizonData,
    isLoading: horizonLoading,
  } = useQuery({
    queryKey: ['accuracy-horizon', fromDate, toDate],
    queryFn: () => api.getAccuracyByHorizon(fromDate, toDate),
    enabled: Boolean(fromDate && toDate),
  });

  // 3. Fetch Breakdowns (Hour of day, wind levels, histogram)
  const {
    data: breakdowns,
    isLoading: breakdownsLoading,
  } = useQuery({
    queryKey: ['accuracy-breakdowns', fromDate, toDate, cutoff],
    queryFn: () => api.getAccuracyBreakdowns(fromDate, toDate, cutoff),
    enabled: Boolean(fromDate && toDate),
  });

  // Dynamic Insight Generator
  const horizonInsight = useMemo(() => {
    if (!horizonData?.buckets || horizonData.buckets.length < 2) {
      return 'Analyzing forecast horizon decay...';
    }
    const b0 = horizonData.buckets[0]; // 0-6h
    const bLast = horizonData.buckets[horizonData.buckets.length - 1]; // 36-48h

    const mae0 = b0.mae ?? 0;
    const maeLast = bLast.mae ?? 0;
    const p90Last = bLast.p90 ?? 0;

    return (
      `Forecast precision shows significant degradation with lead time: 0–6h intraday forecasts achieve an average MAE of ${Math.round(mae0).toLocaleString()} MW, ` +
      `whereas day-ahead 36–48h forecasts experience an MAE of ${Math.round(maeLast).toLocaleString()} MW with a P90 error reaching ${Math.round(p90Last).toLocaleString()} MW. ` +
      `Trading desks should hold a dynamic risk reserve buffer proportional to lead time.`
    );
  }, [horizonData]);

  const isLoading = summaryLoading || horizonLoading || breakdownsLoading;

  return (
    <div className="container">
      {/* Header and Controls */}
      <div className="page-header">
        <h1 className="page-title">Forecast Accuracy & Error Evaluation</h1>
        <p className="page-subtitle">
          Quantitative benchmarking across lead-time horizons, diurnal hours, and generation levels
        </p>

        <div className="controls-bar">
          <div className="control-group">
            <Calendar size={18} color="#0284c7" />
            <span className="control-label">From:</span>
            <select
              className="select-input tabular-nums"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
            >
              {availableDays.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>

            <span className="control-label">To:</span>
            <select
              className="select-input tabular-nums"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
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
            <span className="control-label">Cutoff:</span>
            <select
              className="select-input tabular-nums"
              value={cutoff}
              onChange={(e) => setCutoff(e.target.value)}
            >
              <option value="06:00">06:00 London</option>
              <option value="08:00">08:00 London</option>
              <option value="09:00">09:00 (Default)</option>
              <option value="10:00">10:00 London</option>
              <option value="11:00">11:00 London</option>
              <option value="12:00">12:00 London</option>
            </select>
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="state-container">
          <div className="spinner" />
          <p style={{ color: 'var(--text-secondary)' }}>Calculating multi-day accuracy metrics...</p>
        </div>
      )}

      {/* KPI Cards Row */}
      {summary && (
        <div className="kpi-grid">
          <KpiCard
            title="Mean Absolute Error (MAE)"
            value={summary.mae}
            unit="MW"
            subtitle={`${summary.mae_pct_of_mean_actual ?? '—'}% of mean actual wind`}
            highlight="orange"
          />
          <KpiCard
            title="Root Mean Sq Error (RMSE)"
            value={summary.rmse}
            unit="MW"
            subtitle="Penalizes large outlier forecast errors"
          />
          <KpiCard
            title="Mean Bias"
            value={summary.bias}
            unit="MW"
            subtitle={summary.bias && summary.bias > 0 ? 'Over-forecast bias (short risk)' : 'Under-forecast bias'}
            highlight="blue"
          />
          <KpiCard
            title="P90 Absolute Error"
            value={summary.p90}
            unit="MW"
            subtitle="90% of intervals error is within this"
            highlight="risk"
          />
          <KpiCard
            title="Evaluated Delivery Intervals"
            value={summary.n}
            subtitle={`${fromDate} to ${toDate}`}
          />
        </div>
      )}

      {/* Dynamic Lead-time Decay Insight */}
      <InsightBanner insight={horizonInsight} showRiskNote={true} />

      {/* Chart 1: Error by Horizon Bucket */}
      <div className="chart-card">
        <div className="chart-header">
          <div className="chart-title-group">
            <h2 className="chart-title">Forecast Error by Lead-Time Horizon Bucket</h2>
            <span className="chart-caption">
              Evaluated over ALL historical forecast vintages (MAE and P90 error in MW)
            </span>
          </div>
          <div className="chart-legend">
            <div className="legend-item">
              <span className="legend-color-dot" style={{ backgroundColor: '#0284c7' }} />
              <span>MAE (MW)</span>
            </div>
            <div className="legend-item">
              <span className="legend-color-dot" style={{ backgroundColor: '#ea580c' }} />
              <span>P90 Error (MW)</span>
            </div>
          </div>
        </div>

        <div className="chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={horizonData?.buckets || []} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.6} />
              <XAxis
                dataKey="bucket"
                stroke="#94a3b8"
                tick={{ fontSize: 13, fill: '#94a3b8' }}
                label={{ value: 'Forecast Horizon Bucket (Hours before delivery)', position: 'insideBottom', offset: -12, fill: '#94a3b8', fontSize: 12 }}
              />
              <YAxis
                stroke="#94a3b8"
                tick={{ fontSize: 12, fill: '#94a3b8' }}
                unit=" MW"
                label={{ value: 'Error (MW)', angle: -90, position: 'insideLeft', offset: 0, fill: '#94a3b8', fontSize: 12 }}
              />
              <Tooltip content={<CustomGenericTooltip />} />
              <Bar dataKey="mae" fill="#0284c7" name="MAE (MW)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="p90" fill="#ea580c" name="P90 Error (MW)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Chart 2: Diurnal Error by Hour of Day */}
      <div className="chart-card">
        <div className="chart-header">
          <div className="chart-title-group">
            <h2 className="chart-title">Diurnal Forecast Accuracy: Error by Hour of Day</h2>
            <span className="chart-caption">
              Average MAE and Mean Actual generation per hour in London local time (00:00 to 23:00)
            </span>
          </div>
        </div>

        <div className="chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={breakdowns?.by_hour || []} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.6} />
              <XAxis
                dataKey="hour"
                stroke="#94a3b8"
                tick={{ fontSize: 12, fill: '#94a3b8' }}
                tickFormatter={(h) => `${h}:00`}
                label={{ value: 'Hour of Day (London Local)', position: 'insideBottom', offset: -12, fill: '#94a3b8', fontSize: 12 }}
              />
              <YAxis
                stroke="#94a3b8"
                tick={{ fontSize: 12, fill: '#94a3b8' }}
                unit=" MW"
                label={{ value: 'Power (MW)', angle: -90, position: 'insideLeft', offset: 0, fill: '#94a3b8', fontSize: 12 }}
              />
              <Tooltip content={<CustomGenericTooltip />} />
              <Bar dataKey="mae" fill="#d97706" name="MAE (MW)" radius={[4, 4, 0, 0]} />
              <Line type="monotone" dataKey="mean_actual" stroke="#0284c7" strokeWidth={2} dot={false} name="Mean Actual (MW)" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Split Row: Error Histogram & Error by Wind Output Level */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))', gap: 24 }}>
        {/* Chart 3: Error Histogram */}
        <div className="chart-card">
          <div className="chart-header">
            <div className="chart-title-group">
              <h2 className="chart-title">Forecast Error Distribution (Histogram)</h2>
              <span className="chart-caption">
                Spread of (Forecast - Actual). Bins right of 0 represent over-forecast risk.
              </span>
            </div>
          </div>

          <div style={{ width: '100%', height: 320 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={breakdowns?.histogram || []} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.6} />
                <XAxis
                  dataKey="bin_label"
                  stroke="#94a3b8"
                  tick={{ fontSize: 10, fill: '#94a3b8' }}
                  angle={-25}
                  textAnchor="end"
                  height={50}
                />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 12, fill: '#94a3b8' }} unit=" HH" />
                <Tooltip content={<CustomGenericTooltip />} />
                <Bar dataKey="count" name="Half-Hours" radius={[4, 4, 0, 0]}>
                  {breakdowns?.histogram.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.bin_end <= 0 ? '#0284c7' : '#ea580c'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 4: Error by Actual Level Terciles */}
        <div className="chart-card">
          <div className="chart-header">
            <div className="chart-title-group">
              <h2 className="chart-title">Error Scaling by Wind Generation Tercile</h2>
              <span className="chart-caption">
                MAE and P90 error partitioned by actual wind generation level
              </span>
            </div>
          </div>

          <div style={{ width: '100%', height: 320 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={breakdowns?.by_wind_level || []} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.6} />
                <XAxis dataKey="level" stroke="#94a3b8" tick={{ fontSize: 13, fill: '#94a3b8' }} />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 12, fill: '#94a3b8' }} unit=" MW" />
                <Tooltip content={<CustomGenericTooltip />} />
                <Bar dataKey="mae" fill="#0284c7" name="MAE (MW)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="p90" fill="#ea580c" name="P90 Error (MW)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};

// Generic Custom Recharts Tooltip
const CustomGenericTooltip: React.FC<any> = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;

  return (
    <div className="custom-tooltip">
      <div className="tooltip-time">{label}</div>
      {payload.map((item: any) => (
        <div key={item.dataKey} className="tooltip-row" style={{ color: item.color || '#38bdf8' }}>
          <span>{item.name}:</span>
          <strong className="tabular-nums">
            {typeof item.value === 'number' ? item.value.toLocaleString() : item.value}
          </strong>
        </div>
      ))}
    </div>
  );
};
