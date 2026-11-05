import { createRouter, createWebHistory } from "vue-router";

import PlaceholderView from "../views/PlaceholderView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/projects" },
    { path: "/projects", name: "projects", component: PlaceholderView },
    { path: "/:pathMatch(.*)*", name: "not-found", component: PlaceholderView },
  ],
});
