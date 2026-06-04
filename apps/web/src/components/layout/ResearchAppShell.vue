<template>
  <div class="app-shell">
    <div class="app-shell__frame">
      <aside class="app-shell__sidebar">
        <div class="app-shell__stack">
          <div class="app-shell__brand-card">
            <p class="app-shell__brand-kicker">GoldFXGraph</p>
            <h1 class="app-shell__brand-title">
              黄金研究决策台
            </h1>
            <p class="app-shell__brand-subtitle">
              AI-native
            </p>
            <p class="app-shell__brand-page">
              当前页面 · {{ currentRouteLabel }}
            </p>
          </div>

          <nav class="app-shell__nav" aria-label="主导航">
            <RouterLink
              v-for="item in navigation"
              :key="item.to"
              :to="item.to"
              class="app-shell__nav-link"
              :class="route.path === item.to ? activeLinkClass : inactiveLinkClass"
            >
              <div class="space-y-1">
                <p class="app-shell__nav-label">{{ item.label }}</p>
                <p class="app-shell__nav-copy">{{ item.description }}</p>
              </div>
              <span
                class="app-shell__nav-badge"
                :class="route.path === item.to ? 'app-shell__nav-badge--active' : 'app-shell__nav-badge--inactive'"
              >
                {{ item.short }}
              </span>
            </RouterLink>
          </nav>

          <div class="app-shell__guide">
            <p class="app-shell__guide-kicker">Guidance</p>
            <p class="mt-2">
              先看结论，再看执行计划，随后进入轨迹与验证。
            </p>
          </div>
        </div>
      </aside>

      <main class="min-w-0">
        <div class="px-4 py-4 sm:px-5 sm:py-5 lg:px-6 lg:py-6">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, useRoute } from "vue-router";

const route = useRoute();

const navigation = [
  {
    to: "/",
    label: "研究总览",
    description: "价格、方向、执行建议",
    short: "01",
  },
  {
    to: "/workflow-trace",
    label: "节点轨迹",
    description: "执行轨迹与 prompt",
    short: "02",
  },
];

const activeLinkClass = "app-shell__nav-link--active";
const inactiveLinkClass = "app-shell__nav-link--inactive";

const currentRouteLabel = computed(() => navigation.find((item) => item.to === route.path)?.label ?? "GoldFXGraph");
</script>
