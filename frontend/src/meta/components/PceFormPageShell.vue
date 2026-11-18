<template>
  <main class="pce-page-shell" data-acceptance-id="pce-form-page-shell" data-pce-shell-type="PceFormPageShell">
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
