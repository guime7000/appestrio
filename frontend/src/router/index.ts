import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "inauguration",
      component: () => import("@/views/InaugurationView.vue"),
    },
    {
      path: "/configuration",
      name: "configuration",
      component: () => import("@/views/ConfigurationView.vue"),
      redirect: { name: "configuration-devices" },
      children: [
        {
          path: "appareils",
          name: "configuration-devices",
          component: () => import("@/views/DevicesView.vue"),
        },
        {
          path: "groupes",
          name: "configuration-groups",
          component: () => import("@/views/GroupsView.vue"),
        },
        {
          path: "calendriers",
          name: "configuration-calendars",
          component: () => import("@/views/CalendarsView.vue"),
        },
        {
          path: "horloges",
          name: "configuration-clocks",
          component: () => import("@/views/HorlogesView.vue"),
        },
      ],
    },
  ],
});

export default router;
