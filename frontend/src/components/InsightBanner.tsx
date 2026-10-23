import React from 'react';
import { Lightbulb, AlertTriangle } from 'lucide-react';

interface InsightBannerProps {
  insight: string;
  showRiskNote?: boolean;
}

export const InsightBanner: React.FC<InsightBannerProps> = ({
  insight,
  showRiskNote = true,
}) => {
  return (
    <div>
      <div className="insight-banner">
        <Lightbulb size={20} className="insight-icon" />
        <div className="insight-content">
          <strong>Trading Insight:</strong> {insight}
        </div>
      </div>

      {showRiskNote && (
        <div className="risk-callout">
          <AlertTriangle size={16} style={{ flexShrink: 0 }} />
          <span>
            <strong>Desk Risk Notice:</strong> Error is defined as{' '}
            <code>Forecast - Actual</code>. A <strong>positive error</strong> represents an{' '}
            <strong>over-forecast</strong> (the forecast promised more wind than delivered), leaving the buyer short of power and exposed to under-procurement cashout penalties.
          </span>
        </div>
      )}
    </div>
  );
};
