<template>
  <main class="min-h-screen text-slate-50" :class="marketSessionPageClass">
    <div class="dashboard-shell mx-auto min-h-screen w-full max-w-[1600px] px-4 py-4 sm:px-6 lg:px-8 lg:py-6" :class="marketSessionPageClass">
      <header class="dashboard-panel hero-panel relative overflow-hidden rounded-[32px] px-5 py-6 sm:px-6 sm:py-7 lg:px-8 lg:py-8" :class="marketSessionPageClass">
        <div
          class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(46,230,107,0.18),transparent_22%),radial-gradient(circle_at_16%_18%,rgba(245,197,66,0.16),transparent_24%),radial-gradient(circle_at_84%_12%,rgba(39,199,255,0.08),transparent_20%)]"
        />

        <div class="relative space-y-6">
          <div class="flex flex-wrap items-center gap-3">
            <span class="status-pill" :class="statusPillClass">{{ stateLabel }}</span>
            <span class="status-pill" :class="marketSessionClass">{{ marketSessionLabel }}</span>
          </div>

          <div class="space-y-4">
            <h1 class="display-title text-balance text-3xl font-semibold tracking-tight text-[#eff7ff] sm:text-4xl lg:text-5xl">
              Multi-Agent 预测分析看板
            </h1>
            <p class="max-w-3xl text-xs leading-6 text-slate-300/60 sm:text-sm">
              页面会自动轮询最新研究结果和调度状态，当前显示内容始终来自最新一次可用快照。
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

          <div v-if="forecast" class="grid gap-4 xl:grid-cols-12">
            <article class="metric-card metric-card--hero xl:col-span-5">
              <div class="flex items-start justify-between gap-4">
                <div class="space-y-2">
                  <p class="panel-title">当前价格</p>
                  <p class="price-display">
                    {{ forecast ? formatPrice(forecast.current_price) : "—" }}
                  </p>
                  <p class="text-xs tracking-[0.18em] text-slate-300/70 sm:text-sm">
                    XAUUSD · {{ forecast ? forecast.symbol : "等待 TradingView 快照" }}
                  </p>
                </div>
              </div>

              <div class="mt-4 flex flex-wrap gap-3">
                <span class="status-pill" :class="schedulerStatusClass">
                  {{ schedulerStatusLabel }}
                </span>
                <span v-if="schedulerStatus" class="status-pill status-pill--neutral">
                  {{ schedulerStageLabel }}
                </span>
                <span v-if="schedulerStatus" class="status-pill status-pill--neutral">
                  最新执行 {{ latestExecutionTime }}
                </span>
              </div>

              <p v-if="statusErrorMessage" class="mt-3 text-xs leading-6 text-amber-100/80">
                {{ statusErrorMessage }}
              </p>
            </article>

            <article class="metric-card metric-card--soft xl:col-span-4">
              <div class="flex items-center justify-between gap-3">
                <div class="space-y-1">
                  <p class="metric-label">当日方向</p>
                  <span class="text-[11px] tracking-[0.18em] text-slate-300/55">核心结论</span>
                </div>
                <span class="analysis-badge analysis-badge--accent">主判断</span>
              </div>
              <div class="mt-3 flex flex-wrap items-center gap-3">
                <span class="status-pill" :class="directionClass">{{ directionLabel }}</span>
                <span class="confidence-badge">{{ forecast ? formatPercent(forecast.confidence_score) : "0%" }}</span>
              </div>
              <div
                class="mt-3 h-2 overflow-hidden rounded-full bg-[#0b1d13]"
                role="progressbar"
                :aria-valuenow="confidenceValue"
                aria-valuemin="0"
                aria-valuemax="100"
                :aria-label="forecast ? `置信度 ${formatPercent(forecast.confidence_score)}` : '置信度 0%'"
              >
                <div class="h-full rounded-full bg-gradient-to-r from-cyan-400 via-emerald-400 to-amber-300" :style="confidenceBarStyle" />
              </div>
            </article>

            <article class="metric-card metric-card--soft xl:col-span-3">
              <div class="flex items-center justify-between gap-3">
                <div class="space-y-1">
                  <p class="metric-label">实时元数据</p>
                  <span class="text-[11px] tracking-[0.18em] text-slate-300/55">来源与时间</span>
                </div>
                <span class="analysis-badge analysis-badge--accent">透明</span>
              </div>
              <dl class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                <div v-for="metric in heroMetaCards" :key="metric.label" class="metric-card metric-card--embedded">
                  <dt class="metric-label">{{ metric.label }}</dt>
                  <dd class="mt-1 break-words font-mono text-sm font-medium text-slate-50 sm:text-base">
                    {{ metric.value }}
                  </dd>
                </div>
              </dl>
            </article>
          </div>

          <div v-if="schedulerAgentChips.length > 0" class="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            <div v-for="chip in schedulerAgentChips" :key="chip.label" class="metric-card metric-card--embedded">
              <div class="flex items-center justify-between gap-3">
                <p class="metric-label">{{ chip.label }}</p>
                <span class="status-pill" :class="chip.className">{{ chip.value }}</span>
              </div>
            </div>
          </div>
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
            <h2 class="section-heading">正在加载最新 TradingView 研究结果</h2>
            <p class="section-copy max-w-2xl">
              {{ LOADING_FORECAST_MESSAGE }}加载完成后会自动刷新本页内容。
            </p>
          </div>
          <div class="flex items-center gap-3 rounded-full border border-slate-400/15 bg-[#0f172a]/80 px-4 py-2">
            <span class="h-2.5 w-2.5 animate-pulse rounded-full bg-sky-400" />
            <span class="font-mono text-xs tracking-[0.18em] text-slate-200/70">等待 TradingView 快照</span>
          </div>
        </div>
      </section>

      <section
        v-else-if="errorMessage"
        class="dashboard-panel mt-5 rounded-[28px] border-slate-400/15 px-5 py-8 sm:px-6"
        aria-live="assertive"
        role="alert"
      >
        <div class="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div class="space-y-2">
            <p class="panel-title text-sky-300">加载失败</p>
            <h2 class="section-heading">TradingView 实时行情暂不可用</h2>
            <p class="section-copy max-w-2xl">{{ errorMessage }}</p>
            <p class="section-copy max-w-2xl text-slate-300/60">系统会继续自动轮询，等待下一次可用快照恢复展示。</p>
          </div>
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
            <h2 class="section-heading">尚无可展示的 TradingView 研究快照</h2>
            <p class="section-copy max-w-2xl">{{ EMPTY_FORECAST_MESSAGE }}</p>
          </div>
        </div>
      </section>

      <div v-if="forecast" class="mt-5 space-y-5">
        <section class="dashboard-panel rounded-[28px] px-5 py-6 sm:px-6 lg:px-8">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div class="space-y-2">
              <p class="panel-title">结构化交易字段</p>
              <h2 class="section-heading">入场、止盈、止损与持有框架</h2>
              <p class="section-copy max-w-3xl">
                这一段单独展示交易执行字段，避免与方向窗口和研究摘要混在一起，便于快速扫读。
              </p>
            </div>
            <span class="font-mono text-[11px] tracking-[0.18em] text-slate-300/55">trade setup</span>
          </div>

          <div class="mt-4 grid gap-4 lg:grid-cols-3">
            <article v-for="card in tradeLevelCards" :key="card.label" class="metric-card metric-card--soft">
              <p class="metric-label">{{ card.label }}</p>
              <p class="metric-value mt-2 text-xl">{{ card.value }}</p>
            </article>
          </div>

          <div class="mt-4 grid gap-4 xl:grid-cols-3">
            <article class="summary-detail">
              <div class="mb-2 flex items-center justify-between gap-3">
                <span class="analysis-badge analysis-badge--slate">风险回报比</span>
                <span class="analysis-badge analysis-badge--accent">行动参考</span>
              </div>
              <p class="text-lg font-semibold text-slate-900">{{ riskRewardRatio }}</p>
            </article>
            <article class="summary-lead summary-lead--featured">
              <div class="mb-2 flex items-center justify-between gap-3">
                <span class="analysis-badge analysis-badge--slate">持有周期</span>
                <span class="analysis-badge analysis-badge--accent">重点</span>
              </div>
              <p>{{ forecast.holding_period }}</p>
            </article>
            <article class="summary-detail">
              <div class="mb-2 flex items-center justify-between gap-3">
                <span class="analysis-badge analysis-badge--slate">日内 / 中长期</span>
                <span class="analysis-badge analysis-badge--accent">研究</span>
              </div>
              <p class="leading-7">{{ forecast.intraday_action }}</p>
              <p class="mt-3 leading-7 text-slate-700">{{ forecast.long_term_action }}</p>
            </article>
          </div>
        </section>

        <section class="dashboard-panel rounded-[28px] px-5 py-6 sm:px-6 lg:px-8">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div class="space-y-2">
              <p class="panel-title">时间窗判断</p>
              <h2 class="section-heading">0-3 / 3-5 / 6-15 / 15天后</h2>
              <p class="section-copy max-w-3xl">
                每个时间窗单独成段展示，主判断、补充判断和重点信息分层呈现，避免和其他模块混在一起。
              </p>
            </div>
            <span class="font-mono text-[11px] tracking-[0.18em] text-slate-300/55">window outlook</span>
          </div>

          <div v-if="windowDirectionCards.length > 0" class="mt-4 grid gap-4 xl:grid-cols-2">
            <article
              v-for="window in windowDirectionCards"
              :key="window.label"
              class="metric-card metric-card--soft space-y-3 min-h-[210px]"
            >
              <div class="flex items-center justify-between gap-3">
                <p class="font-mono text-xs tracking-[0.18em] text-slate-300/70">{{ window.label }}</p>
                <span class="status-pill" :class="window.directionClass">{{ window.directionLabel }}</span>
              </div>
              <div class="flex flex-wrap items-center gap-2 text-xs tracking-[0.12em] text-slate-300/70">
                <span class="rounded-full border border-slate-400/15 bg-[#0b1220]/70 px-2 py-1">{{ window.strength }}</span>
                <span class="rounded-full border border-slate-400/15 bg-[#0b1220]/70 px-2 py-1">{{ window.confidence }}</span>
                <span v-if="window.focusTag" class="rounded-full border border-amber-300/20 bg-amber-500/10 px-2 py-1 text-amber-100">{{ window.focusTag }}</span>
              </div>
              <div class="space-y-2">
                <div class="rounded-2xl border border-slate-300/15 bg-white/[0.03] px-3 py-2 text-sm leading-6 text-slate-100/90" :class="window.primaryReasonClass">
                  <div class="mb-2 flex items-center justify-between gap-3">
                    <span class="font-mono text-[10px] tracking-[0.18em] text-slate-300/55">主判断</span>
                    <span class="analysis-badge" :class="window.primaryBadgeClass">{{ window.primaryBadgeLabel }}</span>
                  </div>
                  <p>{{ window.primaryReason }}</p>
                </div>
                <div v-if="window.secondaryReasons.length > 0" class="space-y-2">
                  <div class="flex items-center justify-between gap-3">
                    <span class="font-mono text-[10px] tracking-[0.18em] text-slate-300/55">补充判断</span>
                    <span class="font-mono text-[10px] tracking-[0.18em] text-slate-300/45">由 agent 自由补充</span>
                  </div>
                  <div
                    v-for="item in window.secondaryReasons"
                    :key="`${window.label}-${item.tag}-${item.text}`"
                    class="rounded-2xl border border-slate-300/10 bg-[#0f172a]/75 px-3 py-2 text-sm leading-6 text-slate-200/80"
                    :class="item.important ? 'window-insight--important' : ''"
                  >
                    <div class="mb-2 flex items-center justify-between gap-3">
                      <span class="analysis-badge" :class="item.tagClass">{{ item.tag }}</span>
                      <span v-if="item.important" class="analysis-badge analysis-badge--accent">重点</span>
                    </div>
                    <p>{{ item.text }}</p>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section class="grid gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(360px,0.85fr)]">
          <article class="dashboard-panel market-candle-shell rounded-[28px] p-5 sm:p-6">
            <MarketCandlestickChart
              :bars="marketBars"
              :current-price="forecast?.current_price ?? null"
              title="K线图"
              subtitle="黄金日线结构"
              description="TradingView 行情每 15 分钟抓取一次，展示最近日线结构、收盘节奏、波动区间与价格参考线。"
            />
          </article>

          <aside class="space-y-4">
            <article class="dashboard-panel rounded-[28px] p-5 sm:p-6">
              <div class="flex items-center justify-between gap-3">
                <div class="space-y-2">
                  <p class="panel-title">日线快照</p>
                  <h2 class="section-heading">价格结构</h2>
                </div>
                <span class="font-mono text-[11px] tracking-[0.18em] text-slate-300/55">行情数据</span>
              </div>

              <div v-if="isMarketBarsLoading" class="metric-card metric-card--empty mt-4 text-sm text-slate-200/65">
                {{ LOADING_MARKET_BARS_MESSAGE }}
              </div>
              <div v-else-if="marketBarsErrorMessage" class="metric-card metric-card--danger mt-4 text-sm text-rose-100">
                {{ marketBarsErrorMessage }}
              </div>
              <div v-else-if="latestMarketBar" class="mt-4 space-y-3">
                <div class="metric-card metric-card--soft">
                  <p class="metric-label">日期</p>
                  <p class="metric-value mt-1 text-base">{{ formatDateShort(latestMarketBar.date) }}</p>
                </div>
                <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                  <div class="metric-card metric-card--soft">
                    <p class="metric-label">收盘</p>
                    <p class="metric-value mt-1 text-base">{{ formatPrice(latestMarketBar.close) }}</p>
                  </div>
                  <div class="metric-card metric-card--soft">
                    <p class="metric-label">来源</p>
                    <p class="metric-value mt-1 text-base">
                      {{ formatRuntimeSourceLabel(latestMarketBar.source ?? forecast?.data_source) }}
                    </p>
                  </div>
                </div>
                <div class="metric-card metric-card--accent">
                  <p class="metric-label">15分钟抓取说明</p>
                  <p class="mt-2 text-sm leading-6 text-slate-100/80">
                    TradingView 行情每 15 分钟抓取一次，最近一根日线用于辅助判断波动结构与风险边界。
                  </p>
                </div>
              </div>
              <div v-else class="metric-card metric-card--empty mt-4 text-sm text-slate-200/65">
                {{ EMPTY_MARKET_BARS_MESSAGE }}
              </div>
            </article>

            <article class="dashboard-panel rounded-[28px] p-5 sm:p-6">
              <div class="flex items-center justify-between gap-3">
                <div class="space-y-2">
                  <p class="panel-title">实时元数据</p>
                  <h2 class="section-heading">研究透明度信息</h2>
                </div>
                <span class="font-mono text-[11px] tracking-[0.18em] text-slate-300/55">来源与时间</span>
              </div>

              <dl class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                <div v-for="metric in supportCards" :key="metric.label" class="metric-card metric-card--soft">
                  <dt class="metric-label">{{ metric.label }}</dt>
                  <dd class="mt-1 break-words font-mono text-sm font-medium text-slate-50 sm:text-base">
                    {{ metric.value }}
                  </dd>
                </div>
              </dl>
            </article>
          </aside>
        </section>

        <section class="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(380px,0.8fr)]">
          <article class="dashboard-panel rounded-[28px] p-5 sm:p-6">
            <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div class="space-y-2">
                <p class="panel-title">研究摘要</p>
                <h2 class="section-heading">本轮 XAUUSD 研究结论</h2>
                <p class="text-xs tracking-[0.16em] text-slate-300/60">
                  结论时间：{{ formatDateTime(forecast.reference_time) }}
                </p>
              </div>
              <span class="font-mono text-[11px] tracking-[0.18em] text-slate-300/55">结构化摘要</span>
            </div>

            <div class="mt-4 grid gap-3 xl:grid-cols-12">
              <article
                v-for="section in orderedSummaryCards"
                :key="section.key"
                class="metric-card metric-card--soft summary-card"
                :class="[
                  section.accentClass,
                  section.featured ? 'xl:col-span-6' : 'xl:col-span-3',
                ]"
              >
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <div class="space-y-1">
                    <p class="metric-label">{{ section.title }}</p>
                    <span class="analysis-badge">{{ section.badge }}</span>
                  </div>
                  <span class="analysis-badge analysis-badge--accent">{{ section.stanceTagLabel }}</span>
                </div>

                <div class="mt-3 space-y-3">
                  <div class="summary-lead" :class="section.highlightLead ? 'summary-lead--featured' : ''">
                    <div class="mb-2 flex items-center justify-between gap-3">
                      <span class="font-mono text-[10px] tracking-[0.18em] text-slate-300/55">主判断</span>
                      <span v-if="section.hasImportantLine" class="analysis-badge analysis-badge--accent">重点</span>
                    </div>
                    <p>{{ section.leadLine.text }}</p>
                  </div>
                  <div v-if="section.detailLines.length > 0" class="space-y-2">
                    <div
                      v-for="(line, lineIndex) in section.detailLines"
                      :key="`${section.key}-${lineIndex}-${line.text}`"
                      class="summary-detail"
                      :class="line.important ? 'summary-detail--highlight' : ''"
                    >
                      <div class="mb-2 flex items-center justify-between gap-3">
                        <span class="analysis-badge" :class="line.tagClass">{{ line.tag }}</span>
                        <span v-if="line.important" class="analysis-badge analysis-badge--accent">重点</span>
                      </div>
                      <p>{{ line.text }}</p>
                    </div>
                  </div>
                  <div v-if="section.newsHighlights.length > 0" class="space-y-2">
                    <div class="summary-evidence-title">代表性标题</div>
                    <div
                      v-for="item in section.newsHighlights"
                      :key="`${section.key}-headline-${item.index}-${item.text}`"
                      class="summary-evidence summary-evidence--headline"
                    >
                      <div class="summary-evidence-index">{{ String(item.index).padStart(2, "0") }}</div>
                      <div class="summary-evidence-text">
                        <div class="font-mono text-[10px] tracking-[0.18em] text-slate-300/55">{{ item.source }}</div>
                        <div class="mt-1 text-sm leading-6 text-slate-100/90">{{ item.text }}</div>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="section.evidenceItems.length > 0" class="space-y-2">
                    <div class="summary-evidence-title">参考依据</div>
                    <div
                      v-for="item in section.evidenceItems"
                      :key="`${section.key}-evidence-${item.index}-${item.text}`"
                      class="summary-evidence"
                    >
                      <div class="summary-evidence-index">{{ String(item.index).padStart(2, "0") }}</div>
                      <div class="summary-evidence-text">
                        {{ item.text }}
                      </div>
                    </div>
                  </div>
                  <div class="summary-stance-row summary-stance-row--footer">
                    <span class="summary-stance-label">综合评价</span>
                    <span class="summary-stance summary-stance--featured" :class="section.stanceClass">
                      {{ section.stanceTagLabel }}
                    </span>
                  </div>
                </div>
              </article>
            </div>
          </article>

          <aside class="dashboard-panel risk-panel rounded-[28px] p-5 sm:p-6">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <p class="panel-title risk-panel__title">风险提示</p>
              <span class="font-mono text-[11px] tracking-[0.18em] text-amber-200/70">重点关注</span>
            </div>

            <div class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <div class="metric-card metric-card--soft metric-card--risk-meta">
                <p class="metric-label">风险生成时间</p>
                <p class="metric-value mt-1 text-sm text-slate-100/90">{{ formatDateTime(forecast.reference_time) }}</p>
              </div>
              <div class="metric-card metric-card--soft metric-card--risk-meta">
                <p class="metric-label">数据参考时间</p>
                <p class="metric-value mt-1 text-sm text-slate-100/90">{{ formatDateTime(forecast.data_timestamp) }}</p>
              </div>
            </div>

            <ul class="mt-4 space-y-3">
              <li
                v-for="(note, index) in riskNoteItems"
                :key="`${index}-${note.text}`"
                class="risk-note-card"
                :class="note.toneClass"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="flex items-center gap-2">
                    <span class="risk-note-index">{{ String(index + 1).padStart(2, "0") }}</span>
                    <p class="risk-note-title">风险条目</p>
                  </div>
                  <span class="risk-note-tag">{{ note.tag }}</span>
                </div>
                <p class="risk-note-body mt-2 whitespace-pre-line">
                  {{ note.text }}
                </p>
                <div class="mt-3 flex items-center justify-between gap-3 text-[11px] tracking-[0.14em] text-slate-300/50">
                  <span>生成时间</span>
                  <span>{{ note.generatedAtLabel }}</span>
                </div>
              </li>
              <li v-if="riskNoteItems.length === 0" class="metric-card metric-card--empty text-sm text-slate-200/60">
                当前结果未返回额外的风险提示。
              </li>
            </ul>
          </aside>
        </section>

        <section class="dashboard-panel rounded-[28px] p-5 sm:p-6">
          <div class="flex items-center justify-between gap-3">
            <div class="space-y-2">
              <p class="panel-title">智能体投票</p>
              <h2 class="section-heading">多智能体共识矩阵</h2>
            </div>
          </div>

          <div class="mt-4 space-y-3 lg:hidden">
            <article
              v-for="vote in forecast.agent_votes"
              :key="`${vote.agent}-${vote.rationale}`"
              class="metric-card metric-card--soft"
            >
              <div class="flex flex-wrap items-center justify-between gap-3">
                <p class="font-mono text-sm font-semibold text-slate-50">{{ agentLabel(vote.agent) }}</p>
                <span class="status-pill" :class="voteDirectionClass(vote.direction)">
                  {{ DIRECTION_LABELS[vote.direction] }}
                </span>
              </div>

              <dl class="mt-4 grid gap-3">
                <div class="metric-card metric-card--embedded">
                  <dt class="metric-label">置信度</dt>
                  <dd class="mt-1 font-mono text-sm text-slate-200/80">{{ formatPercent(vote.confidence) }}</dd>
                </div>
                <div class="metric-card metric-card--embedded">
                  <dt class="metric-label">理由</dt>
                  <dd class="mt-1 break-words text-sm leading-6 text-slate-200/80">{{ vote.rationale }}</dd>
                </div>
              </dl>
            </article>

            <div v-if="forecast.agent_votes.length === 0" class="metric-card metric-card--empty text-center text-sm text-slate-300/60">
              当前结果未返回智能体投票。
            </div>
          </div>

          <div class="mt-4 hidden overflow-x-auto rounded-[24px] border border-slate-400/15 bg-[#0f172a]/80 lg:block">
            <table class="min-w-full divide-y divide-slate-400/10">
              <thead class="bg-[#0f172a]/90">
                <tr>
                  <th class="whitespace-nowrap px-4 py-3 text-left font-mono text-[11px] tracking-[0.18em] text-slate-300/70">
                    智能体
                  </th>
                  <th class="whitespace-nowrap px-4 py-3 text-left font-mono text-[11px] tracking-[0.18em] text-slate-300/70">
                    方向
                  </th>
                  <th class="whitespace-nowrap px-4 py-3 text-left font-mono text-[11px] tracking-[0.18em] text-slate-300/70">
                    置信度
                  </th>
                  <th class="px-4 py-3 text-left font-mono text-[11px] tracking-[0.18em] text-slate-300/70">
                    理由
                  </th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-400/10 bg-[#0f172a]/90">
                <tr
                  v-for="vote in forecast.agent_votes"
                  :key="`${vote.agent}-${vote.rationale}`"
                  class="transition-colors duration-200 hover:bg-[#0b1d13]"
                >
                  <td class="whitespace-nowrap px-4 py-3 font-mono text-sm font-medium text-slate-50">{{ agentLabel(vote.agent) }}</td>
                  <td class="whitespace-nowrap px-4 py-3">
                    <span class="status-pill" :class="voteDirectionClass(vote.direction)">
                      {{ DIRECTION_LABELS[vote.direction] }}
                    </span>
                  </td>
                  <td class="whitespace-nowrap px-4 py-3 font-mono text-sm text-slate-200/80">{{ formatPercent(vote.confidence) }}</td>
                  <td class="px-4 py-3 text-sm leading-6 break-words text-slate-200/80">{{ vote.rationale }}</td>
                </tr>
                <tr v-if="forecast.agent_votes.length === 0">
                  <td colspan="4" class="px-4 py-6 text-center text-sm text-slate-300/60">
                    当前结果未返回智能体投票。
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="grid gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.78fr)]">
          <article class="dashboard-panel rounded-[28px] p-5 sm:p-6">
            <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div class="space-y-2">
                <p class="panel-title">历史表现</p>
                <h2 class="section-heading">每日 forecast 复盘与收益点数</h2>
                <p class="section-copy max-w-3xl">
                  这里展示按收盘后评估写回的历史结果，包括每日收益点数、命中结果和结算价，供后续预测参考。
                </p>
              </div>
              <span class="font-mono text-[11px] tracking-[0.18em] text-slate-300/55">
                {{ isHistoryLoading ? "正在加载历史表现" : `${historyStats.evaluatedCount} / ${historyStats.totalCount} 已评估` }}
              </span>
            </div>

            <div class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <div class="metric-card metric-card--soft">
                <p class="metric-label">历史 forecast 数</p>
                <p class="metric-value mt-1">{{ historyStats.totalCount }}</p>
              </div>
              <div class="metric-card metric-card--soft">
                <p class="metric-label">已评估数量</p>
                <p class="metric-value mt-1">{{ historyStats.evaluatedCount }}</p>
              </div>
              <div class="metric-card metric-card--soft">
                <p class="metric-label">累计收益点数</p>
                <p class="metric-value mt-1">{{ formatPnlPoints(historyStats.totalPnl) }}</p>
              </div>
              <div class="metric-card metric-card--soft">
                <p class="metric-label">命中率</p>
                <p class="metric-value mt-1">{{ formatPercent(historyStats.winRate) }}</p>
              </div>
            </div>

            <div class="history-summary-strip mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <div class="history-summary-item">
                <p class="metric-label">累计收益点数</p>
                <p class="history-summary-value">{{ formatPnlPoints(historyStats.totalPnl) }}</p>
              </div>
              <div class="history-summary-item">
                <p class="metric-label">平均每次收益</p>
                <p class="history-summary-value">{{ formatPnlPoints(historyStats.averagePnl) }}</p>
              </div>
              <div class="history-summary-item">
                <p class="metric-label">已评估 / 总数</p>
                <p class="history-summary-value">{{ `${historyStats.evaluatedCount} / ${historyStats.totalCount}` }}</p>
              </div>
              <div class="history-summary-item">
                <p class="metric-label">胜率</p>
                <p class="history-summary-value">{{ formatPercent(historyStats.winRate) }}</p>
              </div>
            </div>

            <div class="mt-4 rounded-[28px] border border-slate-300/10 bg-[#0f172a]/75 p-4">
              <div class="flex items-center justify-between gap-3">
                <div class="space-y-1">
                  <p class="panel-title">收益图表</p>
                  <h3 class="text-lg font-semibold text-slate-50">每日评估收益点数</h3>
                </div>
                <span class="font-mono text-[11px] tracking-[0.18em] text-slate-300/55">bar chart</span>
              </div>

              <div v-if="isHistoryLoading" class="mt-4 rounded-[20px] border border-slate-400/15 bg-[#0f172a]/70 p-6 text-sm text-slate-300/65">
                历史表现正在加载。
              </div>
              <div v-else-if="historyErrorMessage" class="mt-4 rounded-[20px] border border-rose-400/20 bg-rose-500/10 p-6 text-sm text-rose-100">
                {{ historyErrorMessage }}
              </div>
              <div v-else-if="historyChart.bars.length === 0" class="mt-4 rounded-[20px] border border-dashed border-slate-400/20 bg-[#0f172a]/70 p-6 text-sm text-slate-300/65">
                <template v-if="historyStats.totalCount > 0">
                  当前已有 forecast 记录，但尚未生成可展示的收盘评估。定时任务会在美国收盘后按最新收盘日线回写；如果刚过收盘窗口，请等待下一轮维护。
                </template>
                <template v-else>
                  当前没有已评估的历史 forecast，可以在后续收盘评估后查看图表。
                </template>
              </div>
              <div v-else class="mt-4 overflow-x-auto rounded-[22px] border border-slate-400/15 bg-[#0f172a]/80 p-3">
                <svg
                  :viewBox="`0 0 ${historyChart.width} ${historyChart.height}`"
                  class="h-[280px] w-full min-w-[840px]"
                  role="img"
                  aria-label="每日 forecast 收益点数图表"
                >
                  <defs>
                    <linearGradient id="history-positive-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
                      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.95" />
                      <stop offset="100%" stop-color="#22c55e" stop-opacity="0.45" />
                    </linearGradient>
                    <linearGradient id="history-negative-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
                      <stop offset="0%" stop-color="#fb7185" stop-opacity="0.95" />
                      <stop offset="100%" stop-color="#f59e0b" stop-opacity="0.45" />
                    </linearGradient>
                  </defs>
                  <line
                    x1="24"
                    :y1="historyChart.baselineY"
                    x2="816"
                    :y2="historyChart.baselineY"
                    stroke="rgba(148, 163, 184, 0.34)"
                    stroke-width="1.2"
                    stroke-dasharray="6 6"
                  />
                  <g v-for="bar in historyChart.bars" :key="`${bar.dateLabel}-${bar.value}`">
                    <rect
                      :x="bar.x"
                      :y="bar.y"
                      :width="bar.width"
                      :height="bar.height"
                      :fill="bar.fill"
                      rx="10"
                      ry="10"
                    >
                      <title>{{ `${bar.dateLabel} · ${bar.resultLabel} · ${bar.value} 点` }}</title>
                    </rect>
                    <text
                      :x="bar.x + bar.width / 2"
                      :y="bar.y + (bar.value.startsWith('-') ? bar.height + 18 : Math.max(bar.y - 10, 16))"
                      text-anchor="middle"
                      class="fill-slate-100"
                      font-size="11"
                      font-family="Fira Code, monospace"
                    >
                      {{ bar.value }}
                    </text>
                    <text
                      :x="bar.x + bar.width / 2"
                      y="228"
                      text-anchor="middle"
                      class="fill-slate-300/70"
                      font-size="10"
                      font-family="Fira Code, monospace"
                    >
                      {{ bar.dateLabel }}
                    </text>
                    <text
                      :x="bar.x + bar.width / 2"
                      y="242"
                      text-anchor="middle"
                      class="fill-slate-300/45"
                      font-size="9"
                      font-family="Fira Code, monospace"
                    >
                      {{ bar.resultLabel }}
                    </text>
                  </g>
                </svg>
              </div>
            </div>
          </article>

          <aside class="space-y-4">
            <article class="dashboard-panel rounded-[28px] p-5">
              <div class="flex items-center justify-between gap-3">
                <div class="space-y-1">
                  <p class="panel-title">最近结果</p>
                  <h3 class="text-lg font-semibold text-slate-50">逐日复盘</h3>
                </div>
                <span class="font-mono text-[11px] tracking-[0.18em] text-slate-300/55">latest</span>
              </div>

              <div v-if="!isHistoryLoading && !historyErrorMessage && historyItemsDescending.length > 0" class="mt-4 space-y-3">
                <article
                  v-for="item in historyItemsDescending.slice(0, 6)"
                  :key="`${item.forecast.id ?? item.forecast.reference_time}-${item.evaluation?.id ?? 'pending'}`"
                  class="metric-card metric-card--soft"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="space-y-1">
                      <p class="font-mono text-xs tracking-[0.18em] text-slate-300/70">
                        交易日：{{ formatDateShort(item.trading_day ?? item.forecast.reference_time) }}
                      </p>
                      <p class="font-mono text-[11px] tracking-[0.16em] text-slate-300/55">
                        预测：{{ formatDateTime(item.forecast.reference_time) }}
                      </p>
                      <p
                        v-if="item.evaluation"
                        class="font-mono text-[11px] tracking-[0.16em] text-slate-300/55"
                      >
                        评估：{{ formatDateTime(item.evaluation.evaluated_at) }}
                      </p>
                      <p class="text-sm font-semibold text-slate-50">
                        {{ DIRECTION_LABELS[item.forecast.direction] }} · {{ formatPrice(item.forecast.current_price) }}
                      </p>
                    </div>
                    <span
                      class="status-pill"
                      :class="item.evaluation ? (getHistoryDisplayPnlPoints(item) >= 0 ? 'status-pill--success' : 'status-pill--danger') : 'status-pill--neutral'"
                    >
                      {{ item.evaluation ? formatPnlPoints(getHistoryDisplayPnlPoints(item)) : "待评估" }}
                    </span>
                  </div>

                  <dl class="mt-3 grid gap-2">
                    <div class="metric-card metric-card--embedded">
                      <dt class="metric-label">结论</dt>
                      <dd class="mt-1 text-sm text-slate-200/80">
                        {{ item.evaluation ? HISTORY_RESULT_LABELS[item.evaluation.result] ?? item.evaluation.result : "尚未完成收盘评估" }}
                      </dd>
                    </div>
                    <div class="metric-card metric-card--embedded">
                      <dt class="metric-label">结算价</dt>
                      <dd class="mt-1 text-sm text-slate-200/80">
                        {{ item.evaluation ? formatPrice(item.evaluation.settlement_price) : "—" }}
                      </dd>
                    </div>
                  </dl>
                </article>
              </div>

              <div v-else class="metric-card metric-card--empty mt-4 text-sm text-slate-300/60">
                暂无可展示的历史结果。
              </div>
            </article>

            <article class="dashboard-panel rounded-[28px] p-5">
              <div class="flex items-center justify-between gap-3">
                <div class="space-y-1">
                  <p class="panel-title">反馈回流</p>
                  <h3 class="text-lg font-semibold text-slate-50">历史评估摘要</h3>
                </div>
                <span class="font-mono text-[11px] tracking-[0.18em] text-slate-300/55">context</span>
              </div>
              <div v-if="historyItemsDescending.length > 0" class="mt-4 space-y-2">
                <div
                  v-for="item in historyItemsDescending.slice(0, 4)"
                  :key="`summary-${item.forecast.id ?? item.forecast.reference_time}`"
                  class="summary-card summary-card--slate text-sm leading-6 text-slate-200/80"
                >
                  <div class="flex items-center justify-between gap-3">
                    <div class="space-y-0.5">
                      <p class="font-mono text-[11px] tracking-[0.18em] text-slate-300/70">
                        交易日：{{ formatDateShort(item.trading_day ?? item.forecast.reference_time) }}
                      </p>
                      <p class="font-mono text-[11px] tracking-[0.18em] text-slate-300/70">
                        预测：{{ formatDateTime(item.forecast.reference_time) }}
                      </p>
                      <p v-if="item.evaluation" class="font-mono text-[10px] tracking-[0.16em] text-slate-300/50">
                        评估：{{ formatDateTime(item.evaluation.evaluated_at) }}
                      </p>
                    </div>
                    <span class="analysis-badge">{{ item.evaluation ? HISTORY_RESULT_LABELS[item.evaluation.result] ?? item.evaluation.result : "待评估" }}</span>
                  </div>
                  <p class="mt-2">
                    {{ item.evaluation?.summary ?? "当前 forecast 尚未完成评估。" }}
                  </p>
                </div>
              </div>
              <div v-else class="metric-card metric-card--empty mt-4 text-sm text-slate-300/60">
                暂无摘要可以回流到后续预测。
              </div>
            </article>
          </aside>
        </section>

        <section class="dashboard-panel rounded-[28px] p-5 sm:p-6">
          <div class="flex items-center justify-between gap-3">
            <div class="space-y-2">
              <p class="panel-title">免责声明</p>
              <h2 class="section-heading">仅供研究，不构成投资建议</h2>
            </div>
            <span class="font-mono text-[11px] tracking-[0.18em] text-slate-300/55">Research only</span>
          </div>
          <p class="mt-4 break-words text-sm leading-6 text-slate-200/80">
            {{ forecast.disclaimer }}
          </p>
        </section>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import {
  AGENT_LABELS,
  DIRECTION_LABELS,
  DIRECTION_STYLES,
  HISTORY_RESULT_LABELS,
  EMPTY_FORECAST_MESSAGE,
  EMPTY_MARKET_BARS_MESSAGE,
  ERROR_FORECAST_MESSAGE,
  ERROR_MARKET_BARS_MESSAGE,
  LOADING_FORECAST_MESSAGE,
  LOADING_MARKET_BARS_MESSAGE,
  SUMMARY_SECTIONS,
  SCHEDULER_STAGE_LABELS,
  SCHEDULER_STATUS_LABELS,
  WINDOW_DIRECTION_LABELS,
  formatRuntimeSourceLabel,
} from "@/constants/forecast";
import MarketCandlestickChart from "@/components/MarketCandlestickChart.vue";
import {
  fetchForecastHistory,
  fetchLatestForecast,
  fetchLatestSchedulerStatus,
  fetchRecentMarketBars,
} from "@/services/forecastApi";
import type {
  AgentVote,
  DailyBar,
  ForecastDirection,
  ForecastHistoryItem,
  ForecastResult,
  SchedulerRunStatus,
} from "@/types/forecast";

const forecast = ref<ForecastResult | null>(null);
const schedulerStatus = ref<SchedulerRunStatus | null>(null);
const isLoading = ref(true);
const isStatusLoading = ref(true);
const errorMessage = ref("");
const statusErrorMessage = ref("");
const historyItems = ref<ForecastHistoryItem[]>([]);
const isHistoryLoading = ref(true);
const historyErrorMessage = ref("");
const marketBars = ref<DailyBar[]>([]);
const isMarketBarsLoading = ref(true);
const marketBarsErrorMessage = ref("");
const marketSessionClock = ref(new Date());
let marketSessionTimer: ReturnType<typeof window.setInterval> | null = null;
let liveRefreshTimer: ReturnType<typeof window.setInterval> | null = null;

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

const schedulerStatusLabel = computed(() => {
  if (isStatusLoading.value) {
    return "正在加载调度状态";
  }
  if (statusErrorMessage.value) {
    return "调度状态不可用";
  }
  if (!schedulerStatus.value) {
    return "等待调度状态";
  }
  return SCHEDULER_STATUS_LABELS[schedulerStatus.value.status] ?? schedulerStatus.value.status;
});

const schedulerStatusClass = computed(() => {
  if (isStatusLoading.value) {
    return "status-pill--loading";
  }
  if (statusErrorMessage.value) {
    return "status-pill--danger";
  }
  if (!schedulerStatus.value) {
    return "status-pill--neutral";
  }

  switch (schedulerStatus.value.status) {
    case "running":
      return "status-pill--loading";
    case "success":
      return "status-pill--success";
    case "failed":
      return "status-pill--danger";
    default:
      return "status-pill--neutral";
  }
});

const schedulerStageLabel = computed(() => {
  if (!schedulerStatus.value) {
    return "—";
  }
  return SCHEDULER_STAGE_LABELS[schedulerStatus.value.current_stage] ?? schedulerStatus.value.current_stage;
});

const latestExecutionTime = computed(() => {
  const status = schedulerStatus.value;
  if (!status) {
    return "—";
  }

  const value = status.completed_at ?? status.started_at;
  return formatDateTime(value);
});

const schedulerAgentChips = computed(() => {
  const status = schedulerStatus.value;
  if (!status || status.agent_statuses.length === 0) {
    return [];
  }

  return status.agent_statuses.map((agentStatus) => ({
    label: agentLabel(agentStatus.agent),
    value: schedulerAgentStatusLabel(agentStatus.status),
    className: schedulerAgentStatusClass(agentStatus.status),
  }));
});

const windowDirectionCards = computed(() => {
  if (!forecast.value) {
    return [];
  }

  return forecast.value.window_directions.map((window) => ({
    label: WINDOW_DIRECTION_LABELS[window.window_label] ?? window.window_label,
    directionLabel: DIRECTION_LABELS[window.direction],
    directionClass: DIRECTION_STYLES[window.direction],
    strength: window.strength === "strong" ? "强烈" : window.strength === "moderate" ? "中等" : "轻度",
    confidence: formatPercent(window.confidence),
    ...buildInsightDisplay(window.reason),
  }));
});

const marketSessionLabel = computed(() => getMarketSessionLabel(marketSessionClock.value));

const marketSessionClass = computed(() => {
  const label = marketSessionLabel.value;
  if (label === "周末 / 非交易时段") {
    return "status-pill--market-closed";
  }
  if (label === "美国市") {
    return "status-pill--market-us";
  }
  if (label === "伦敦市") {
    return "status-pill--market-london";
  }
  if (label === "欧洲市") {
    return "status-pill--market-eu";
  }
  if (label === "日本市") {
    return "status-pill--market-jp";
  }
  return "status-pill--market-closed";
});

const marketSessionPageClass = computed(() => {
  const label = marketSessionLabel.value;
  if (label === "周末 / 非交易时段") {
    return "market-session--closed";
  }
  if (label === "美国市") {
    return "market-session--us";
  }
  if (label === "伦敦市") {
    return "market-session--london";
  }
  if (label === "欧洲市") {
    return "market-session--eu";
  }
  return "market-session--jp";
});

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
    { label: "当日方向", value: directionLabel.value },
    { label: "置信度", value: formatPercent(forecast.value.confidence_score) },
  ];
});

const heroMetaCards = computed(() => {
  if (!forecast.value && !schedulerStatus.value) {
    return [];
  }

  const cards = [
    forecast.value ? { label: "数据时间", value: formatDateTime(forecast.value.data_timestamp) } : null,
    forecast.value ? { label: "数据来源", value: formatRuntimeSourceLabel(forecast.value.data_source) } : null,
    schedulerStatus.value
      ? {
          label: "最新执行",
          value: latestExecutionTime.value,
        }
      : null,
    schedulerStatus.value
      ? {
          label: "当前阶段",
          value: schedulerStageLabel.value,
        }
      : null,
  ];

  return cards.filter((card): card is { label: string; value: string } => card !== null);
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

const tradeLevelCards = computed(() => {
  if (!forecast.value) {
    return [];
  }

  const hasEntryRange =
    forecast.value.entry_price_low != null &&
    forecast.value.entry_price_high != null &&
    forecast.value.entry_price_low !== forecast.value.entry_price_high;

  return [
    {
      label: hasEntryRange ? "入场区间" : "入场价",
      value: hasEntryRange
        ? formatPriceRange(forecast.value.entry_price_low, forecast.value.entry_price_high)
        : formatOptionalPrice(forecast.value.entry_price),
    },
    { label: "止盈价", value: formatOptionalPrice(forecast.value.take_profit_price) },
    { label: "止损价", value: formatOptionalPrice(forecast.value.stop_loss_price) },
  ];
});

const entryLevelLabel = computed(() => {
  if (
    forecast.value?.entry_price_low != null &&
    forecast.value?.entry_price_high != null &&
    forecast.value.entry_price_low !== forecast.value.entry_price_high
  ) {
    return "入场区间";
  }
  return "入场价";
});

const entryLevelValue = computed(() => {
  if (
    forecast.value?.entry_price_low != null &&
    forecast.value?.entry_price_high != null &&
    forecast.value.entry_price_low !== forecast.value.entry_price_high
  ) {
    return formatPriceRange(forecast.value.entry_price_low, forecast.value.entry_price_high);
  }
  return formatOptionalPrice(forecast.value?.entry_price);
});

const summaryCards = computed(() => {
  if (!forecast.value) {
    return [];
  }

  return SUMMARY_SECTIONS.map((section) => {
    const content = forecast.value?.[section.key] ?? null;
    const renderedContent = content && String(content).trim() ? String(content) : "当前维度暂无摘要。";
    const rawLines = splitSummaryLines(renderedContent);
    const newsMarkerIndex = section.key === "news_summary" ? rawLines.findIndex((line) => line.includes("代表性标题")) : -1;
    const lines = rawLines.map((line) => parseInsightLine(line));
    const newsHighlights = section.key === "news_summary" ? parseNewsHighlights(renderedContent) : [];
    const evidenceLines = section.key === "news_summary" ? [] : splitEvidenceLines(renderedContent).slice(1);
    const hasImportantLine = lines.some((line) => line.important);
    return {
      key: section.key,
      title: section.title,
      content: renderedContent,
      leadLine: lines[0] ?? parseInsightLine("当前维度暂无摘要。"),
      detailLines: section.key === "news_summary" && newsMarkerIndex > 0 ? lines.slice(1, newsMarkerIndex) : lines.slice(1),
      highlightLead: (lines[0] ?? parseInsightLine("当前维度暂无摘要。")).important,
      hasImportantLine,
      evidenceItems: evidenceLines.map((text, index) => ({
        index: index + 1,
        text,
      })),
      newsHighlights,
      stanceLabel: summaryStanceLabel(section.key, renderedContent),
      stanceTagLabel: summaryStanceTagLabel(section.key, renderedContent),
      stanceClass: summaryStanceClass(section.key, renderedContent),
      badge: summaryBadge(section.key),
      accentClass: summaryAccentClass(section.key),
      featured: section.key === "technical_summary" || section.key === "risk_summary",
    };
  });
});

const orderedSummaryCards = computed(() => {
  const priority = [
    "technical_summary",
    "risk_summary",
    "macro_summary",
    "news_summary",
    "market_sentiment_summary",
    "alt_data_summary",
  ] as const;

  const cards = new Map(summaryCards.value.map((card) => [card.key, card]));
  return priority.map((key) => cards.get(key)).filter(Boolean) as typeof summaryCards.value;
});

const historyDailySeries = computed(() => {
  const sortedItems = [...historyItems.value].sort((left, right) => {
    const rightTime = new Date(right.forecast.reference_time).getTime();
    const leftTime = new Date(left.forecast.reference_time).getTime();
    return rightTime - leftTime;
  });

  const latestByTradingDay = new Map<string, ForecastHistoryItem>();
  for (const item of sortedItems) {
    const tradingDayKey = item.trading_day ?? formatTradingDayKey(item.forecast.reference_time);
    if (!latestByTradingDay.has(tradingDayKey)) {
      latestByTradingDay.set(tradingDayKey, item);
    }
  }

  return [...latestByTradingDay.values()].sort((left, right) => {
    const leftKey = left.trading_day ?? formatTradingDayKey(left.forecast.reference_time);
    const rightKey = right.trading_day ?? formatTradingDayKey(right.forecast.reference_time);
    return rightKey.localeCompare(leftKey);
  });
});

const historyItemsDescending = computed(() => [...historyDailySeries.value]);

const historyEvaluations = computed(() => historyDailySeries.value.filter((item) => item.evaluation));

const historyStats = computed(() => {
  const evaluations = historyEvaluations.value;
  const totalCount = historyDailySeries.value.length;
  const evaluatedCount = evaluations.length;
  const totalPnl = evaluations.reduce((sum, item) => sum + getHistoryDisplayPnlPoints(item), 0);
  const winCount = evaluations.filter((item) => item.evaluation?.result === "win").length;
  const averagePnl = evaluatedCount > 0 ? totalPnl / evaluatedCount : 0;
  const winRate = evaluatedCount > 0 ? winCount / evaluatedCount : 0;

  return {
    totalCount,
    evaluatedCount,
    totalPnl,
    averagePnl,
    winRate,
  };
});

const historyChart = computed(() => {
  const evaluations = historyEvaluations.value;
  const chartWidth = 840;
  const chartHeight = 240;
  const barGap = 14;
  const barCount = evaluations.length;
  if (barCount === 0) {
    return {
      width: chartWidth,
      height: chartHeight,
      baselineY: chartHeight / 2,
      bars: [] as Array<{
        x: number;
        y: number;
        height: number;
        width: number;
        fill: string;
        label: string;
        value: string;
        resultLabel: string;
        dateLabel: string;
      }>,
    };
  }

  const innerWidth = chartWidth - 64;
  const barWidth = Math.max(18, (innerWidth - barGap * (barCount - 1)) / barCount);
  const maxAbs = Math.max(...evaluations.map((item) => Math.abs(getHistoryDisplayPnlPoints(item))), 1);
  const baselineY = chartHeight / 2;
  const maxBarHeight = chartHeight * 0.34;

  return {
    width: chartWidth,
    height: chartHeight,
    baselineY,
    bars: evaluations.map((item, index) => {
      const pnl = getHistoryDisplayPnlPoints(item);
      const barHeight = Math.max(2, (Math.abs(pnl) / maxAbs) * maxBarHeight);
      const x = 32 + index * (barWidth + barGap);
      const y = pnl >= 0 ? baselineY - barHeight : baselineY;
      return {
        x,
        y,
        height: barHeight,
        width: barWidth,
        fill: pnl >= 0 ? "url(#history-positive-gradient)" : "url(#history-negative-gradient)",
        label: item.forecast.symbol,
        value: formatSignedPnl(pnl),
        resultLabel: HISTORY_RESULT_LABELS[item.evaluation?.result ?? "flat"] ?? item.evaluation?.result ?? "未知",
        dateLabel: formatDateShort(item.trading_day ?? item.forecast.reference_time),
      };
    }),
  };
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

const latestMarketBar = computed(() => marketBars.value[marketBars.value.length - 1] ?? null);

const riskNoteItems = computed(() => {
  if (!forecast.value) {
    return [];
  }

  const generatedAtLabel = formatDateTime(forecast.value.reference_time);

  return forecast.value.risk_notes
    .filter((note) => !isDiagnosticRiskNote(note))
    .map((note) => ({
    text: note,
    tag: riskNoteTag(note),
    toneClass: riskNoteToneClass(note),
    generatedAtLabel,
    }));
});

async function loadForecast(options: { background?: boolean } = {}): Promise<void> {
  const background = options.background ?? false;

  if (!background) {
    isLoading.value = true;
    errorMessage.value = "";
  }

  try {
    forecast.value = await fetchLatestForecast();
    errorMessage.value = "";
  } catch (error) {
    if (!background || forecast.value === null) {
      forecast.value = null;
      errorMessage.value = error instanceof Error ? error.message : ERROR_FORECAST_MESSAGE;
    }
  } finally {
    if (!background) {
      isLoading.value = false;
    }
  }
}

async function loadSchedulerStatus(options: { background?: boolean } = {}): Promise<void> {
  const background = options.background ?? false;

  if (!background) {
    isStatusLoading.value = true;
    statusErrorMessage.value = "";
  }

  try {
    schedulerStatus.value = await fetchLatestSchedulerStatus();
    statusErrorMessage.value = "";
  } catch (error) {
    if (!background || schedulerStatus.value === null) {
      schedulerStatus.value = null;
      statusErrorMessage.value = error instanceof Error ? error.message : "未知错误，无法加载最新调度状态。";
    }
  } finally {
    if (!background) {
      isStatusLoading.value = false;
    }
  }
}

async function loadHistory(): Promise<void> {
  isHistoryLoading.value = true;
  historyErrorMessage.value = "";

  try {
    historyItems.value = await fetchForecastHistory(30);
  } catch (error) {
    historyItems.value = [];
    historyErrorMessage.value = error instanceof Error ? error.message : "未知错误，无法加载历史表现。";
  } finally {
    isHistoryLoading.value = false;
  }
}

async function loadMarketBars(): Promise<void> {
  isMarketBarsLoading.value = true;
  marketBarsErrorMessage.value = "";

  try {
    marketBars.value = await fetchRecentMarketBars("XAUUSD", 60);
  } catch (error) {
    marketBars.value = [];
    marketBarsErrorMessage.value = error instanceof Error ? error.message : ERROR_MARKET_BARS_MESSAGE;
  } finally {
    isMarketBarsLoading.value = false;
  }
}

async function refreshLiveData(options: { background?: boolean } = {}): Promise<void> {
  await Promise.all([loadForecast(options), loadSchedulerStatus(options)]);
}

async function loadStaticData(): Promise<void> {
  await Promise.all([loadHistory(), loadMarketBars()]);
}

function getHistoryDisplayPnlPoints(item: ForecastHistoryItem): number {
  const evaluation = item.evaluation;
  if (!evaluation) {
    return 0;
  }
  return evaluation.pnl_points;
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

function formatPriceRange(
  low: number | null | undefined,
  high: number | null | undefined,
): string {
  if (low == null || high == null) {
    return "暂无";
  }
  return `${formatPrice(low)} - ${formatPrice(high)}`;
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

function formatTradingDayKey(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toISOString().slice(0, 10);
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

function formatSignedPnl(value: number): string {
  const rounded = value.toFixed(2);
  return value > 0 ? `+${rounded}` : rounded;
}

function formatPnlPoints(value: number): string {
  return formatSignedPnl(value);
}

function agentLabel(agent: AgentVote["agent"]): string {
  return AGENT_LABELS[agent] ?? agent;
}

function voteDirectionClass(direction: ForecastDirection): string {
  return DIRECTION_STYLES[direction];
}

function schedulerAgentStatusLabel(status: string): string {
  const labelMap: Record<string, string> = {
    pending: "分析中",
    running: "执行中",
    success: "已完成",
    failed: "已失败",
  };

  return labelMap[status] ?? status;
}

function schedulerAgentStatusClass(status: string): string {
  switch (status) {
    case "running":
      return "status-pill--loading";
    case "success":
      return "status-pill--success";
    case "failed":
      return "status-pill--danger";
    default:
      return "status-pill--neutral";
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function splitSummaryLines(value: string): string[] {
  const normalized = value.replace(/\r\n/g, "\n").trim();
  if (!normalized) {
    return [];
  }

  const lines = normalized
    .split("\n")
    .map((line) => line.replace(/^\-\s*/, "").trim())
    .filter((line) => line.length > 0);

  return lines.length > 0 ? lines : [normalized];
}

function parseInsightLine(value: string, fallbackTag = "主判断"): {
  tag: string;
  text: string;
  tagClass: string;
  important: boolean;
} {
  const normalized = value.trim();
  if (!normalized) {
    return {
      tag: fallbackTag,
      text: "",
      tagClass: "analysis-badge--slate",
      important: false,
    };
  }

  const match = normalized.match(/^(?:【(?<bracketTag>[^】]{1,12})】|(?<plainTag>[^：:]{1,12})[:：])\s*(?<text>.+)$/u);
  const extractedTag = (match?.groups?.bracketTag ?? match?.groups?.plainTag ?? "").trim();
  const text = (match?.groups?.text ?? normalized).trim();
  const tag = extractedTag || fallbackTag;
  const important = /^(?:重点|关键|核心|最重要|重要|必须关注|风险|结论|主判断|趋势)/u.test(tag) || /^(?:重点|关键|核心|最重要|重要|必须关注|风险|结论|主判断|趋势)/u.test(text);
  return {
    tag,
    text,
    tagClass: extractedTag ? "analysis-badge--accent" : "analysis-badge--slate",
    important,
  };
}

function parseNewsHighlights(value: string): Array<{ index: number; source: string; text: string }> {
  const lines = splitSummaryLines(value);
  const markerIndex = lines.findIndex((line) => line.includes("代表性标题"));
  if (markerIndex < 0) {
    return [];
  }

  return lines
    .slice(markerIndex + 1)
    .map((line) => line.replace(/^\-\s*/, "").trim())
    .filter((line) => line.length > 0)
    .map((line, index) => {
      const match = line.match(/^(?<source>[^:：]{1,32})[:：]\s*(?<text>.+)$/u);
      return {
        index: index + 1,
        source: match?.groups?.source?.trim() || "新闻",
        text: (match?.groups?.text ?? line).trim(),
      };
    });
}

function buildInsightDisplay(value: string): {
  focusTag: string;
  primaryReason: string;
  primaryBadgeLabel: string;
  primaryBadgeClass: string;
  primaryReasonClass: string;
  highlightLead: boolean;
  secondaryReasons: Array<{
    tag: string;
    text: string;
    tagClass: string;
    important: boolean;
  }>;
} {
  const items = splitSummaryLines(value).map((line) => parseInsightLine(line, "主判断"));
  const primary = items[0] ?? parseInsightLine("当前暂无判断。");
  const secondaryReasons = items.slice(1);
  const focusItem = secondaryReasons.find((item) => item.important || item.tag !== "补充判断" && item.tag !== "主判断");
  return {
    focusTag: focusItem ? focusItem.tag : "",
    primaryReason: primary.text,
    primaryBadgeLabel: primary.tag,
    primaryBadgeClass: primary.tagClass,
    primaryReasonClass: primary.important ? "summary-lead--featured" : "",
    highlightLead: primary.important,
    secondaryReasons,
  };
}

function splitEvidenceLines(value: string): string[] {
  const normalized = value.replace(/\r\n/g, "\n").trim();
  if (!normalized) {
    return [];
  }

  const rawLines = normalized.includes("\n")
    ? normalized.split("\n")
    : normalized.split(/[。！？；;]/);

  return rawLines
    .map((line) => line.replace(/^\-\s*/, "").trim())
    .filter((line) => line.length > 0);
}

function getMarketSessionLabel(now: Date = new Date()): string {
  const utcDay = now.getUTCDay();
  const minutes = now.getUTCHours() * 60 + now.getUTCMinutes();
  const fridayClose = 22 * 60;
  const japanEnd = 7 * 60;
  const europeEnd = 8 * 60;
  const londonEnd = 13 * 60 + 30;
  const usEnd = 21 * 60;

  if (utcDay === 6) {
    return "周末 / 非交易时段";
  }
  if (utcDay === 5 && minutes >= fridayClose) {
    return "周末 / 非交易时段";
  }
  if (utcDay === 0 && minutes < fridayClose) {
    return "周末 / 非交易时段";
  }
  if (minutes >= 13 * 60 + 30 && minutes < usEnd) {
    return "美国市";
  }
  if (minutes >= 8 * 60 && minutes < londonEnd) {
    return "伦敦市";
  }
  if (minutes >= japanEnd && minutes < europeEnd) {
    return "欧洲市";
  }
  return "日本市";
}

function summaryBadge(key: string): string {
  const badgeMap: Record<string, string> = {
    technical_summary: "技术",
    macro_summary: "宏观",
    news_summary: "新闻",
    market_sentiment_summary: "情绪",
    alt_data_summary: "另类",
    risk_summary: "风险",
  };

  return badgeMap[key] ?? "重点";
}

function summaryAccentClass(key: string): string {
  const accentMap: Record<string, string> = {
    technical_summary: "summary-card--teal",
    macro_summary: "summary-card--blue",
    news_summary: "summary-card--amber",
    market_sentiment_summary: "summary-card--lime",
    alt_data_summary: "summary-card--cyan",
    risk_summary: "summary-card--rose",
  };

  return accentMap[key] ?? "summary-card--slate";
}

function summaryStanceLabel(key: string, content: string): string {
  const lowerContent = content.toLowerCase();
  if (key === "risk_summary") {
    return "中性 / 防守";
  }
  if (lowerContent.includes("看空") || lowerContent.includes("bearish") || content.includes("偏空") || content.includes("压力")) {
    return "看空";
  }
  if (lowerContent.includes("看多") || lowerContent.includes("bullish") || content.includes("偏多") || content.includes("支撑")) {
    return "看多";
  }
  if (content.includes("中性") || content.includes("震荡") || content.includes("暂不可用")) {
    return "中性";
  }
  return "中性";
}

function summaryStanceClass(key: string, content: string): string {
  const stance = summaryStanceLabel(key, content);
  if (stance === "看多") {
    return "summary-stance--bullish";
  }
  if (stance === "看空") {
    return "summary-stance--bearish";
  }
  return "summary-stance--neutral";
}

function summaryStanceTagLabel(key: string, content: string): string {
  const stance = summaryStanceLabel(key, content);
  if (stance === "看多") {
    return "偏多";
  }
  if (stance === "看空") {
    return "偏空";
  }
  return key === "risk_summary" ? "防守" : "中性";
}

function riskNoteTag(note: string): string {
  if (isDiagnosticRiskNote(note)) {
    return "诊断";
  }
  if (note.includes("ATR") || note.includes("止损") || note.includes("止盈")) {
    return "波动";
  }
  if (note.includes("缺失") || note.includes("不可用")) {
    return "缺失";
  }

  return "提示";
}

function riskNoteToneClass(note: string): string {
  if (isDiagnosticRiskNote(note)) {
    return "risk-note-card--warning";
  }
  if (note.includes("ATR")) {
    return "risk-note-card--accent";
  }
  return "risk-note-card--neutral";
}

function isDiagnosticRiskNote(note: string): boolean {
  return /^OpenAI-compatible\s+.+\s+agent\s+/.test(note) || note.includes("调用失败") || note.includes("回退");
}

onMounted(() => {
  marketSessionTimer = window.setInterval(() => {
    marketSessionClock.value = new Date();
  }, 60_000);

  void loadStaticData();
  void refreshLiveData();
  liveRefreshTimer = window.setInterval(() => {
    void refreshLiveData({ background: true });
  }, 60_000);
});

onBeforeUnmount(() => {
  if (marketSessionTimer !== null) {
    window.clearInterval(marketSessionTimer);
    marketSessionTimer = null;
  }
  if (liveRefreshTimer !== null) {
    window.clearInterval(liveRefreshTimer);
    liveRefreshTimer = null;
  }
});
</script>
