<!-- CharacterLayer.vue — z-10 character sprite area (placeholder) -->
<template>
  <div class="char-layer">
    <slot />
    <!-- Phase 2+: CharacterSprite components with entry/exit animations -->
  </div>
</template>

<style scoped lang="scss">
.char-layer {
  position: fixed;
  bottom: 35%;
  left: 0;
  right: 0;
  height: 60%;
  z-index: 10;
  display: flex;
  justify-content: center;
  align-items: flex-end;
  pointer-events: none;
}
</style>
