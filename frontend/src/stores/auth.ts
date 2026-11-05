import { defineStore } from "pinia";

import { login as loginRequest, me, register as registerRequest } from "../api/auth";
import { setAuthToken } from "../api/client";
import type { User } from "../api/types";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: null as string | null,
    user: null as User | null,
  }),
  getters: {
    isAuthenticated: (state) => state.token !== null,
  },
  actions: {
    async login(username: string, password: string): Promise<void> {
      const response = await loginRequest(username, password);
      setAuthToken(response.access_token);
      this.token = response.access_token;
      this.user = await me();
    },
    async register(username: string, password: string): Promise<void> {
      await registerRequest(username, password);
      await this.login(username, password);
    },
    clear(): void {
      setAuthToken(null);
      this.token = null;
      this.user = null;
    },
    logout(): void {
      this.clear();
    },
  },
});
