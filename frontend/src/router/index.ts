import { createRouter, createWebHistory } from "vue-router";

import ProjectLayout from "../layouts/ProjectLayout.vue";
import ApisView from "../views/ApisView.vue";
import CaseEditorView from "../views/CaseEditorView.vue";
import CasesView from "../views/CasesView.vue";
import EnvironmentsView from "../views/EnvironmentsView.vue";
import LoginView from "../views/LoginView.vue";
import OverviewView from "../views/OverviewView.vue";
import ProjectsView from "../views/ProjectsView.vue";
import RegisterView from "../views/RegisterView.vue";
import RunReportView from "../views/RunReportView.vue";
import RunsView from "../views/RunsView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/projects" },
    {
      path: "/auth/login",
      name: "login",
      component: LoginView,
      meta: { public: true },
    },
    {
      path: "/auth/register",
      name: "register",
      component: RegisterView,
      meta: { public: true },
    },
    { path: "/projects", name: "projects", component: ProjectsView },
    {
      path: "/projects/:projectId",
      component: ProjectLayout,
      redirect: (to) => ({ name: "overview", params: to.params }),
      children: [
        { path: "overview", name: "overview", component: OverviewView },
        {
          path: "environments",
          name: "environments",
          component: EnvironmentsView,
        },
        { path: "apis", name: "apis", component: ApisView },
        { path: "cases", name: "cases", component: CasesView },
        { path: "cases/new", name: "case-new", component: CaseEditorView },
        {
          path: "cases/:caseId/edit",
          name: "case-edit",
          component: CaseEditorView,
        },
        { path: "runs", name: "runs", component: RunsView },
      ],
    },
    { path: "/runs/:runId", name: "run-report", component: RunReportView },
    { path: "/:pathMatch(.*)*", redirect: "/projects" },
  ],
});

router.beforeEach(async (to) => {
  const { useAuthStore } = await import("../stores/auth");
  const auth = useAuthStore();
  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.meta.public && auth.isAuthenticated) {
    return { name: "projects" };
  }
  return true;
});
