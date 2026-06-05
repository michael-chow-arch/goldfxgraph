<template>
  <RouterView v-slot="{ Component }">
    <ResearchAppShell>
      <component :is="Component" />
    </ResearchAppShell>
  </RouterView>
</template>

<script setup lang="ts">
import { RouterView } from "vue-router";
import ResearchAppShell from "@/components/layout/ResearchAppShell.vue";
</script>
