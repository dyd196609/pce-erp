import { defineStore } from "pinia";

export const useMenuStore = defineStore("menu", {
    state: () => ({
        menus: [],
    }),

    actions: {
        setMenus(data) {
            this.menus = data;
        },

        clearMenus() {
            this.menus = [];
        },
    },
});