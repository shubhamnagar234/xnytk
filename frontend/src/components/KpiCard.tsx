import React from 'react';

interface KpiCardProps {
  title: string;
  value: number | string | null | undefined;
  unit?: string;
  subtitle?: string;
  highlight?: 'blue' | 'orange' | 'risk';
}

export const KpiCard: React.FC<KpiCardProps> = ({
  title,
  value,
  unit,
  subtitle,
  highlight,
}) => {
  let formattedValue = '—';
  if (typeof value === 'number') {
    formattedValue = value.toLocaleString('en-GB', {
      maximumFractionDigits: 1,
    });
  } else if (typeof value === 'string' && value.length > 0) {
    formattedValue = value;
  }

  const highlightClass = highlight
    ? `kpi-highlight-${highlight}`
    : '';

  return (
    <div className={`kpi-card ${highlightClass}`}>
      <div className="kpi-header">
        <span className="kpi-title">{title}</span>
      </div>
      <div className="kpi-value-row">
        <span className="kpi-value tabular-nums">{formattedValue}</span>
        {unit && <span className="kpi-unit">{unit}</span>}
      </div>
      {subtitle && <div className="kpi-subtitle">{subtitle}</div>}
    </div>
  );
};
