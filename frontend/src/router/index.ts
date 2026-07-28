import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "home",
      component: () => import("@/views/HomeView.vue"),
    },
    {
      path: "/devices",
      name: "devices",
      component: () => import("@/views/DevicesView.vue"),
    },
    {
      path: "/groups",
      name: "groups",
      component: () => import("@/views/GroupsView.vue"),
    },
    {
      path: "/calendars",
      name: "calendars",
      component: () => import("@/views/CalendarsView.vue"),
    },
  ],
});

export default router;
