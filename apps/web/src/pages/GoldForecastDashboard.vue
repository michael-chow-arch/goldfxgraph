<template>
  <main class="min-h-screen text-emerald-50">
    <div class="dashboard-shell mx-auto min-h-screen w-full max-w-[1600px] px-4 py-4 sm:px-6 lg:px-8 lg:py-6">
      <header class="dashboard-panel hero-panel relative overflow-hidden rounded-[32px] px-5 py-6 sm:px-6 sm:py-7 lg:px-8 lg:py-8">
        <div
          class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(46,230,107,0.18),transparent_22%),radial-gradient(circle_at_16%_18%,rgba(245,197,66,0.16),transparent_24%),radial-gradient(circle_at_84%_12%,rgba(39,199,255,0.08),transparent_20%)]"
        />
        <div class="relative grid gap-6 xl:grid-cols-[1.45fr_0.95fr]">
          <div class="space-y-6">
            <div class="flex flex-wrap items-center gap-3">
              <p class="panel-title">GoldFXGraph / XAUUSD 研究看板</p>
              <span class="status-pill" :class="statusPillClass">{{ stateLabel }}</span>
              <span class="status-pill status-pill--neutral">黑绿金赛博面板</span>
            </div>

            <div class="space-y-4">
              <h1 class="display-title text-balance text-4xl font-semibold tracking-tight text-[#eaf7ee] sm:text-5xl lg:text-6xl">
                黄金研究指挥台
              </h1>
              <p class="max-w-3xl text-sm leading-7 text-emerald-100/70 sm:text-base">
                聚焦最新 XAUUSD 研究结果、结构化交易字段、多智能体结论与风险提示。页面仅用于研究和决策支持，不构成投资建议，也不用于自动交易。
              </p>
              <p class="max-w-3xl text-xs leading-6 text-emerald-100/55 sm:text-sm">
                页面不会自动轮询刷新，仅在打开页面或点击“手动刷新”后重新读取最新研究结果。
              </p>
            </div>

            <div v-if="forecast" class="flex flex-wrap gap-3">
              <span v-for="chip in heroChips" :key="chip.label" class="data-chip">
                <span class="data-chip__label">{{ chip.label }}</span>
                <span class="data-chip__value">{{ chip.value }}</span>
              </span>
            </div>

            <div v-else class="flex flex-wrap gap-3">
              <span class="data-chip data-chip--placeholder">等待最新研究数据</span>
              <span class="data-chip data-chip--placeholder">等待方向信号</span>
              <span class="data-chip data-chip--placeholder">等待置信度快照</span>
            </div>
          </div>

          <aside class="metric-card metric-card--hero space-y-5">
            <div class="flex items-start justify-between gap-4">
              <div class="space-y-2">
                <p class="panel-title">实时价格快照</p>
                <p class="price-display">
                  {{ forecast ? formatPrice(forecast.current_price) : "—" }}
                </p>
                <p class="text-xs tracking-[0.18em] text-emerald-200/70 sm:text-sm">
                  XAUUSD · {{ forecast ? forecast.symbol : "等待加载" }}
                </p>
              </div>
              <span class="status-pill" :class="forecast ? directionClass : 'status-pill--neutral'">
                {{ forecast ? directionLabel : "等待加载" }}
              </span>
            </div>

            <div class="rounded-[24px] border border-emerald-400/20 bg-[#07150e]/75 p-4 backdrop-blur-xl">
              <div class="flex items-center justify-between text-xs text-emerald-100/55">
                <span>置信度</span>
                <span>{{ forecast ? formatPercent(forecast.confidence_score) : "0%" }}</span>
              </div>
              <div
                class="mt-2 h-2 overflow-hidden rounded-full bg-[#0b1d13]"
                role="progressbar"
                :aria-valuenow="confidenceValue"
                aria-valuemin="0"
                aria-valuemax="100"
                :aria-label="forecast ? `置信度 ${formatPercent(forecast.confidence_score)}` : '置信度 0%'"
              >
                <div
                  class="h-full rounded-full bg-gradient-to-r from-emerald-400 via-lime-400 to-amber-300"
                  :style="confidenceBarStyle"
                />
              </div>
            </div>

            <div class="grid gap-3 sm:grid-cols-2">
              <div v-for="metric in heroMetaCards" :key="metric.label" class="metric-card metric-card--soft">
                <p class="metric-label">{{ metric.label }}</p>
                <p class="metric-value mt-1 text-sm break-words text-emerald-100">{{ metric.value }}</p>
              </div>
            </div>

            <button type="button" class="action-button action-button--ghost w-full" @click="retry">手动刷新</button>
          </aside>
        </div>
      </header>

      <section
        v-if="isLoading"
        class="dashboard-panel mt-5 rounded-[28px] px-5 py-8 sm:px-6"
        aria-live="polite"
        role="status"
      >
        <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div class="space-y-2">
            <p class="panel-title">加载中</p>
            <h2 class="section-heading">正在加载最新黄金研究结果</h2>
            <p class="section-copy max-w-2xl">
              正在请求 `/api/v1/forecast/latest`，加载完成后会自动刷新本页内容。
            </p>
          </div>
          <div class="flex items-center gap-3 rounded-full border border-emerald-400/20 bg-[#06130d]/80 px-4 py-2">
            <span class="h-2.5 w-2.5 animate-pulse rounded-full bg-emerald-400" />
            <span class="font-mono text-xs tracking-[0.18em] text-emerald-100/65">等待最新快照</span>
          </div>
        </div>
      </section>

      <section
        v-else-if="errorMessage"
        class="dashboard-panel mt-5 rounded-[28px] border-emerald-400/20 px-5 py-8 sm:px-6"
        aria-live="assertive"
        role="alert"
      >
        <div class="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div class="space-y-2">
            <p class="panel-title text-emerald-300">加载失败</p>
            <h2 class="section-heading">研究结果加载失败</h2>
            <p class="section-copy max-w-2xl">{{ errorMessage }}</p>
          </div>
          <button type="button" class="action-button action-button--primary" @click="retry">手动刷新</button>
        </div>
      </section>

      <section
        v-else-if="!forecast"
        class="dashboard-panel mt-5 rounded-[28px] px-5 py-8 sm:px-6"
        aria-live="polite"
        role="status"
      >
        <div class="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div class="space-y-2">
            <p class="panel-title">暂无结果</p>
            <h2 class="section-heading">尚无可展示的最新研究结果</h2>
            <p class="section-copy max-w-2xl">{{ EMPTY_FORECAST_MESSAGE }}</p>
          </div>
          <button type="button" class="action-button action-button--secondary" @click="retry">重新查询</button>
        </div>
      </section>

      <template v-else>
        <section class="mt-5 grid gap-4 xl:grid-cols-12">
          <article class="dashboard-panel rounded-[28px] p-5 sm:p-6 xl:col-span-8">
            <div class="flex items-center justify-between gap-3">
              <div class="space-y-2">
                <p class="panel-title">研究摘要</p>
                <h2 class="section-heading">本轮 XAUUSD 研究结论</h2>
              </div>
              <span class="font-mono text-[11px] tracking-[0.18em] text-emerald-100/55">结构化摘要</span>
            </div>

            <div class="mt-4 grid gap-3 md:grid-cols-2">
              <article
                v-for="section in summaryCards"
                :key="section.title"
                class="metric-card metric-card--soft"
              >
                <p class="metric-label">{{ section.title }}</p>
                <p class="mt-2 break-words text-sm leading-6 text-emerald-100/75">{{ section.content }}</p>
              </article>
            </div>
          </article>

          <aside class="dashboard-panel rounded-[28px] p-5 sm:p-6 xl:col-span-4">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <p class="panel-title text-amber-300">风险提示</p>
              <span class="font-mono text-[11px] tracking-[0.18em] text-amber-200/70">重点关注</span>
            </div>

            <ul class="mt-4 space-y-3">
              <li
                v-for="(note, index) in forecast.risk_notes"
                :key="`${index}-${note}`"
                class="rounded-2xl border border-amber-300/20 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-emerald-100/80 shadow-[0_14px_36px_-30px_rgba(245,197,66,0.24)]"
              >
                {{ note }}
              </li>
              <li v-if="forecast.risk_notes.length === 0" class="metric-card metric-card--empty text-sm text-emerald-100/60">
                当前结果未返回额外的风险提示。
              </li>
            </ul>
          </aside>
        </section>

        <section class="mt-4">
          <article class="dashboard-panel rounded-[28px] p-5 sm:p-6">
            <div class="flex items-center justify-between gap-3">
              <div class="space-y-2">
                <p class="panel-title">智能体投票</p>
                <h2 class="section-heading">多智能体共识矩阵</h2>
              </div>
              <button type="button" class="action-button action-button--ghost" @click="retry">手动刷新</button>
            </div>

            <div class="mt-4 space-y-3 lg:hidden">
              <article
                v-for="vote in forecast.agent_votes"
                :key="`${vote.agent}-${vote.rationale}`"
                class="metric-card metric-card--soft"
              >
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <p class="font-mono text-sm font-semibold text-[#eaf7ee]">{{ agentLabel(vote.agent) }}</p>
                  <span class="status-pill" :class="voteDirectionClass(vote.direction)">
                    {{ DIRECTION_LABELS[vote.direction] }}
                  </span>
                </div>

                <dl class="mt-4 grid gap-3">
                  <div class="metric-card metric-card--embedded">
                    <dt class="metric-label">置信度</dt>
                    <dd class="mt-1 font-mono text-sm text-emerald-100/75">{{ formatPercent(vote.confidence) }}</dd>
                  </div>
                  <div class="metric-card metric-card--embedded">
                    <dt class="metric-label">理由</dt>
                    <dd class="mt-1 break-words text-sm leading-6 text-emerald-100/75">{{ vote.rationale }}</dd>
                  </div>
                </dl>
              </article>

              <div v-if="forecast.agent_votes.length === 0" class="metric-card metric-card--empty text-center text-sm text-emerald-100/60">
                当前结果未返回智能体投票。
              </div>
            </div>

            <div class="mt-4 hidden overflow-x-auto rounded-[24px] border border-emerald-400/20 bg-[#06130d]/80 lg:block">
              <table class="min-w-full divide-y divide-emerald-400/10">
                <thead class="bg-[#07150e]/90">
                  <tr>
                    <th class="whitespace-nowrap px-4 py-3 text-left font-mono text-[11px] tracking-[0.18em] text-emerald-200/70">
                      智能体
                    </th>
                    <th class="whitespace-nowrap px-4 py-3 text-left font-mono text-[11px] tracking-[0.18em] text-emerald-200/70">
                      方向
                    </th>
                    <th class="whitespace-nowrap px-4 py-3 text-left font-mono text-[11px] tracking-[0.18em] text-emerald-200/70">
                      置信度
                    </th>
                    <th class="px-4 py-3 text-left font-mono text-[11px] tracking-[0.18em] text-emerald-200/70">
                      理由
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-emerald-400/10 bg-[#06130d]/90">
                  <tr
                    v-for="vote in forecast.agent_votes"
                    :key="`${vote.agent}-${vote.rationale}`"
                    class="transition-colors duration-200 hover:bg-[#0b1d13]"
                  >
                    <td class="whitespace-nowrap px-4 py-3 font-mono text-sm font-medium text-[#eaf7ee]">{{ agentLabel(vote.agent) }}</td>
                    <td class="whitespace-nowrap px-4 py-3">
                      <span class="status-pill" :class="voteDirectionClass(vote.direction)">
                        {{ DIRECTION_LABELS[vote.direction] }}
                      </span>
                    </td>
                    <td class="whitespace-nowrap px-4 py-3 font-mono text-sm text-emerald-100/75">{{ formatPercent(vote.confidence) }}</td>
                    <td class="px-4 py-3 text-sm leading-6 break-words text-emerald-100/75">{{ vote.rationale }}</td>
                  </tr>
                  <tr v-if="forecast.agent_votes.length === 0">
                    <td colspan="4" class="px-4 py-6 text-center text-sm text-emerald-100/60">
                      当前结果未返回智能体投票。
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
        </section>

        <section class="mt-4 grid gap-4 xl:grid-cols-12">
          <article class="dashboard-panel rounded-[28px] p-5 sm:p-6 xl:col-span-7">
            <div class="flex items-center justify-between gap-3">
              <div class="space-y-2">
                <p class="panel-title">结构化交易字段</p>
                <h2 class="section-heading">研究决策行动卡</h2>
              </div>
              <span class="font-mono text-[11px] tracking-[0.18em] text-emerald-100/55">仅供研究</span>
            </div>

            <div class="mt-4 grid gap-3 md:grid-cols-2">
              <div class="metric-card metric-card--accent">
                <p class="metric-label">入场价</p>
                <p class="metric-value mt-1 text-base">{{ formatOptionalPrice(forecast.entry_price) }}</p>
              </div>
              <div class="metric-card metric-card--accent">
                <p class="metric-label">止盈价</p>
                <p class="metric-value mt-1 text-base">{{ formatOptionalPrice(forecast.take_profit_price) }}</p>
              </div>
              <div class="metric-card">
                <p class="metric-label">止损价</p>
                <p class="metric-value mt-1 text-base">{{ formatOptionalPrice(forecast.stop_loss_price) }}</p>
              </div>
              <div class="metric-card">
                <p class="metric-label">风险回报比</p>
                <p class="metric-value mt-1 text-base">{{ riskRewardRatio }}</p>
              </div>
            </div>

            <div class="mt-4 grid gap-3">
              <div class="metric-card metric-card--soft">
                <p class="metric-label">建议持有周期</p>
                <p class="mt-2 text-sm leading-6 text-emerald-100/75">{{ forecast.holding_period }}</p>
              </div>
              <div class="metric-card metric-card--soft">
                <p class="metric-label">日内建议</p>
                <p class="mt-2 text-sm leading-6 text-emerald-100/75">{{ forecast.intraday_action }}</p>
              </div>
              <div class="metric-card metric-card--soft">
                <p class="metric-label">中长期建议</p>
                <p class="mt-2 text-sm leading-6 text-emerald-100/75">{{ forecast.long_term_action }}</p>
              </div>
            </div>
          </article>

          <aside class="space-y-4 xl:col-span-5">
            <article class="dashboard-panel rounded-[28px] p-5 sm:p-6">
              <div class="flex items-center justify-between gap-3">
                <div class="space-y-2">
                  <p class="panel-title">实时元数据</p>
                  <h2 class="section-heading">研究透明度信息</h2>
                </div>
                <span class="font-mono text-[11px] tracking-[0.18em] text-emerald-100/55">来源与时间</span>
              </div>

              <dl class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                <div v-for="metric in supportCards" :key="metric.label" class="metric-card metric-card--soft">
                  <dt class="metric-label">{{ metric.label }}</dt>
                  <dd class="mt-1 break-words font-mono text-sm font-medium text-[#eaf7ee] sm:text-base">
                    {{ metric.value }}
                  </dd>
                </div>
              </dl>
            </article>

            <article class="dashboard-panel rounded-[28px] p-5 sm:p-6">
              <div class="flex items-center justify-between gap-3">
                <div class="space-y-2">
                  <p class="panel-title">日线 OHLC</p>
                  <h2 class="section-heading">已完成日线</h2>
                </div>
                <span class="font-mono text-[11px] tracking-[0.18em] text-emerald-100/55">Completed bar</span>
              </div>

              <div class="mt-4 grid gap-3 sm:grid-cols-2">
                <div v-for="ohlc in ohlcMetrics" :key="ohlc.label" class="metric-card">
                  <p class="metric-label">{{ ohlc.label }}</p>
                  <p class="metric-value mt-1">{{ ohlc.value }}</p>
                </div>
              </div>
            </article>
          </aside>
        </section>

        <section class="mt-4">
          <article class="dashboard-panel rounded-[28px] p-5 sm:p-6">
            <div class="flex items-center justify-between gap-3">
              <div class="space-y-2">
                <p class="panel-title">免责声明</p>
                <h2 class="section-heading">仅供研究，不构成投资建议</h2>
              </div>
              <span class="font-mono text-[11px] tracking-[0.18em] text-emerald-100/55">Research only</span>
            </div>
            <p class="mt-4 break-words text-sm leading-6 text-emerald-100/75">
              {{ forecast.disclaimer }}
            </p>
          </article>
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
import type { AgentVote, ForecastDirection, ForecastResult } from "@/types/forecast";

const forecast = ref<ForecastResult | null>(null);
const isLoading = ref(true);
const errorMessage = ref("");

const stateLabel = computed(() => {
  if (isLoading.value) {
    return "正在加载";
  }
  if (errorMessage.value) {
    return "加载失败";
  }
  if (!forecast.value) {
    return "暂无结果";
  }
  return "已同步";
});

const statusPillClass = computed(() =>
  isLoading.value
    ? "status-pill--loading"
    : errorMessage.value
      ? "status-pill--danger"
      : forecast.value
        ? "status-pill--success"
        : "status-pill--neutral",
);

const directionLabel = computed(() =>
  forecast.value ? DIRECTION_LABELS[forecast.value.direction] : "未加载",
);

const directionClass = computed(() =>
  forecast.value ? DIRECTION_STYLES[forecast.value.direction] : "border-amber-300/30 bg-amber-500/10 text-amber-100",
);

const confidenceValue = computed(() => {
  if (!forecast.value) {
    return 0;
  }

  return Math.round(clamp(forecast.value.confidence_score, 0, 1) * 100);
});

const confidenceBarStyle = computed(() => ({
  width: `${confidenceValue.value}%`,
}));

const heroChips = computed(() => {
  if (!forecast.value) {
    return [];
  }

  return [
    { label: "标的", value: forecast.value.symbol },
    { label: "方向", value: directionLabel.value },
    { label: "置信度", value: formatPercent(forecast.value.confidence_score) },
  ];
});

const heroMetaCards = computed(() => {
  if (!forecast.value) {
    return [];
  }

  return [
    { label: "数据时间", value: formatDateTime(forecast.value.data_timestamp) },
    { label: "数据来源", value: forecast.value.data_source },
  ];
});

const supportCards = computed(() => {
  if (!forecast.value) {
    return [];
  }

  return [
    { label: "参考时间", value: formatDateTime(forecast.value.reference_time) },
    { label: "运行编号", value: forecast.value.run_id ?? "暂无" },
    { label: "预测编号", value: forecast.value.id ?? "暂无" },
  ];
});

const ohlcMetrics = computed(() => {
  if (!forecast.value) {
    return [];
  }

  return [
    { label: "开盘", value: formatPrice(forecast.value.daily_open) },
    { label: "最高", value: formatPrice(forecast.value.daily_high) },
    { label: "最低", value: formatPrice(forecast.value.daily_low) },
    { label: "收盘", value: formatPrice(forecast.value.daily_close) },
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
      content: content && String(content).trim() ? String(content) : "当前维度暂无摘要。",
    };
  });
});

const riskRewardRatio = computed(() => {
  if (!forecast.value) {
    return "暂无";
  }

  const { entry_price, take_profit_price, stop_loss_price } = forecast.value;
  if (entry_price == null || take_profit_price == null || stop_loss_price == null) {
    return "暂无";
  }

  const reward = Math.abs(take_profit_price - entry_price);
  const risk = Math.abs(entry_price - stop_loss_price);
  if (risk === 0) {
    return "暂无";
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
    errorMessage.value = error instanceof Error ? error.message : "未知错误，无法加载最新黄金研究结果。";
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
    return "暂无";
  }
  return formatPrice(value);
}

function formatPercent(value: number): string {
  return `${(clamp(value, 0, 1) * 100).toFixed(0)}%`;
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

function voteDirectionClass(direction: ForecastDirection): string {
  return DIRECTION_STYLES[direction];
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

onMounted(() => {
  void loadForecast();
});
</script>
