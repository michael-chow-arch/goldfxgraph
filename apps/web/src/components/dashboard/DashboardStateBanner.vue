<template>
  <section :class="bannerClass" :role="role" :aria-live="ariaLive">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      <div class="space-y-2">
        <p v-if="eyebrow" class="state-banner__eyebrow" :class="eyebrowClass">
          {{ eyebrow }}
        </p>
        <h2 class="section-heading">{{ title }}</h2>
        <p class="section-copy max-w-2xl">
          {{ message }}
        </p>
        <p v-if="detail" class="state-banner__detail">
          {{ detail }}
        </p>
        <slot name="supporting" />
      </div>

      <div v-if="$slots.actions" class="flex items-center gap-3">
        <slot name="actions" />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    title: string;
    message: string;
    detail?: string;
    eyebrow?: string;
    variant?: "loading" | "empty" | "error" | "stale";
  }>(),
  {
    detail: "",
    eyebrow: "",
    variant: "loading",
  },
);

const role = computed(() => (props.variant === "error" ? "alert" : "status"));
const ariaLive = computed(() => (props.variant === "error" ? "assertive" : "polite"));
const bannerClass = computed(() => [
  "dashboard-panel mt-5 rounded-[28px] px-5 py-8 sm:px-6",
  `research-state-banner research-state-banner--${props.variant}`,
]);
const eyebrowClass = computed(() => {
  if (props.variant === "error") {
    return "state-banner__eyebrow--error";
  }
  if (props.variant === "empty") {
    return "state-banner__eyebrow--empty";
  }
  if (props.variant === "stale") {
    return "state-banner__eyebrow--stale";
  }
  return "state-banner__eyebrow--loading";
});
</script>
