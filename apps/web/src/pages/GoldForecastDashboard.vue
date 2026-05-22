<template>
  <main class="min-h-screen bg-terminal-bg text-terminal-text">
    <div class="mx-auto flex min-h-screen w-full max-w-[1600px] flex-col px-4 py-5 sm:px-6 lg:px-8">
      <header class="dashboard-panel rounded-lg px-4 py-4 sm:px-6">
        <div class="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div class="space-y-3">
            <p class="panel-title">GoldFXGraph / XAUUSD Research Dashboard</p>
            <div class="space-y-2">
              <h1 class="text-balance text-2xl font-semibold text-slate-50 sm:text-3xl">
                黄金研究信号总览
              </h1>
              <p class="max-w-3xl text-sm text-slate-400 sm:text-base">
                聚合最新 XAUUSD 研究结果、风险提示与多 Agent 结论，面向研究与决策支持，不用于自动交易。
              </p>
            </div>
          </div>

          <div class="grid gap-3 sm:grid-cols-3 xl:min-w-[540px]">
            <div class="rounded-md border border-slate-800 bg-slate-950/80 px-4 py-3">
              <p class="metric-label">Symbol</p>
              <p class="metric-value">{{ forecast?.symbol ?? "XAUUSD" }}</p>
            </div>
            <div class="rounded-md border border-slate-800 bg-slate-950/80 px-4 py-3">
              <p class="metric-label">Refresh</p>
              <p class="metric-value text-base">{{ isLoading ? "同步中" : "Latest" }}</p>
            </div>
            <div class="rounded-md border border-slate-800 bg-slate-950/80 px-4 py-3">
              <p class="metric-label">State</p>
              <p class="metric-value text-base">{{ stateLabel }}</p>
            </div>
          </div>
        </div>
      </header>

      <section
        v-if="isLoading"
        class="dashboard-panel mt-5 rounded-lg px-5 py-8 sm:px-6"
        aria-live="polite"
      >
        <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div class="space-y-2">
            <p class="panel-title">Loading</p>
            <h2 class="text-xl font-semibold text-slate-50">正在加载最新研究结果</h2>
            <p class="max-w-2xl text-sm text-slate-400">
              正在请求 `/api/v1/forecast/latest`，加载完成后会自动更新 Dashboard。
            </p>
          </div>
          <div class="flex items-center gap-3">
            <span class="h-2.5 w-2.5 animate-pulse rounded-full bg-emerald-400" />
            <span class="font-mono text-sm text-slate-300">Awaiting latest forecast payload</span>
          </div>
        </div>
      </section>

      <section
        v-else-if="errorMessage"
        class="dashboard-panel mt-5 rounded-lg border-orange-500/20 px-5 py-8 sm:px-6"
        aria-live="assertive"
      >
        <div class="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div class="space-y-2">
            <p class="panel-title text-orange-300">Error</p>
            <h2 class="text-xl font-semibold text-slate-50">研究结果加载失败</h2>
            <p class="max-w-2xl text-sm text-slate-400">{{ errorMessage }}</p>
          </div>
          <button
            type="button"
            class="inline-flex h-11 items-center justify-center rounded-md border border-emerald-500/30 bg-emerald-500/10 px-4 font-medium text-emerald-200 transition-colors duration-200 hover:bg-emerald-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/80"
            @click="retry"
          >
            重新加载
          </button>
        </div>
      </section>

      <section
        v-else-if="!forecast"
        class="dashboard-panel mt-5 rounded-lg px-5 py-8 sm:px-6"
        aria-live="polite"
      >
        <div class="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div class="space-y-2">
            <p class="panel-title">Empty</p>
            <h2 class="text-xl font-semibold text-slate-50">暂无最新预测</h2>
            <p class="max-w-2xl text-sm text-slate-400">{{ EMPTY_FORECAST_MESSAGE }}</p>
          </div>
          <button
            type="button"
            class="inline-flex h-11 items-center justify-center rounded-md border border-slate-700 bg-slate-800/80 px-4 font-medium text-slate-100 transition-colors duration-200 hover:border-slate-500 hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300/70"
            @click="retry"
          >
            重试查询
          </button>
        </div>
      </section>

      <template v-else>
        <section class="mt-5 grid gap-4 xl:grid-cols-[1.6fr_1fr]">
          <article class="dashboard-panel rounded-lg p-5 sm:p-6">
            <div class="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
              <div class="space-y-3">
                <p class="panel-title">Latest forecast</p>
                <div class="flex flex-wrap items-center gap-3">
                  <h2 class="font-mono text-4xl font-semibold tracking-tight text-slate-50 sm:text-5xl">
                    {{ formatPrice(forecast.current_price) }}
                  </h2>
                  <span
                    class="inline-flex min-h-9 items-center rounded-md border px-3 py-1.5 font-mono text-sm font-medium"
                    :class="directionClass"
                  >
                    {{ directionLabel }}
                  </span>
                </div>
                <div class="grid gap-2 text-sm text-slate-400 sm:grid-cols-2">
                  <p>数据来源: <span class="font-mono text-slate-200">{{ forecast.data_source }}</span></p>
                  <p>行情时间: <span class="font-mono text-slate-200">{{ formatDateTime(forecast.data_timestamp) }}</span></p>
                  <p>参考时间: <span class="font-mono text-slate-200">{{ formatDateTime(forecast.reference_time) }}</span></p>
                  <p>Forecast ID: <span class="font-mono text-slate-200">{{ forecast.id ?? "N/A" }}</span></p>
                </div>
              </div>

              <div class="grid min-w-full gap-3 sm:grid-cols-3 xl:min-w-[360px] xl:max-w-[420px]">
                <div class="rounded-md border border-slate-800 bg-slate-950/75 px-4 py-3">
                  <p class="metric-label">Confidence</p>
                  <p class="metric-value">{{ formatPercent(forecast.confidence_score) }}</p>
                </div>
                <div class="rounded-md border border-slate-800 bg-slate-950/75 px-4 py-3">
                  <p class="metric-label">Run ID</p>
                  <p class="metric-value">{{ forecast.run_id ?? "N/A" }}</p>
                </div>
                <div class="rounded-md border border-slate-800 bg-slate-950/75 px-4 py-3">
                  <p class="metric-label">Risk / Reward</p>
                  <p class="metric-value text-base">{{ riskRewardRatio }}</p>
                </div>
              </div>
            </div>
          </article>

          <aside class="dashboard-panel rounded-lg p-5 sm:p-6">
            <div class="flex items-center justify-between">
              <p class="panel-title">Execution</p>
              <button
                type="button"
                class="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs uppercase tracking-[0.18em] text-slate-200 transition-colors duration-200 hover:border-emerald-400/40 hover:text-emerald-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/80"
                @click="retry"
              >
                Refresh
              </button>
            </div>

            <dl class="mt-4 grid gap-3 sm:grid-cols-2">
              <div
                v-for="metric in executionMetrics"
                :key="metric.label"
                class="rounded-md border border-slate-800 bg-slate-950/75 px-4 py-3 transition-colors duration-200 hover:border-slate-700"
              >
                <dt class="metric-label">{{ metric.label }}</dt>
                <dd class="mt-1 font-mono text-sm font-medium text-slate-100 sm:text-base">
                  {{ metric.value }}
                </dd>
              </div>
            </dl>
          </aside>
        </section>

        <section class="mt-4 grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
          <article class="dashboard-panel rounded-lg p-5 sm:p-6">
            <div class="flex items-center justify-between">
              <p class="panel-title">Daily OHLC</p>
              <span class="font-mono text-xs uppercase tracking-[0.18em] text-slate-500">Completed daily bar</span>
            </div>

            <div class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div
                v-for="ohlc in ohlcMetrics"
                :key="ohlc.label"
                class="rounded-md border border-slate-800 bg-slate-950/75 px-4 py-3 transition-colors duration-200 hover:border-slate-700"
              >
                <p class="metric-label">{{ ohlc.label }}</p>
                <p class="metric-value">{{ ohlc.value }}</p>
              </div>
            </div>
          </article>

          <article class="dashboard-panel rounded-lg p-5 sm:p-6">
            <div class="flex items-center justify-between">
              <p class="panel-title">Holding guidance</p>
              <span class="font-mono text-xs uppercase tracking-[0.18em] text-slate-500">Research only</span>
            </div>

            <div class="mt-4 grid gap-3">
              <div class="rounded-md border border-slate-800 bg-slate-950/75 px-4 py-3">
                <p class="metric-label">Holding period</p>
                <p class="mt-1 text-sm text-slate-100">{{ forecast.holding_period }}</p>
              </div>
              <div class="rounded-md border border-slate-800 bg-slate-950/75 px-4 py-3">
                <p class="metric-label">Intraday action</p>
                <p class="mt-1 text-sm text-slate-100">{{ forecast.intraday_action }}</p>
              </div>
              <div class="rounded-md border border-slate-800 bg-slate-950/75 px-4 py-3">
                <p class="metric-label">Long-term action</p>
                <p class="mt-1 text-sm text-slate-100">{{ forecast.long_term_action }}</p>
              </div>
            </div>
          </article>
        </section>

        <section class="mt-4 grid gap-4 xl:grid-cols-[1.25fr_0.75fr]">
          <article class="dashboard-panel rounded-lg p-5 sm:p-6">
            <div class="flex items-center justify-between">
              <p class="panel-title">Research summaries</p>
              <span class="font-mono text-xs uppercase tracking-[0.18em] text-slate-500">Multi-agent digest</span>
            </div>

            <div class="mt-4 grid gap-3 md:grid-cols-2">
              <article
                v-for="section in summaryCards"
                :key="section.title"
                class="rounded-md border border-slate-800 bg-slate-950/75 px-4 py-4 transition-colors duration-200 hover:border-slate-700"
              >
                <p class="metric-label">{{ section.title }}</p>
                <p class="mt-2 text-sm leading-6 text-slate-200">{{ section.content }}</p>
              </article>
            </div>
          </article>

          <article class="dashboard-panel rounded-lg p-5 sm:p-6">
            <div class="flex items-center justify-between">
              <p class="panel-title">Risk notes</p>
              <span class="font-mono text-xs uppercase tracking-[0.18em] text-slate-500">Watchlist</span>
            </div>

            <ul class="mt-4 space-y-3">
              <li
                v-for="(note, index) in forecast.risk_notes"
                :key="`${index}-${note}`"
                class="rounded-md border border-slate-800 bg-slate-950/75 px-4 py-3 text-sm leading-6 text-slate-200 transition-colors duration-200 hover:border-slate-700"
              >
                {{ note }}
              </li>
              <li
                v-if="forecast.risk_notes.length === 0"
                class="rounded-md border border-dashed border-slate-800 bg-slate-950/55 px-4 py-3 text-sm text-slate-500"
              >
                当前结果未返回额外 risk notes。
              </li>
            </ul>
          </article>
        </section>

        <section class="mt-4 grid gap-4 xl:grid-cols-[1fr_auto]">
          <article class="dashboard-panel rounded-lg p-5 sm:p-6">
            <div class="flex items-center justify-between">
              <p class="panel-title">Agent votes</p>
              <span class="font-mono text-xs uppercase tracking-[0.18em] text-slate-500">Consensus matrix</span>
            </div>

            <div class="mt-4 space-y-3 lg:hidden">
              <article
                v-for="vote in forecast.agent_votes"
                :key="`${vote.agent}-${vote.rationale}`"
                class="rounded-md border border-slate-800 bg-slate-950/75 px-4 py-4"
              >
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <p class="font-mono text-sm font-semibold text-slate-100">{{ agentLabel(vote.agent) }}</p>
                  <span
                    class="inline-flex min-h-8 items-center rounded-md border px-2.5 py-1 font-mono text-xs font-medium"
                    :class="DIRECTION_STYLES[vote.direction]"
                  >
                    {{ DIRECTION_LABELS[vote.direction] }}
                  </span>
                </div>

                <dl class="mt-4 grid gap-3">
                  <div class="rounded-md border border-slate-800/80 bg-slate-900/55 px-3 py-2.5">
                    <dt class="metric-label">Confidence</dt>
                    <dd class="mt-1 font-mono text-sm text-slate-200">{{ formatPercent(vote.confidence) }}</dd>
                  </div>
                  <div class="rounded-md border border-slate-800/80 bg-slate-900/55 px-3 py-2.5">
                    <dt class="metric-label">Rationale</dt>
                    <dd class="mt-1 break-words text-sm leading-6 text-slate-300">{{ vote.rationale }}</dd>
                  </div>
                </dl>
              </article>

              <div
                v-if="forecast.agent_votes.length === 0"
                class="rounded-md border border-dashed border-slate-800 bg-slate-950/55 px-4 py-6 text-center text-sm text-slate-500"
              >
                当前结果未返回 agent votes。
              </div>
            </div>

            <div class="mt-4 hidden overflow-x-auto rounded-md border border-slate-800 lg:block">
              <table class="min-w-full divide-y divide-slate-800">
                <thead class="bg-slate-950/90">
                  <tr>
                    <th class="px-4 py-3 text-left font-mono text-[11px] uppercase tracking-[0.18em] text-slate-500">
                      Agent
                    </th>
                    <th class="px-4 py-3 text-left font-mono text-[11px] uppercase tracking-[0.18em] text-slate-500">
                      Direction
                    </th>
                    <th class="px-4 py-3 text-left font-mono text-[11px] uppercase tracking-[0.18em] text-slate-500">
                      Confidence
                    </th>
                    <th class="px-4 py-3 text-left font-mono text-[11px] uppercase tracking-[0.18em] text-slate-500">
                      Rationale
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-800 bg-slate-900/65">
                  <tr
                    v-for="vote in forecast.agent_votes"
                    :key="`${vote.agent}-${vote.rationale}`"
                    class="transition-colors duration-200 hover:bg-slate-800/70"
                  >
                    <td class="px-4 py-3 font-mono text-sm text-slate-100">{{ agentLabel(vote.agent) }}</td>
                    <td class="px-4 py-3">
                      <span
                        class="inline-flex min-h-8 items-center rounded-md border px-2.5 py-1 font-mono text-xs font-medium"
                        :class="DIRECTION_STYLES[vote.direction]"
                      >
                        {{ DIRECTION_LABELS[vote.direction] }}
                      </span>
                    </td>
                    <td class="px-4 py-3 font-mono text-sm text-slate-200">{{ formatPercent(vote.confidence) }}</td>
                    <td class="px-4 py-3 text-sm leading-6 text-slate-300 break-words">{{ vote.rationale }}</td>
                  </tr>
                  <tr v-if="forecast.agent_votes.length === 0">
                    <td colspan="4" class="px-4 py-6 text-center text-sm text-slate-500">
                      当前结果未返回 agent votes。
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>

          <aside class="dashboard-panel rounded-lg px-5 py-6 sm:px-6 xl:w-[320px]">
            <p class="panel-title">Disclaimer</p>
            <p class="mt-4 text-sm leading-6 text-slate-300">
              {{ forecast.disclaimer }}
            </p>
          </aside>
        </section>
      </template>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  AGENT_LABELS,
  DIRECTION_LABELS,
  DIRECTION_STYLES,
  EMPTY_FORECAST_MESSAGE,
  SUMMARY_SECTIONS,
} from "@/constants/forecast";
import { fetchLatestForecast } from "@/services/forecastApi";
import type { AgentVote, ForecastResult } from "@/types/forecast";

const forecast = ref<ForecastResult | null>(null);
const isLoading = ref(true);
const errorMessage = ref("");

const stateLabel = computed(() => {
  if (isLoading.value) {
    return "LOADING";
  }
  if (errorMessage.value) {
    return "ERROR";
  }
  if (!forecast.value) {
    return "EMPTY";
  }
  return "LIVE";
});

const directionLabel = computed(() =>
  forecast.value ? DIRECTION_LABELS[forecast.value.direction] : "未加载",
);

const directionClass = computed(() =>
  forecast.value ? DIRECTION_STYLES[forecast.value.direction] : "border-slate-700 bg-slate-800/70 text-slate-200",
);

const executionMetrics = computed(() => {
  if (!forecast.value) {
    return [];
  }

  return [
    { label: "Entry", value: formatOptionalPrice(forecast.value.entry_price) },
    { label: "Take Profit", value: formatOptionalPrice(forecast.value.take_profit_price) },
    { label: "Stop Loss", value: formatOptionalPrice(forecast.value.stop_loss_price) },
    { label: "Direction", value: directionLabel.value },
    { label: "Current Price", value: formatPrice(forecast.value.current_price) },
    { label: "Data Source", value: forecast.value.data_source },
  ];
});

const ohlcMetrics = computed(() => {
  if (!forecast.value) {
    return [];
  }

  return [
    { label: "Open", value: formatPrice(forecast.value.daily_open) },
    { label: "High", value: formatPrice(forecast.value.daily_high) },
    { label: "Low", value: formatPrice(forecast.value.daily_low) },
    { label: "Close", value: formatPrice(forecast.value.daily_close) },
  ];
});

const summaryCards = computed(() => {
  if (!forecast.value) {
    return [];
  }

  return SUMMARY_SECTIONS.map((section) => {
    const content = forecast.value?.[section.key] ?? null;
    return {
      title: section.title,
      content: content && String(content).trim() ? String(content) : "当前结果未返回该维度摘要。",
    };
  });
});

const riskRewardRatio = computed(() => {
  if (!forecast.value) {
    return "N/A";
  }

  const { entry_price, take_profit_price, stop_loss_price } = forecast.value;
  if (entry_price == null || take_profit_price == null || stop_loss_price == null) {
    return "N/A";
  }

  const reward = Math.abs(take_profit_price - entry_price);
  const risk = Math.abs(entry_price - stop_loss_price);
  if (risk === 0) {
    return "N/A";
  }

  return `${(reward / risk).toFixed(2)} R`;
});

async function loadForecast(): Promise<void> {
  isLoading.value = true;
  errorMessage.value = "";

  try {
    forecast.value = await fetchLatestForecast();
  } catch (error) {
    forecast.value = null;
    errorMessage.value = error instanceof Error ? error.message : "未知错误，无法加载最新研究结果";
  } finally {
    isLoading.value = false;
  }
}

async function retry(): Promise<void> {
  await loadForecast();
}

function formatPrice(value: number): string {
  return new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatOptionalPrice(value: number | null | undefined): string {
  if (value == null) {
    return "N/A";
  }
  return formatPrice(value);
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

function agentLabel(agent: AgentVote["agent"]): string {
  return AGENT_LABELS[agent] ?? agent;
}

onMounted(() => {
  void loadForecast();
});
</script>
