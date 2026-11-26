<template>
  <main class="pce-page-shell" data-acceptance-id="pce-detail-page-shell" data-pce-shell-type="PceDetailPageShell">
    <slot />
  </main>
</template>

<style scoped>
.pce-page-shell {
  display: block;
  min-width: 0;
  max-width: 100%;
}
</style>
