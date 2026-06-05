<template>
  <main class="min-h-screen text-ui-surface">
    <DashboardStateBanner
      v-if="isLoading"
      variant="loading"
      eyebrow="加载中"
      title="正在加载执行轨迹与 prompt 元数据"
      message="页面将展示 workflow nodes、prompt versions、validation 与修复信息。"
      detail="完成后自动刷新为最新研究运行状态。"
    />

    <DashboardStateBanner
      v-else-if="errorMessage"
      variant="error"
      eyebrow="加载失败"
      title="轨迹页面暂不可用"
      :message="errorMessage"
      detail="请稍后再试，或返回研究总览页查看最新 forecast。"
    />

    <DashboardStateBanner
      v-else-if="!forecast"
      variant="empty"
      eyebrow="暂无内容"
      title="当前没有可展示的执行轨迹"
      message="暂无最新 forecast，因此无法渲染节点轨迹和 prompt 元数据。"
    />

    <div v-else class="space-y-5">
      <section class="dashboard-panel rounded-[28px] px-5 py-6 sm:px-6 lg:px-8">
        <DashboardSectionHeader
          eyebrow="Trace Overview"
          title="节点执行轨迹与 prompt 版本"
          description="该页面专门承载 workflow 轨迹、prompt 元数据和校验结果，避免与主结论混在一起。"
          badge="execution center"
        />

        <div class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <div class="metric-card metric-card--soft">
            <p class="metric-label">当前价格</p>
            <p class="metric-value mt-1">{{ formatPrice(forecast.current_price) }}</p>
          </div>
          <div class="metric-card metric-card--soft">
            <p class="metric-label">方向</p>
            <p class="metric-value mt-1">{{ directionLabel }}</p>
          </div>
          <div class="metric-card metric-card--soft">
            <p class="metric-label">置信度</p>
            <p class="metric-value mt-1">{{ formatPercent(forecast.confidence_score) }}</p>
          </div>
          <div class="metric-card metric-card--soft">
            <p class="metric-label">数据时间</p>
            <p class="metric-value mt-1 text-ui-body-md">{{ formatDateTime(forecast.data_timestamp) }}</p>
          </div>
          <div class="metric-card metric-card--soft">
            <p class="metric-label">数据来源</p>
            <p class="metric-value mt-1 text-ui-body-md">{{ formatRuntimeSourceLabel(forecast.data_source) }}</p>
          </div>
        </div>
      </section>

      <section class="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(360px,0.9fr)]">
        <article class="dashboard-panel rounded-[28px] p-5 sm:p-6">
          <DashboardSectionHeader
            eyebrow="Execution Trace"
            title="节点执行轨迹"
            description="按 workflow 顺序展示节点执行状态，便于检查 current stage 与执行结果。"
            badge="completed / running / failed / pending"
          />

          <div class="mt-4 grid gap-2">
            <div v-for="node in traceNodes" :key="node.key" class="metric-card metric-card--embedded">
              <div class="flex flex-wrap items-center justify-between gap-3">
                <div class="space-y-1">
                  <p class="text-ui-meta">{{ node.label }}</p>
                  <p class="text-ui-body-md">{{ node.hint }}</p>
                </div>
                <span class="status-pill" :class="node.statusClass">{{ node.statusLabel }}</span>
              </div>
            </div>
          </div>
        </article>

        <aside class="space-y-4">
          <article class="dashboard-panel rounded-[28px] p-5 sm:p-6">
            <DashboardSectionHeader eyebrow="Prompt Versions" title="实际使用的 prompt" heading-tag="h3" />

            <div v-if="promptVersions.length > 0" class="mt-4 space-y-2">
              <div v-for="prompt in promptVersions" :key="`${prompt.prompt_key}-${prompt.version}`" class="metric-card metric-card--embedded">
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <p class="text-ui-meta">{{ prompt.prompt_key }}</p>
                  <p class="text-ui-label">v{{ prompt.version }}</p>
                </div>
                <p class="mt-2 text-ui-body-md">
                  {{ prompt.agent_name ?? prompt.node_name ?? prompt.prompt_type }}
                </p>
                <p class="mt-1 text-ui-meta">
                  {{ prompt.prompt_type }}
                </p>
              </div>
            </div>

            <div v-else class="metric-card metric-card--empty surface-card-dark--empty mt-4 text-ui-body-sm">
              当前没有可展示的 prompt 元数据。
            </div>
          </article>

          <article class="dashboard-panel rounded-[28px] p-5 sm:p-6">
            <DashboardSectionHeader eyebrow="Validation" title="规则校验与修复" heading-tag="h3" />

            <div class="mt-4 space-y-3">
              <div class="metric-card metric-card--soft">
                <p class="metric-label">校验状态</p>
                <p class="metric-value mt-1 text-ui-card-title">{{ validationLabel }}</p>
              </div>
              <div v-if="validationSummary" class="metric-card metric-card--soft">
                <p class="metric-label">摘要</p>
                <p class="mt-2 text-ui-body-md">{{ validationSummary }}</p>
              </div>
              <div v-if="validationWarnings.length > 0" class="space-y-2">
                <p class="text-ui-meta">warnings</p>
                <div v-for="(warning, index) in validationWarnings" :key="`warning-${index}-${warning}`" class="metric-card metric-card--embedded">
                  <p class="text-ui-body-md">{{ warning }}</p>
                </div>
              </div>
              <div v-if="validationErrors.length > 0" class="space-y-2">
                <p class="text-ui-meta">errors</p>
                <div v-for="(error, index) in validationErrors" :key="`error-${index}-${error}`" class="metric-card metric-card--embedded">
                  <p class="text-ui-body-md">{{ error }}</p>
                </div>
              </div>
            </div>
          </article>
        </aside>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import DashboardSectionHeader from "@/components/dashboard/DashboardSectionHeader.vue";
import DashboardStateBanner from "@/components/dashboard/DashboardStateBanner.vue";
import { DIRECTION_LABELS, formatRuntimeSourceLabel } from "@/constants/forecast";
import { fetchLatestForecast, fetchLatestSchedulerStatus } from "@/services/forecastApi";
import type { FinalForecast, SchedulerRunStatus, PromptVersionMetadata } from "@/types/forecast";

const forecast = ref<FinalForecast | null>(null);
const schedulerStatus = ref<SchedulerRunStatus | null>(null);
const isLoading = ref(true);
const errorMessage = ref("");

const COMMITTEE_TRACE_SEQUENCE = [
  "router_validate_request",
  "tool_load_market_data",
  "tool_ensure_market_data_freshness",
  "tool_fetch_current_gold_quote",
  "tool_compute_indicators",
  "agent_technical_analysis",
  "tool_fetch_macro_inputs",
  "agent_macro_analysis",
  "tool_fetch_newsflow_inputs",
  "agent_news_analysis",
  "tool_fetch_pizza_index_inputs",
  "tool_load_forecast_feedback_history",
  "tool_fetch_polymarket_inputs",
  "tool_fetch_market_sentiment_inputs",
  "tool_fetch_alt_data_inputs",
  "agent_market_sentiment_analysis",
  "agent_alt_data_analysis",
  "agent_risk_analysis",
  "node_build_evidence_package",
  "agent_bull_opening_case",
  "agent_bear_opening_case",
  "agent_bull_rebuttal",
  "agent_bear_rebuttal",
  "agent_bull_final_position",
  "agent_bear_final_position",
  "agent_trading_committee_chair",
  "node_validate_committee_decision",
  "agent_repair_committee_decision",
  "node_persist_forecast",
  "router_finalize_result",
] as const;

const directionLabel = computed(() =>
  forecast.value ? DIRECTION_LABELS[forecast.value.direction] : "—",
);

const promptVersions = computed<PromptVersionMetadata[]>(() => forecast.value?.prompt_versions ?? []);
const validationStatus = computed(() => forecast.value?.validation_status ?? null);
const validationLabel = computed(() => {
  if (!validationStatus.value) {
    return "未校验";
  }
  return validationStatus.value.is_valid ? "校验通过" : "校验失败";
});
const validationSummary = computed(() => validationStatus.value?.summary ?? "");
const validationWarnings = computed(() => validationStatus.value?.warnings ?? []);
const validationErrors = computed(() => validationStatus.value?.errors ?? []);

const traceNodes = computed(() => {
  const hasForecast = Boolean(forecast.value);
  const schedulerState = schedulerStatus.value?.status ?? null;
  const currentStage = schedulerStatus.value?.current_stage ?? "";
  const currentIndex = COMMITTEE_TRACE_SEQUENCE.indexOf(currentStage as (typeof COMMITTEE_TRACE_SEQUENCE)[number]);

  return COMMITTEE_TRACE_SEQUENCE.map((key, index) => {
    let status: "completed" | "running" | "failed" | "pending" = "pending";

    if (schedulerState === "running") {
      if (currentIndex >= 0 && index < currentIndex) {
        status = "completed";
      } else if (currentIndex >= 0 && index === currentIndex) {
        status = "running";
      }
    } else if (schedulerState === "failed") {
      if (currentIndex >= 0 && index < currentIndex) {
        status = "completed";
      } else if (currentIndex >= 0 && index === currentIndex) {
        status = "failed";
      }
    } else if (schedulerState === "success") {
      status = "completed";
    } else if (hasForecast) {
      status = "completed";
    }

    return {
      key,
      label: committeeNodeLabel(key),
      hint: committeeNodeHint(key),
      status,
      statusLabel: committeeTraceStatusLabel(status),
      statusClass: committeeTraceStatusClass(status),
    };
  });
});

function committeeNodeLabel(key: string): string {
  const labels: Record<string, string> = {
    router_validate_request: "请求校验",
    tool_load_market_data: "加载市场数据",
    tool_ensure_market_data_freshness: "检查数据鲜度",
    tool_fetch_current_gold_quote: "获取最新黄金报价",
    tool_compute_indicators: "计算技术指标",
    agent_technical_analysis: "技术分析",
    tool_fetch_macro_inputs: "宏观输入",
    agent_macro_analysis: "宏观分析",
    tool_fetch_newsflow_inputs: "新闻输入",
    agent_news_analysis: "新闻分析",
    tool_fetch_pizza_index_inputs: "Pizza 指数",
    tool_load_forecast_feedback_history: "反馈历史",
    tool_fetch_polymarket_inputs: "Polymarket",
    tool_fetch_market_sentiment_inputs: "市场情绪输入",
    tool_fetch_alt_data_inputs: "另类数据输入",
    agent_market_sentiment_analysis: "市场情绪分析",
    agent_alt_data_analysis: "另类数据分析",
    agent_risk_analysis: "风险分析",
    node_build_evidence_package: "构建证据包",
    agent_bull_opening_case: "多头开场",
    agent_bear_opening_case: "空头开场",
    agent_bull_rebuttal: "多头反驳",
    agent_bear_rebuttal: "空头反驳",
    agent_bull_final_position: "多头终局",
    agent_bear_final_position: "空头终局",
    agent_trading_committee_chair: "主席仲裁",
    node_validate_committee_decision: "校验决策",
    agent_repair_committee_decision: "修复决策",
    node_persist_forecast: "持久化 forecast",
    router_finalize_result: "结束",
  };

  return labels[key] ?? key;
}

function committeeNodeHint(key: string): string {
  const hints: Record<string, string> = {
    router_validate_request: "验证输入与路由条件",
    tool_load_market_data: "读取市场数据源",
    tool_ensure_market_data_freshness: "确认 completed daily bars 已追平",
    tool_fetch_current_gold_quote: "拉取最新黄金报价",
    tool_compute_indicators: "计算技术指标特征",
    agent_technical_analysis: "输出技术面观点",
    tool_fetch_macro_inputs: "准备宏观输入",
    agent_macro_analysis: "输出宏观面观点",
    tool_fetch_newsflow_inputs: "准备新闻流输入",
    agent_news_analysis: "输出新闻面观点",
    node_build_evidence_package: "汇总证据包",
    agent_trading_committee_chair: "裁决最终结论",
    node_validate_committee_decision: "检查结构化结果",
    agent_repair_committee_decision: "修复缺失或冲突项",
    node_persist_forecast: "写回 forecast 结果",
    router_finalize_result: "完成本次 workflow",
  };

  return hints[key] ?? "workflow 节点";
}

function committeeTraceStatusLabel(status: "completed" | "running" | "failed" | "pending"): string {
  switch (status) {
    case "completed":
      return "已完成";
    case "running":
      return "执行中";
    case "failed":
      return "已失败";
    case "pending":
      return "待执行";
  }
}

function committeeTraceStatusClass(status: "completed" | "running" | "failed" | "pending"): string {
  switch (status) {
    case "completed":
      return "status-pill--success";
    case "running":
      return "status-pill--loading";
    case "failed":
      return "status-pill--danger";
    case "pending":
      return "status-pill--neutral";
  }
}

function formatPrice(value: number): string {
  return `$${value.toFixed(2)}`;
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

async function loadData(): Promise<void> {
  isLoading.value = true;
  errorMessage.value = "";

  try {
    const [latestForecast, latestSchedulerStatus] = await Promise.all([
      fetchLatestForecast(),
      fetchLatestSchedulerStatus(),
    ]);
    forecast.value = latestForecast;
    schedulerStatus.value = latestSchedulerStatus;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "无法加载节点轨迹页面。";
  } finally {
    isLoading.value = false;
  }
}

onMounted(() => {
  void loadData();
});
</script>
