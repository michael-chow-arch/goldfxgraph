import type { ForecastResult } from "@/types/forecast";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

interface ApiErrorEnvelope {
  error?: {
    type?: string;
    message?: string;
  };
}

function buildUrl(path: string): string {
  return `${API_BASE_URL.replace(/\/$/, "")}${path}`;
}

export async function fetchLatestForecast(): Promise<ForecastResult | null> {
  const response = await fetch(buildUrl("/api/v1/forecast/latest"), {
    headers: {
      Accept: "application/json",
    },
  });

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
