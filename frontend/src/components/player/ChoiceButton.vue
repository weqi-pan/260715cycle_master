<!-- frontend/src/components/player/ChoiceButton.vue — 符纸风格 -->
<template>
  <button
    class="choice-btn"
    :class="{
      locked: !choice.available,
      warp: choice.source === 'special_warp',
    }"
    :disabled="!choice.available"
    @click="$emit('select', choice.id)"
  >
    <span class="choice-text">{{ choice.text }}</span>
    <span v-if="!choice.available && choice.reason" class="choice-reason">
      <span class="reason-icon">✕</span> {{ choice.reason }}
    </span>
    <span v-if="choice.source === 'special_warp'" class="warp-tag">跃迁</span>
  </button>
</template>

<script setup lang="ts">
import type { ChoiceResult } from '@/types'

defineProps<{ choice: ChoiceResult }>()
defineEmits<{ select: [id: string] }>()
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables.scss' as *;

.choice-btn {
  display: block;
  width: 100%;
  padding: 0.9rem 1.4rem;
  margin-bottom: 0.5rem;
  background: linear-gradient(135deg, rgba(26,20,16,0.95) 0%, rgba(30,24,18,0.9) 100%);
  border: 1px solid rgba($accent-gold, 0.18);
  border-left: 3px solid rgba($accent-gold, 0.35);
  color: $text-primary;
  font-family: $font-body;
  font-size: 0.98rem;
  cursor: pointer;
  text-align: left;
  transition: all 0.25s ease;
  position: relative;

  &:hover:not(.locked) {
    border-color: rgba($accent-gold, 0.5);
    border-left-color: $accent-gold;
    background: linear-gradient(135deg, rgba(36,28,20,0.95) 0%, rgba(40,30,22,0.9) 100%);
    transform: translateX(2px);
  }

  &:active:not(.locked) {
    transform: translateX(1px);
  }

  &.locked {
    border-color: rgba($text-dim, 0.2);
    border-left-color: rgba($text-dim, 0.25);
    cursor: default;

    .choice-text {
      color: $text-dim;
    }
  }

  &.warp {
    border-color: rgba($accent-ghost, 0.35);
    border-left-color: rgba($accent-ghost, 0.6);
    border-style: dashed;
    background: linear-gradient(135deg, rgba(13,16,20,0.95) 0%, rgba(16,20,26,0.9) 100%);

    &:hover:not(.locked) {
      border-color: rgba($accent-ghost, 0.6);
      background: linear-gradient(135deg, rgba(20,24,30,0.95) 0%, rgba(24,28,34,0.9) 100%);
    }
  }
}

.choice-text {
  display: block;
  letter-spacing: 0.03em;
}

.choice-reason {
  display: block;
  margin-top: 0.4rem;
  padding-top: 0.35rem;
  border-top: 1px dotted rgba($text-dim, 0.25);
  font-family: $font-ui;
  font-size: 0.78rem;
  color: $text-dim;
  line-height: 1.5;
}

.reason-icon {
  color: rgba($accent-red, 0.5);
  font-size: 0.7rem;
}

.warp-tag {
  position: absolute;
  right: 0.8rem;
  top: 50%;
  transform: translateY(-50%);
  font-family: $font-ui;
  font-size: 0.65rem;
  color: rgba($accent-ghost, 0.6);
  border: 1px solid rgba($accent-ghost, 0.25);
  padding: 0.1rem 0.4rem;
  border-radius: 2px;
}
</style>
