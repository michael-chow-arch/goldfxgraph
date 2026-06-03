import type {
  DailyBar,
  ForecastHistoryItem,
  FinalForecast,
  SchedulerRunStatus,
} from "@/types/forecast";
import {
  TRADINGVIEW_SOURCE_ERROR_LABEL,
  TRADINGVIEW_SOURCE_UNAVAILABLE_LABEL,
} from "@/constants/forecast";

const CONFIG_ERROR_MESSAGE = "前端配置错误：VITE_API_BASE_URL 无效，无法连接 GoldFXGraph backend。";
const NETWORK_FORECAST_ERROR_MESSAGE = "网络连接失败，暂时无法获取 TradingView 最新研究结果。";
const NETWORK_HISTORY_ERROR_MESSAGE = "网络连接失败，暂时无法获取历史研究结果。";
const NETWORK_MARKET_BARS_ERROR_MESSAGE = "网络连接失败，暂时无法获取 TradingView 实时行情日线。";
const DEFAULT_API_BASE_URL = "http://localhost:8000";

interface ApiErrorEnvelope {
  error?: {
    type?: string;
    message?: string;
  };
}

function sanitizeRuntimeMessage(message: string): string {
  return message.replace(/api\.gold-api\.com/gi, "TradingView").replace(/gold api/gi, "TradingView");
}

function formatRuntimeErrorMessage(
  fallbackMessage: string,
  payload: ApiErrorEnvelope | null,
  response: Response,
  includeTradingViewPrefix: boolean,
): string {
  const errorType = payload?.error?.type?.trim().toLowerCase();
  const responseMessage = sanitizeRuntimeMessage(
    payload?.error?.message?.trim() || response.statusText.trim() || fallbackMessage,
  );

  if (
    includeTradingViewPrefix &&
    (errorType?.includes("quote_provider") || errorType?.includes("market_data") || errorType?.includes("unavailable"))
  ) {
    return `${TRADINGVIEW_SOURCE_UNAVAILABLE_LABEL}，${responseMessage}`;
  }

  if (includeTradingViewPrefix && errorType?.includes("error")) {
    return `${TRADINGVIEW_SOURCE_ERROR_LABEL}，${responseMessage}`;
  }

  return responseMessage;
}

export function resolveApiBaseUrl(baseUrl?: string | null): string {
  const normalizedBaseUrl = baseUrl?.trim();
  if (!normalizedBaseUrl) {
    return DEFAULT_API_BASE_URL;
  }

  let parsedUrl: URL;

  try {
    parsedUrl = new URL(normalizedBaseUrl);
  } catch {
    throw new Error(CONFIG_ERROR_MESSAGE);
  }

  if (!["http:", "https:"].includes(parsedUrl.protocol)) {
    throw new Error(CONFIG_ERROR_MESSAGE);
  }

  return parsedUrl.toString().replace(/\/$/, "");
}

function apiBaseUrl(): string {
  return resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL);
}

function buildUrl(path: string): string {
  return `${apiBaseUrl()}${path}`;
}

export async function fetchLatestForecast(): Promise<FinalForecast | null> {
  let response: Response;

  try {
    response = await fetch(buildUrl("/api/v1/forecast/latest"), {
      headers: {
        Accept: "application/json",
      },
    });
  } catch (error) {
    if (error instanceof Error && error.message === CONFIG_ERROR_MESSAGE) {
      throw error;
    }

    throw new Error(NETWORK_FORECAST_ERROR_MESSAGE);
  }

  if (response.status === 404 || response.status === 204) {
    return null;
  }

  if (!response.ok) {
    let message = "无法加载最新 TradingView 研究结果";
    let payload: ApiErrorEnvelope | null = null;

    try {
      payload = (await response.json()) as ApiErrorEnvelope;
    } catch {
      payload = null;
    }

    throw new Error(formatRuntimeErrorMessage(message, payload, response, true));
  }

  const bodyText = await response.text();
  if (!bodyText.trim()) {
    return null;
  }

  return JSON.parse(bodyText) as FinalForecast;
}

export async function fetchForecastHistory(limit = 30): Promise<ForecastHistoryItem[]> {
  let response: Response;

  try {
    response = await fetch(buildUrl(`/api/v1/forecast/history?limit=${encodeURIComponent(String(limit))}`), {
      headers: {
        Accept: "application/json",
      },
    });
  } catch (error) {
    if (error instanceof Error && error.message === CONFIG_ERROR_MESSAGE) {
      throw error;
    }

    throw new Error(NETWORK_HISTORY_ERROR_MESSAGE);
  }

  if (!response.ok) {
    let message = "无法加载历史研究结果";
    let payload: ApiErrorEnvelope | null = null;

    try {
      payload = (await response.json()) as ApiErrorEnvelope;
    } catch {
      payload = null;
    }

    throw new Error(formatRuntimeErrorMessage(message, payload, response, false));
  }

  const bodyText = await response.text();
  if (!bodyText.trim()) {
    return [];
  }

  return JSON.parse(bodyText) as ForecastHistoryItem[];
}

export async function fetchLatestSchedulerStatus(): Promise<SchedulerRunStatus | null> {
  let response: Response;

  try {
    response = await fetch(buildUrl("/api/v1/research-status/latest"), {
      headers: {
        Accept: "application/json",
      },
    });
  } catch (error) {
    if (error instanceof Error && error.message === CONFIG_ERROR_MESSAGE) {
      throw error;
    }

    throw new Error("网络连接失败，暂时无法获取最新调度状态。");
  }

  if (response.status === 404 || response.status === 204) {
    return null;
  }

  if (!response.ok) {
    let message = "无法加载最新调度状态";
    let payload: ApiErrorEnvelope | null = null;

    try {
      payload = (await response.json()) as ApiErrorEnvelope;
    } catch {
      payload = null;
    }

    throw new Error(formatRuntimeErrorMessage(message, payload, response, false));
  }

  const bodyText = await response.text();
  if (!bodyText.trim()) {
    return null;
  }

  return JSON.parse(bodyText) as SchedulerRunStatus;
}

export async function fetchRecentMarketBars(symbol = "XAUUSD", limit = 60): Promise<DailyBar[]> {
  let response: Response;

  try {
    response = await fetch(
      buildUrl(`/api/v1/market-data/bars?symbol=${encodeURIComponent(symbol)}&limit=${encodeURIComponent(String(limit))}`),
      {
        headers: {
          Accept: "application/json",
        },
      },
    );
  } catch (error) {
    if (error instanceof Error && error.message === CONFIG_ERROR_MESSAGE) {
      throw error;
    }

    throw new Error(NETWORK_MARKET_BARS_ERROR_MESSAGE);
  }

  if (!response.ok) {
    let message = "无法加载 TradingView 日线数据";
    let payload: ApiErrorEnvelope | null = null;

    try {
      payload = (await response.json()) as ApiErrorEnvelope;
    } catch {
      payload = null;
    }

    throw new Error(formatRuntimeErrorMessage(message, payload, response, true));
  }

  const bodyText = await response.text();
  if (!bodyText.trim()) {
    return [];
  }

  return JSON.parse(bodyText) as DailyBar[];
}
