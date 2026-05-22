import { createRouter, createWebHistory } from "vue-router";

import GoldForecastDashboard from "@/pages/GoldForecastDashboard.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "gold-forecast-dashboard",
      component: GoldForecastDashboard,
    },
  ],
});

export default router;
