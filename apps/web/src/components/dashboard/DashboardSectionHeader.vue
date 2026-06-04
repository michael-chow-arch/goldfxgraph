<template>
  <header class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
    <div class="space-y-2">
      <p v-if="eyebrow" class="panel-title">{{ eyebrow }}</p>
      <component :is="headingTag" class="section-heading">{{ title }}</component>
      <p v-if="description" class="section-copy max-w-3xl">
        {{ description }}
      </p>
      <slot name="supporting" />
    </div>

    <div v-if="$slots.actions || badge" class="flex items-center gap-3">
      <slot name="actions">
        <span v-if="badge" class="section-header__badge">
          {{ badge }}
        </span>
      </slot>
    </div>
  </header>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    eyebrow?: string;
    description?: string;
    badge?: string;
    headingTag?: "h2" | "h3";
  }>(),
  {
    eyebrow: "",
    description: "",
    badge: "",
    headingTag: "h2",
  },
);
</script>
