import { createRouter, createWebHistory } from "vue-router";

import GoldForecastDashboard from "@/pages/GoldForecastDashboard.vue";
import WorkflowTracePage from "@/pages/WorkflowTracePage.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "gold-forecast-dashboard",
      component: GoldForecastDashboard,
    },
    {
      path: "/workflow-trace",
      name: "workflow-trace",
      component: WorkflowTracePage,
    },
  ],
});

export default router;
