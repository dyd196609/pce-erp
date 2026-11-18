import { defineStore } from 'pinia';
import { terminateEnterpriseSession } from '../api/auth.js';
import { clearCurrentIdentity, rememberCurrentIdentity } from '../meta/runtime/pageTitleManager.js';
import { clearTabAuthentication, getTabAuthToken, setTabAuthToken } from '../meta/runtime/tabAuthenticationContext.js';

export const useUserStore = defineStore('user', {
  state: () => ({
    token: getTabAuthToken(),
    userInfo: null,
  }),
  actions: {
    setToken(token) {
      this.token = token;
      setTabAuthToken(token);
      window.dispatchEvent(new CustomEvent('pce:authentication-changed', {
        detail: { authenticated: Boolean(token) },
      }));
    },
    setUserInfo(info) {
      this.userInfo = info;
      rememberCurrentIdentity(info);
      window.dispatchEvent(new CustomEvent('pce:authentication-changed', {
        detail: { authenticated: true, userId: info?.id, username: info?.username },
      }));
    },
    async logout() {
      try {
        await terminateEnterpriseSession();
      } finally {
        this.token = '';
        this.userInfo = null;
        clearTabAuthentication();
        clearCurrentIdentity();
        window.dispatchEvent(new CustomEvent('pce:authentication-changed', {
          detail: { authenticated: false },
        }));
      }
    },
  },
});
