<template>
  <section class="market-candle-chart">
    <div class="flex items-start justify-between gap-4">
      <div class="space-y-2">
        <p class="panel-title">{{ title }}</p>
        <h3 class="section-heading">{{ subtitle }}</h3>
        <p class="section-copy max-w-2xl">
          {{ description }}
        </p>
      </div>
      <div v-if="latestBar" class="text-right">
        <p class="font-mono text-[11px] tracking-[0.18em] text-slate-300/55">最新完成日线</p>
        <p class="mt-1 font-mono text-sm text-slate-200/80">{{ formatDate(latestBar.date) }}</p>
        <p class="mt-2 font-mono text-lg font-semibold text-amber-200">{{ formatPrice(latestBar.close) }}</p>
        <p class="mt-1 font-mono text-[11px] tracking-[0.16em] text-slate-300/50">悬停查看开高低收</p>
        <div v-if="hasCurrentPrice" class="mt-3 rounded-2xl border border-cyan-400/15 bg-cyan-400/10 px-3 py-2 text-left">
          <p class="font-mono text-[10px] tracking-[0.18em] text-cyan-100/60">实时参考价</p>
          <p class="mt-1 font-mono text-sm font-semibold text-cyan-100">{{ formatPrice(currentPriceDisplayValue) }}</p>
          <p class="mt-1 font-mono text-[10px] tracking-[0.16em] text-cyan-50/45">TradingView 最新快照</p>
        </div>
      </div>
    </div>

    <div v-if="chartStats" class="market-candle-chart__stats mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <div class="market-candle-chart__stat">
        <p class="metric-label">较前收盘涨跌</p>
        <p class="market-candle-chart__stat-value" :class="chartStats.change >= 0 ? 'text-emerald-200' : 'text-rose-200'">
          {{ formatSignedPrice(chartStats.change) }} / {{ formatPercent(chartStats.changePct) }}
        </p>
      </div>
      <div class="market-candle-chart__stat">
        <p class="metric-label">本日开收</p>
        <p class="market-candle-chart__stat-value" :class="chartStats.openCloseChange >= 0 ? 'text-emerald-200' : 'text-rose-200'">
          {{ formatSignedPrice(chartStats.openCloseChange) }} / {{ formatPercent(chartStats.openCloseChangePct) }}
        </p>
      </div>
      <div class="market-candle-chart__stat">
        <p class="metric-label">近10日均值</p>
        <p class="market-candle-chart__stat-value">{{ formatPrice(chartStats.averageClose) }}</p>
      </div>
      <div class="market-candle-chart__stat">
        <p class="metric-label">收盘形态</p>
        <p class="market-candle-chart__stat-value text-amber-200">{{ chartStats.trendLabel }}</p>
      </div>
    </div>

    <div v-if="bars.length === 0" class="metric-card metric-card--empty mt-4 text-sm text-slate-200/60">
      暂无可用的黄金日线数据。
    </div>

    <div v-else class="market-candle-chart__frame mt-4 rounded-[24px] border border-slate-400/15 bg-[#0f172a]/80 p-4 shadow-[0_18px_50px_-28px_rgba(0,0,0,0.36)]">
      <div class="overflow-x-auto">
        <div class="market-candle-chart__canvas relative w-max min-w-full" @mouseleave="clearHoveredCandle">
          <svg
            :viewBox="`0 0 ${chartWidth} ${chartHeight}`"
            class="h-[320px] w-full min-w-[840px]"
            role="img"
            :aria-label="`${title}，共 ${bars.length} 根日线`"
          >
            <defs>
              <radialGradient id="candle-canvas-glow" cx="50%" cy="22%" r="78%">
                <stop offset="0%" stop-color="rgba(56, 189, 248, 0.16)" />
                <stop offset="55%" stop-color="rgba(245, 158, 11, 0.06)" />
                <stop offset="100%" stop-color="rgba(15, 23, 42, 0)" />
              </radialGradient>
              <linearGradient id="candle-rise-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stop-color="#67e8f9" stop-opacity="0.96" />
                <stop offset="100%" stop-color="#22c55e" stop-opacity="0.72" />
              </linearGradient>
              <linearGradient id="candle-fall-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stop-color="#fb7185" stop-opacity="0.96" />
                <stop offset="100%" stop-color="#f97316" stop-opacity="0.68" />
              </linearGradient>
              <linearGradient id="candle-latest-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stop-color="#fde68a" stop-opacity="0.98" />
                <stop offset="100%" stop-color="#f59e0b" stop-opacity="0.88" />
              </linearGradient>
              <filter id="candle-glow" x="-40%" y="-40%" width="180%" height="180%">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            <rect x="0" y="0" :width="chartWidth" :height="chartHeight" fill="url(#candle-canvas-glow)" opacity="0.32" />

            <line
              :x1="paddingLeft"
              :x2="plotRight"
              :y1="paddingTop + plotHeight / 2"
              :y2="paddingTop + plotHeight / 2"
              stroke="rgba(148, 163, 184, 0.08)"
              stroke-width="1"
              stroke-dasharray="6 10"
            />

            <g v-if="hasCurrentPrice">
              <line
                :x1="paddingLeft"
                :x2="plotRight"
                :y1="currentPriceY"
                :y2="currentPriceY"
                stroke="rgba(34, 211, 238, 0.72)"
                stroke-width="1.5"
                stroke-dasharray="8 8"
              />
              <circle :cx="plotRight - 6" :cy="currentPriceY" r="4" fill="#67e8f9" opacity="0.95" />
              <text
                :x="plotRight + 16"
                :y="currentPriceY + 4"
                class="fill-cyan-100/88"
                font-size="10"
                font-family="Fira Code, monospace"
              >
                当前价 {{ formatPrice(currentPriceDisplayValue) }}
              </text>
            </g>

            <line
              :x1="plotRight + 10"
              :x2="plotRight + 10"
              :y1="paddingTop"
              :y2="paddingTop + plotHeight"
              stroke="rgba(148, 163, 184, 0.08)"
              stroke-width="1"
            />

            <g v-for="label in priceLabels" :key="label.text">
              <line
                :x1="paddingLeft"
                :x2="plotRight"
                :y1="label.y"
                :y2="label.y"
                stroke="rgba(148, 163, 184, 0.045)"
                stroke-width="1"
              />
              <text
                :x="plotRight + 16"
                :y="label.y + 4"
                class="fill-slate-300/58"
                font-size="10"
                font-family="Fira Code, monospace"
              >
                {{ label.text }}
              </text>
            </g>

            <g
              v-for="candle in candles"
              :key="`${candle.date}-${candle.index}`"
              @mouseenter="setHoveredCandle(candle)"
            >
              <line
                :x1="candle.centerX"
                :x2="candle.centerX"
                :y1="candle.highY"
                :y2="candle.lowY"
                :stroke="candle.isLatest ? 'url(#candle-latest-gradient)' : candle.isBullish ? 'url(#candle-rise-gradient)' : 'url(#candle-fall-gradient)'"
                :stroke-width="candle.isLatest ? 2.5 : 2"
                stroke-linecap="round"
              />
              <rect
                :x="candle.bodyX"
                :y="candle.bodyY"
                :width="candle.bodyWidth"
                :height="candle.bodyHeight"
                :fill="candle.isLatest ? 'url(#candle-latest-gradient)' : candle.isBullish ? 'url(#candle-rise-gradient)' : 'url(#candle-fall-gradient)'"
                :stroke="candle.isLatest ? 'rgba(251, 191, 36, 0.98)' : 'rgba(255,255,255,0.05)'"
                :stroke-width="candle.isLatest ? 2 : 1"
                :filter="candle.isLatest ? 'url(#candle-glow)' : undefined"
                rx="6"
                ry="6"
              />
              <circle
                v-if="candle.isLatest"
                :cx="candle.centerX"
                :cy="candle.bodyY"
                r="4"
                fill="#fde68a"
                opacity="0.9"
              />
              <text
                v-if="candle.showLabel"
                :x="candle.centerX"
                :y="paddingTop + plotHeight + 28"
                text-anchor="middle"
                class="fill-slate-300/70"
                font-size="10"
                font-family="Fira Code, monospace"
              >
                {{ candle.dateLabel }}
              </text>
            </g>
          </svg>

          <div
            v-if="hoveredCandle"
            class="market-candle-chart__tooltip pointer-events-none absolute z-20 rounded-2xl border border-slate-300/15 bg-slate-950/92 px-4 py-3 shadow-[0_20px_45px_-24px_rgba(0,0,0,0.72)] backdrop-blur-xl"
            :style="hoverTooltipStyle"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="space-y-1">
                <p class="font-mono text-[11px] tracking-[0.18em] text-slate-300/55">日线详情</p>
                <p class="text-sm font-semibold text-slate-50">{{ hoveredCandle.dateLabel }}</p>
              </div>
              <span class="status-pill status-pill--neutral text-[10px] tracking-[0.16em]">
                {{ hoveredCandle.isLatest ? "最新" : hoveredCandle.isBullish ? "阳线" : "阴线" }}
              </span>
            </div>

            <div class="mt-3 grid grid-cols-2 gap-2 text-xs">
              <div class="market-candle-chart__tooltip-row">
                <span class="market-candle-chart__tooltip-label">开盘</span>
                <span class="market-candle-chart__tooltip-value">{{ formatPrice(hoveredCandle.open) }}</span>
              </div>
              <div class="market-candle-chart__tooltip-row">
                <span class="market-candle-chart__tooltip-label">收盘</span>
                <span class="market-candle-chart__tooltip-value">{{ formatPrice(hoveredCandle.close) }}</span>
              </div>
              <div class="market-candle-chart__tooltip-row">
                <span class="market-candle-chart__tooltip-label">最高</span>
                <span class="market-candle-chart__tooltip-value text-emerald-200">{{ formatPrice(hoveredCandle.high) }}</span>
              </div>
              <div class="market-candle-chart__tooltip-row">
                <span class="market-candle-chart__tooltip-label">最低</span>
                <span class="market-candle-chart__tooltip-value text-rose-200">{{ formatPrice(hoveredCandle.low) }}</span>
              </div>
              <div class="market-candle-chart__tooltip-row col-span-2">
                <span class="market-candle-chart__tooltip-label">涨跌</span>
                <span class="market-candle-chart__tooltip-value" :class="hoveredCandle.change >= 0 ? 'text-emerald-200' : 'text-rose-200'">
                  {{ formatSignedPrice(hoveredCandle.change) }} / {{ formatPercent(hoveredCandle.changePct) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div class="metric-card metric-card--soft">
          <p class="metric-label">最近收盘</p>
          <p class="metric-value mt-1">{{ latestBar ? formatPrice(latestBar.close) : "—" }}</p>
        </div>
        <div class="metric-card metric-card--soft">
          <p class="metric-label">最近开盘</p>
          <p class="metric-value mt-1">{{ latestBar ? formatPrice(latestBar.open) : "—" }}</p>
        </div>
        <div class="metric-card metric-card--soft">
          <p class="metric-label">区间高低</p>
          <p class="metric-value mt-1">
            {{ latestBar ? `${formatPrice(latestBar.high)} / ${formatPrice(latestBar.low)}` : "—" }}
          </p>
        </div>
        <div class="metric-card metric-card--soft">
          <p class="metric-label">数据条数</p>
          <p class="metric-value mt-1">{{ bars.length }} 根</p>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { ref } from "vue";

import type { DailyBar } from "@/types/forecast";

interface CandlePoint {
  index: number;
  date: string;
  dateLabel: string;
  centerX: number;
  highY: number;
  lowY: number;
  bodyX: number;
  bodyY: number;
  bodyWidth: number;
  bodyHeight: number;
  open: number;
  high: number;
  low: number;
  close: number;
  isBullish: boolean;
  isLatest: boolean;
  showLabel: boolean;
  change: number;
  changePct: number;
}

interface PriceLabel {
  text: string;
  y: number;
}

const props = withDefaults(
  defineProps<{
    bars: DailyBar[];
    currentPrice?: number | null;
    title?: string;
    subtitle?: string;
    description?: string;
  }>(),
  {
    title: "黄金日线 K 线",
    subtitle: "最新一根日线",
    description: "黄金日线直接从行情数据读取，用于展示最近一根日线结构、收盘节奏和波动区间。",
  },
);

const paddingTop = 22;
const paddingBottom = 44;
const paddingLeft = 24;
const paddingRight = 72;
const chartHeight = 320;

const chartWidth = computed(() => Math.max(840, props.bars.length * 16 + paddingLeft + paddingRight));
const plotHeight = computed(() => chartHeight - paddingTop - paddingBottom);
const plotRight = computed(() => chartWidth.value - paddingRight);
const latestBar = computed(() => props.bars[props.bars.length - 1] ?? null);
const previousBar = computed(() => (props.bars.length > 1 ? props.bars[props.bars.length - 2] : null));
const hoveredCandle = ref<CandlePoint | null>(null);
const currentPriceValue = computed(() => (isValidPrice(props.currentPrice) ? props.currentPrice : null));
const currentPriceDisplayValue = computed(() => currentPriceValue.value ?? 0);
const hasCurrentPrice = computed(() => currentPriceValue.value !== null);
const highPrice = computed(() => {
  const barHigh = Math.max(...props.bars.map((bar) => bar.high), 1);
  return hasCurrentPrice.value ? Math.max(barHigh, currentPriceValue.value ?? barHigh) : barHigh;
});
const lowPrice = computed(() => {
  const barLow = Math.min(...props.bars.map((bar) => bar.low), highPrice.value);
  return hasCurrentPrice.value ? Math.min(barLow, currentPriceValue.value ?? barLow) : barLow;
});
const priceRange = computed(() => Math.max(highPrice.value - lowPrice.value, 1));
const currentPriceY = computed(() =>
  hasCurrentPrice.value ? scalePrice(currentPriceDisplayValue.value) : paddingTop + plotHeight.value / 2,
);

const hoverTooltipStyle = computed(() => {
  if (hoveredCandle.value === null) {
    return {};
  }

  const tooltipWidth = 256;
  const tooltipHeight = 168;
  const candle = hoveredCandle.value;
  const preferredLeft = candle.centerX;
  const left = Math.min(
    Math.max(preferredLeft, tooltipWidth / 2 + 16),
    chartWidth.value - tooltipWidth / 2 - 16,
  );
  const preferredTop = candle.highY <= paddingTop + 110 ? candle.lowY + 14 : candle.highY - tooltipHeight - 12;
  const top = Math.min(Math.max(preferredTop, 12), chartHeight - tooltipHeight - 12);

  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${tooltipWidth}px`,
    transform: "translateX(-50%)",
  };
});

const chartStats = computed(() => {
  if (latestBar.value === null) {
    return null;
  }

  const recentBars = props.bars.slice(-10);
  const averageClose = recentBars.reduce((sum, bar) => sum + bar.close, 0) / recentBars.length;
  const previousClose = previousBar.value?.close ?? latestBar.value.close;
  const change = latestBar.value.close - previousClose;
  const changePct = previousClose === 0 ? 0 : change / previousClose;
  const openCloseChange = latestBar.value.close - latestBar.value.open;
  const openCloseChangePct = latestBar.value.open === 0 ? 0 : openCloseChange / latestBar.value.open;
  const range = latestBar.value.high - latestBar.value.low;
  const trendLabel = latestBar.value.close >= latestBar.value.open ? "阳线" : "阴线";

  return {
    change,
    changePct,
    openCloseChange,
    openCloseChangePct,
    range,
    averageClose,
    trendLabel,
  };
});

const candles = computed<CandlePoint[]>(() => {
  if (props.bars.length === 0) {
    return [];
  }

  const innerWidth = chartWidth.value - paddingLeft - paddingRight - 20;
  const step = innerWidth / props.bars.length;
  const bodyWidth = Math.max(6, Math.min(12, step * 0.58));

  return props.bars.map((bar, index) => {
    const centerX = paddingLeft + step * index + step / 2;
    const highY = scalePrice(bar.high);
    const lowY = scalePrice(bar.low);
    const openY = scalePrice(bar.open);
    const closeY = scalePrice(bar.close);
    const bodyTop = Math.min(openY, closeY);
    const bodyBottom = Math.max(openY, closeY);
    const bodyHeight = Math.max(2, bodyBottom - bodyTop);
    const showLabel = index === 0 || index === props.bars.length - 1 || index % 6 === 0;
    const change = bar.close - bar.open;
    const changePct = bar.open === 0 ? 0 : change / bar.open;

    return {
      index,
      date: bar.date,
      dateLabel: formatDateShort(bar.date),
      centerX,
      highY,
      lowY,
      bodyX: centerX - bodyWidth / 2,
      bodyY: bodyTop,
      bodyWidth,
      bodyHeight,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      isBullish: bar.close >= bar.open,
      isLatest: index === props.bars.length - 1,
      showLabel,
      change,
      changePct,
    };
  });
});

const priceLabels = computed<PriceLabel[]>(() => {
  const max = highPrice.value;
  const min = lowPrice.value;
  const mid = min + (max - min) / 2;
  return [
    { text: formatPrice(max), y: paddingTop + 4 },
    { text: formatPrice(mid), y: paddingTop + plotHeight.value / 2 + 4 },
    { text: formatPrice(min), y: paddingTop + plotHeight.value - 2 },
  ];
});

function scalePrice(value: number): number {
  const ratio = (highPrice.value - value) / priceRange.value;
  return paddingTop + ratio * plotHeight.value;
}

function formatPrice(value: number): string {
  return new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function isValidPrice(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

function formatSignedPrice(value: number): string {
  const rendered = formatPrice(Math.abs(value));
  return value > 0 ? `+${rendered}` : value < 0 ? `-${rendered}` : rendered;
}

function setHoveredCandle(candle: CandlePoint): void {
  hoveredCandle.value = candle;
}

function clearHoveredCandle(): void {
  hoveredCandle.value = null;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

function formatDateShort(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}
</script>
