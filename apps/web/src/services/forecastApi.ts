import type { ForecastResult } from "@/types/forecast";

const CONFIG_ERROR_MESSAGE = "前端配置错误：VITE_API_BASE_URL 无效，无法连接 GoldFXGraph backend。";
const NETWORK_ERROR_MESSAGE = "网络连接失败，暂时无法获取最新黄金研究结果。";

interface ApiErrorEnvelope {
  error?: {
    type?: string;
    message?: string;
  };
}

function apiBaseUrl(): string {
  const baseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

  if (!baseUrl) {
    throw new Error(CONFIG_ERROR_MESSAGE);
  }

  let parsedUrl: URL;

  try {
    parsedUrl = new URL(baseUrl);
  } catch {
    throw new Error(CONFIG_ERROR_MESSAGE);
  }

  if (!["http:", "https:"].includes(parsedUrl.protocol)) {
    throw new Error(CONFIG_ERROR_MESSAGE);
  }

  return parsedUrl.toString().replace(/\/$/, "");
}

function buildUrl(path: string): string {
  return `${apiBaseUrl()}${path}`;
}

export async function fetchLatestForecast(): Promise<ForecastResult | null> {
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

    throw new Error(NETWORK_ERROR_MESSAGE);
  }

  if (response.status === 404 || response.status === 204) {
    return null;
  }

  if (!response.ok) {
    let message = "无法加载最新黄金研究结果";

    try {
      const payload = (await response.json()) as ApiErrorEnvelope;
      if (payload.error?.message) {
        message = payload.error.message;
      }
    } catch {
      if (response.statusText) {
        message = response.statusText;
      }
    }

    throw new Error(message);
  }

  const bodyText = await response.text();
  if (!bodyText.trim()) {
    return null;
  }

  return JSON.parse(bodyText) as ForecastResult;
}
