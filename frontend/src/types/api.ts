/**
 * TypeScript API model definitions matching FastAPI Pydantic schemas.
 */

export interface DataWindow {
  start: string;
  end: string;
}

export interface MetaResponse {
  delivery_days: string[];
  data_window: DataWindow;
  default_cutoff: string;
  timezone: string;
  decision_month: string;
  total_actual_rows: number;
  total_forecast_rows: number;
}

export interface HalfHourForecast {
  startTime: string;
  publishTime: string | null;
  forecast_mw: number | null;
  actual_mw: number | null;
  error: number | null;
  horizon_hours: number | null;
}

export interface DaySummary {
  forecast_mwh: number | null;
  actual_mwh: number | null;
  forecast_peak_mw: number | null;
  forecast_min_mw: number | null;
  actual_peak_mw: number | null;
  actual_min_mw: number | null;
  p90_error: number | null;
  mae: number | null;
  bias: number | null;
}

export interface DecisionForecastResponse {
  date: string;
  cutoff: string;
  summary: DaySummary;
  intervals: HalfHourForecast[];
}

export interface ForecastVintage {
  startTime: string;
  publishTime: string;
  forecast_mw: number;
  horizon_hours: number;
}

export interface VintagesResponse {
  date: string;
  count: number;
  vintages: ForecastVintage[];
}

export interface AccuracySummaryResponse {
  from_date: string;
  to_date: string;
  cutoff: string;
  n: number;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  p50: number | null;
  p90: number | null;
  p95: number | null;
  mae_pct_of_mean_actual: number | null;
  mean_actual: number | null;
}

export interface HorizonBucket {
  bucket: string;
  n: number;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  p90: number | null;
}

export interface AccuracyByHorizonResponse {
  from_date: string;
  to_date: string;
  buckets: HorizonBucket[];
}

export interface HourOfDayBreakdown {
  hour: number;
  n: number;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  p90: number | null;
  mean_actual: number | null;
}

export interface WindLevelBreakdown {
  level: string;
  min_mw: number;
  max_mw: number;
  n: number;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  p90: number | null;
}

export interface HistogramBin {
  bin_start: number;
  bin_end: number;
  bin_label: string;
  count: number;
}

export interface AccuracyBreakdownsResponse {
  from_date: string;
  to_date: string;
  cutoff: string;
  by_hour: HourOfDayBreakdown[];
  by_wind_level: WindLevelBreakdown[];
  histogram: HistogramBin[];
}
