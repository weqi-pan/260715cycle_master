<!-- SpeakerHeader.vue — avatar + speaker name -->
<template>
  <div v-if="speaker" class="speaker-header">
    <div class="speaker-avatar">
      <img v-if="avatar" :src="avatar" :alt="speaker" class="avatar-img" />
      <span v-else class="avatar-placeholder">{{ speaker[0] }}</span>
    </div>
    <span class="speaker-name">{{ speaker }}</span>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  speaker: string | null
  avatar: string | null
}>()
</script>

<style scoped lang="scss">
@import '@/assets/styles/variables.scss';

.speaker-header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.6rem;
}

.speaker-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  overflow: hidden;
  border: 1px solid rgba($accent-gold, 0.3);
  flex-shrink: 0;
  background: rgba($accent-gold, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-placeholder {
  color: $accent-gold;
  font-family: $font-display;
  font-size: 1.1rem;
  font-weight: 600;
}

.speaker-name {
  color: $accent-gold;
  font-family: $font-ui;
  font-size: 0.9rem;
  font-weight: 500;
}
</style>
