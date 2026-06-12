<template>
    <div>
        <h2>菜单测试</h2>

        <pre>{{ menus }}</pre>
    </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { getMenus } from "@/api/menu";

const menus = ref([]);

onMounted(async () => {
    const res = await getMenus();

    if (res.success) {
        menus.value = res.data;
    }
});
</script>