import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "@/App.vue";
import router from "@/router";

import "@/style.css";

const app = createApp(App);

// No stores defined yet (src/stores/ is empty) -- kept wired in for the
// IS_MASTER/whoami global UI-gating state item 9 will need.
app.use(createPinia());
app.use(router);

app.mount("#app");
