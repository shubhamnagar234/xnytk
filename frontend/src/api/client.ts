/**
 * Typed HTTP API client for the UK Wind Forecast Dashboard.
 */

import {
  AccuracyBreakdownsResponse,
  AccuracyByHorizonResponse,
  AccuracySummaryResponse,
  DecisionForecastResponse,
  MetaResponse,
  VintagesResponse,
} from '../types/api';

const API_BASE = '/api';

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) {
        errorDetail = errJson.detail;
      }
    } catch {
      // Keep default error detail if body is not JSON
    }
    throw new Error(errorDetail);
  }
  return response.json();
}

export const api = {
  getMeta: (): Promise<MetaResponse> => {
    return fetchJson<MetaResponse>(`${API_BASE}/meta`);
  },

  getDecisionForecast: (date: string, cutoff: string = '09:00'): Promise<DecisionForecastResponse> => {
    const params = new URLSearchParams({ date, cutoff });
    return fetchJson<DecisionForecastResponse>(`${API_BASE}/forecast/decision?${params.toString()}`);
  },

  getVintages: (date: string): Promise<VintagesResponse> => {
    const params = new URLSearchParams({ date });
    return fetchJson<VintagesResponse>(`${API_BASE}/forecast/vintages?${params.toString()}`);
  },

  getAccuracySummary: (
    fromDate?: string,
    toDate?: string,
    cutoff: string = '09:00',
  ): Promise<AccuracySummaryResponse> => {
    const params = new URLSearchParams();
    if (fromDate) params.append('from', fromDate);
    if (toDate) params.append('to', toDate);
    params.append('cutoff', cutoff);
    return fetchJson<AccuracySummaryResponse>(`${API_BASE}/accuracy/summary?${params.toString()}`);
  },

  getAccuracyByHorizon: (fromDate?: string, toDate?: string): Promise<AccuracyByHorizonResponse> => {
    const params = new URLSearchParams();
    if (fromDate) params.append('from', fromDate);
    if (toDate) params.append('to', toDate);
    return fetchJson<AccuracyByHorizonResponse>(`${API_BASE}/accuracy/by-horizon?${params.toString()}`);
  },

  getAccuracyBreakdowns: (
    fromDate?: string,
    toDate?: string,
    cutoff: string = '09:00',
  ): Promise<AccuracyBreakdownsResponse> => {
    const params = new URLSearchParams();
    if (fromDate) params.append('from', fromDate);
    if (toDate) params.append('to', toDate);
    params.append('cutoff', cutoff);
    return fetchJson<AccuracyBreakdownsResponse>(`${API_BASE}/accuracy/breakdowns?${params.toString()}`);
  },
};
