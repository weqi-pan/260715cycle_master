<template>
  <div v-if="frame" class="play">
    <StatusBar
      :cycle-count="frame.state.cycleCount"
      :half-cycle-count="frame.state.halfCycleCount"
      :attributes="frame.state.playerAttributes"
      :inventory="frame.state.inventory"
      :node-name="frame.node.name"
      :busy="busy"
      @toggle-backpack="store.toggleBackpack"
      @save="showSaves = true"
      @open-saves="openSaves"
    />
    <div class="layout">
      <main class="stage">
        <div class="scene" :class="{ transitioning }">
          <h1>{{ frame.node.name }}</h1>
          <p v-if="frame.node.timeLabel" class="time">{{ frame.node.timeLabel }}</p>
        </div>
        <article class="playback">
          <div v-for="block in timeline" :key="`${block.id}-${block.text}`" class="block" :class="block.type">
            <strong v-if="block.type === 'dialogue' && block.speakerId">{{ speakerName(block.speakerId) }}</strong>
            <p>{{ block.text }}</p>
          </div>
        </article>
        <section class="choices">
          <button
            v-for="choice in choices"
            :key="choice.id"
            type="button"
            :disabled="!canAct || !choice.available"
            @click="choose(choice.id)"
          >
            <span>{{ choice.text }}</span>
            <small v-if="choice.reason">{{ choice.reason }}</small>
          </button>
        </section>
        <p v-if="error" class="error">{{ error }}</p>
        <p v-if="fatal" class="error">连接异常，请读取手动存档或重新开始。</p>
      </main>
      <InventoryDrawer v-if="openBackpack" :items="frame.state.inventory" :busy="busy" @discard="discard" />
    </div>
    <CycleMap
      class="map"
      :current-id="frame.state.currentNodeId"
      :visited-ids="frame.state.visitedNodes"
    />
    <SavesDialog
      v-if="showSaves"
      :saves="saves"
      :busy="busy"
      @close="showSaves = false"
      @load="load"
      @save="save"
      @remove="remove"
    />
  </div>
  <div v-else class="empty">
    <p>当前没有运行中的回合。</p>
    <RouterLink to="/">返回开始页</RouterLink>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import StatusBar from '../components/player/StatusBar.vue'
import CycleMap from '../components/player/CycleMap.vue'
import InventoryDrawer from '../components/player/InventoryDrawer.vue'
import SavesDialog from '../components/player/SavesDialog.vue'
import { gameApi } from '../features/game/api'
import { useGameStore } from '../stores/gameStore'
import { speakerDisplayName } from '../lib/playbackTimeline'
import { orderedChoices } from '../lib/choiceVisibility'

const store = useGameStore()
const { frame, timeline, busy, error, fatal, saves, canAct, openBackpack } = storeToRefs(store)
const showSaves = ref(false)
const transitioning = computed(() => Boolean(frame.value?.resultBlocks.length))

const choices = computed(() => orderedChoices(frame.value?.choices ?? []))

onMounted(() => { void store.refreshSaves() })

function speakerName(speakerId: string): string { return speakerDisplayName(speakerId, frame.value?.speakerNames ?? {}) }
function choose(choiceId: string): void { void store.choose(choiceId) }
function discard(itemId: string): void { void store.discard(itemId) }
function openSaves(): void { void store.refreshSaves(); showSaves.value = true }
function load(saveId: string): void { void store.resume(saveId).then(() => { showSaves.value = false }) }
function save(name: string): void { store.saveName = name; void store.save().then(() => { showSaves.value = false }) }
function remove(saveId: string): void { void store.deleteSave(saveId) }
</script>

<style scoped>
.play { min-height: 100vh; background: radial-gradient(circle at 50% 20%, #171310, #060505); color: #efe6d3; }
.layout { display: flex; min-height: calc(100vh - 53px); }
.stage { flex: 1; padding: 28px 48px 110px; max-width: 920px; margin: auto; }
.scene { min-height: 170px; display: grid; align-content: center; justify-items: center; text-align: center; }
.scene h1 { margin: 0; font-size: clamp(26px, 4vw, 42px); color: #d9b868; }
.time { color: #9d9284; margin: 5px 0 0; }
.playback { min-height: 220px; padding: 22px; background: rgba(11,10,9,.66); border: 1px solid rgba(184,148,62,.12); }
.block p { margin: 0; line-height: 1.75; color: #d8cdb8; }
.block.dialogue { border-left: 2px solid rgba(184,148,62,.45); padding-left: 12px; }
.block.dialogue strong { color: #b8943e; }
.block.system p { color: #b3a996; font-size: 14px; }
.block.check_result p { color: #f0d59b; }
.choices { display: grid; gap: 10px; margin-top: 22px; }
.choices button { display: grid; gap: 4px; padding: 13px 16px; text-align: left; color: #e8ddc6; border: 1px solid rgba(184,148,62,.18); background: rgba(184,148,62,.05); cursor: pointer; }
.choices button:hover:not(:disabled) { border-color: #b8943e; color: #ffedbe; }
.choices small { color: #9d9284; }
.map { position: fixed; right: 20px; bottom: 20px; z-index: 15; }
.empty { min-height: 100vh; display: grid; place-content: center; color: #b3a996; gap: 12px; }
.error { color: #e6a68f; }
</style>
