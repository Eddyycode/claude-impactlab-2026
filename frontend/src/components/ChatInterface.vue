<script setup>
import { nextTick, ref, watch } from 'vue';
import { useChat } from '../composables/useChat';
import ScoreCard from './ScoreCard.vue';
import RiskMap from './RiskMap.vue';

const { isTyping, messages, sendMessage } = useChat();
const userInput = ref('');
const messagesContainer = ref(null);

const onSubmit = async () => {
  if (!userInput.value.trim() || isTyping.value) return;
  const text = userInput.value;
  userInput.value = '';
  await sendMessage(text);
};

watch(messages, async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
}, { deep: true });
</script>

<template>
  <div class="chat-interface">
    <div class="chat-messages" ref="messagesContainer">

      <!-- Empty state -->
      <div v-if="messages.length === 0" class="empty-state">
        <div class="empty-icon">🏙️</div>
        <h2>¿Dónde quieres vivir en <span class="accent-orange">CDMX</span>?</h2>
        <p>
          Escribe una colonia o dirección. Te doy un análisis de calidad de vida
          basado en <strong>datos abiertos del gobierno</strong>.
        </p>
        <div class="suggestions">
          <button @click="userInput = 'Narvarte Poniente'; onSubmit()">🏘 Narvarte Poniente</button>
          <button @click="userInput = 'Roma Norte'; onSubmit()">☕ Roma Norte</button>
          <button @click="userInput = 'Coyoacán Centro'; onSubmit()">🌳 Coyoacán Centro</button>
        </div>
      </div>

      <!-- Messages -->
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        class="message-wrapper"
        :class="msg.role"
      >
        <div class="message-bubble">
          <div class="content" v-html="msg.content"></div>
        </div>

        <!-- Report block -->
        <div v-if="msg.reportData" class="report-container">

          <!-- Global score header -->
          <div class="global-score-bar">
            <div class="gsb-left">
              <span class="gsb-icon">📍</span>
              <h3>{{ msg.reportData.direccion }}</h3>
            </div>
            <div class="global-badge">
              <strong>{{ msg.reportData.scores.global.toFixed(1) }}</strong>
              <span class="badge-sep">/10</span>
              <span class="badge-label">{{ msg.reportData.scores.etiqueta_global }}</span>
            </div>
          </div>

          <!-- Map -->
          <RiskMap
            v-if="msg.reportData.lat && msg.reportData.lng"
            :lat="msg.reportData.lat"
            :lng="msg.reportData.lng"
          />

          <!-- Summary -->
          <div class="resume-box" v-html="msg.reportData.resumen"></div>

          <!-- Score grid -->
          <div class="dimensions-grid">
            <ScoreCard
              v-for="dim in msg.reportData.scores.dimensiones"
              :key="dim.id"
              :dimension="dim.nombre"
              :score="dim.score"
              :peso="dim.peso_aplicado"
              :fuente="dim.fuente"
              :consultadoEn="dim.consultado_en"
              :datoBruto="dim.dato_bruto"
              :detalle="dim.detalle"
            />
          </div>

          <!-- Missing dimensions -->
          <div v-if="msg.reportData.scores.faltantes?.length" class="missing-data">
            <h4>⚠ Dimensiones sin datos</h4>
            <ul>
              <li v-for="f in msg.reportData.scores.faltantes" :key="f.id">
                <strong>{{ f.id }}:</strong> {{ f.razon }}
              </li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Typing indicator -->
      <div v-if="isTyping" class="message-wrapper assistant">
        <div class="message-bubble">
          <div class="typing-indicator">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>
    </div>

    <!-- Input bar -->
    <div class="input-wrapper">
      <form class="chat-input-area" @submit.prevent="onSubmit">
        <input
          type="text"
          v-model="userInput"
          placeholder="Escribe una colonia o dirección de CDMX..."
          :disabled="isTyping"
          class="main-input"
          autocomplete="off"
        />
        <button type="submit" :disabled="isTyping || !userInput.trim()" class="send-btn">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20"
            fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
/* ── Shell ── */
.chat-interface {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: transparent;
  color: #1a1a1a;
  font-family: 'Inter', sans-serif;
  overflow: hidden;
}

/* ── Messages area ── */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 36px 20px 20px;
  display: flex;
  flex-direction: column;
  gap: 28px;
  scrollbar-width: thin;
  scrollbar-color: #d1d5db transparent;
}

/* ── Empty state ── */
.empty-state {
  margin: auto;
  text-align: center;
  max-width: 480px;
  padding: 32px 20px;
}

.empty-icon {
  font-size: 3.5rem;
  margin-bottom: 20px;
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}

.empty-state h2 {
  font-size: 1.9rem;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: #111827;
  margin-bottom: 12px;
}

.accent-orange { color: #f97316; }

.empty-state p {
  color: #6b7280;
  line-height: 1.65;
  font-size: 0.97rem;
  margin-bottom: 28px;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}

.suggestions button {
  background: rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(8px);
  border: 1px solid #1a1a1a22;
  color: #374151;
  padding: 9px 18px;
  border-radius: 50px;
  cursor: pointer;
  font-size: 0.9rem;
  font-family: 'Inter', sans-serif;
  transition: all 0.2s;
  font-weight: 500;
}

.suggestions button:hover {
  background: #f97316;
  color: white;
  border-color: #f97316;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(249, 115, 22, 0.3);
}

/* ── Message wrappers ── */
.message-wrapper {
  display: flex;
  flex-direction: column;
  max-width: 820px;
  width: 100%;
  margin: 0 auto;
}
.message-wrapper.user    { align-items: flex-end; }
.message-wrapper.assistant { align-items: flex-start; }

/* ── Bubbles ── */
.message-bubble {
  max-width: 78%;
  padding: 14px 20px;
  border-radius: 20px;
  line-height: 1.55;
  font-size: 0.97rem;
}

.user .message-bubble {
  background: #f97316;
  color: white;
  border-bottom-right-radius: 4px;
  border: 1px solid #ea6c0e;
  box-shadow: 0 2px 8px rgba(249,115,22,0.25);
}

.assistant .message-bubble {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(8px);
  border: 1px solid #1a1a1a1a;
  color: #1f2937;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.content { margin: 0; }

/* ── Markdown-rendered content inside bubbles ── */
.content :deep(h1),
.content :deep(h2),
.content :deep(h3) {
  margin: 14px 0 8px 0;
  font-weight: 700;
  color: #111827;
  line-height: 1.3;
}
.content :deep(h2) { font-size: 1.05rem; }
.content :deep(h3) { font-size: 0.98rem; }
.content :deep(h1:first-child),
.content :deep(h2:first-child),
.content :deep(h3:first-child) { margin-top: 0; }

.content :deep(p) {
  margin: 0 0 10px 0;
  line-height: 1.55;
}
.content :deep(p:last-child) { margin-bottom: 0; }

.content :deep(strong) { font-weight: 700; color: #111827; }
.content :deep(em)     { font-style: italic; color: #4b5563; }

.content :deep(ul),
.content :deep(ol) {
  margin: 8px 0 12px 0;
  padding-left: 22px;
}
.content :deep(li)     { margin-bottom: 4px; line-height: 1.5; }

.content :deep(hr) {
  border: none;
  border-top: 1px solid #1a1a1a20;
  margin: 14px 0;
}

.content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0;
  font-size: 0.88rem;
  background: rgba(255,255,255,0.5);
  border-radius: 8px;
  overflow: hidden;
}
.content :deep(th),
.content :deep(td) {
  padding: 8px 12px;
  text-align: left;
  border-bottom: 1px solid #1a1a1a15;
}
.content :deep(th) {
  background: rgba(249, 115, 22, 0.08);
  font-weight: 700;
  color: #111827;
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
.content :deep(tr:last-child td) { border-bottom: none; }

.content :deep(code) {
  background: rgba(17,24,39,0.08);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 0.88em;
}
.content :deep(blockquote) {
  margin: 10px 0;
  padding: 6px 14px;
  border-left: 3px solid #f97316;
  background: rgba(249,115,22,0.06);
  color: #4b5563;
  border-radius: 0 6px 6px 0;
}

/* Burbujas del user: invertir paleta porque fondo es naranja */
.user .content :deep(h1),
.user .content :deep(h2),
.user .content :deep(h3),
.user .content :deep(strong) { color: white; }

/* ── Typing dots ── */
.typing-indicator {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 2px 4px;
}

.typing-indicator span {
  display: inline-block;
  width: 8px;
  height: 8px;
  background-color: #9ca3af;
  border-radius: 50%;
  animation: dot-bounce 1.4s infinite ease-in-out both;
}
.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

/* ── Report block ── */
.report-container {
  width: 100%;
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* Global score bar */
.global-score-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
  border: 1px solid #1a1a1a1a;
  padding: 16px 22px;
  border-radius: 14px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.05);
}

.gsb-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.gsb-icon { font-size: 1.3rem; }

.global-score-bar h3 {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 700;
  color: #111827;
  letter-spacing: -0.02em;
}

.global-badge {
  display: flex;
  align-items: baseline;
  gap: 6px;
  background: linear-gradient(135deg, #22c55e, #16a34a);
  padding: 8px 18px;
  border-radius: 50px;
  color: white;
  border: 1px solid #15803d44;
  box-shadow: 0 2px 8px rgba(34,197,94,0.25);
}

.global-badge strong {
  font-size: 1.4rem;
  font-weight: 800;
}

.badge-sep {
  font-size: 0.9rem;
  opacity: 0.75;
}

.badge-label {
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding-left: 4px;
  border-left: 1px solid rgba(255,255,255,0.4);
  margin-left: 4px;
}

/* Summary box */
.resume-box {
  background: rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(8px);
  padding: 20px 22px;
  border-radius: 12px;
  border: 1px solid #1a1a1a1a;
  border-left: 3px solid #f97316;
  line-height: 1.65;
  color: #374151;
  font-size: 0.94rem;
}
.resume-box :deep(h3) {
  margin-top: 0;
  color: #111827;
  font-size: 1rem;
  font-weight: 700;
}

/* Score cards grid */
.dimensions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}

/* Missing data */
.missing-data {
  background: rgba(254, 243, 199, 0.7);
  border: 1px dashed #fbbf24;
  padding: 14px 18px;
  border-radius: 10px;
  color: #92400e;
  font-size: 0.88rem;
}
.missing-data h4 {
  margin: 0 0 8px 0;
  color: #b45309;
  font-weight: 700;
}
.missing-data ul { margin: 0; padding-left: 18px; }
.missing-data li { margin-bottom: 4px; }

/* ── Input bar ── */
.input-wrapper {
  padding: 16px 20px 20px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(14px);
  border-top: 1px solid #1a1a1a15;
}

.chat-input-area {
  display: flex;
  gap: 10px;
  align-items: center;
  max-width: 820px;
  margin: 0 auto;
}

.main-input {
  flex: 1;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid #1a1a1a22;
  padding: 14px 22px;
  border-radius: 50px;
  color: #111827;
  font-size: 0.97rem;
  font-family: 'Inter', sans-serif;
  transition: all 0.2s;
  outline: none;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.main-input::placeholder { color: #9ca3af; }

.main-input:focus {
  border-color: #f97316;
  box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.12);
}

.send-btn {
  background: #f97316;
  color: white;
  border: 1px solid #ea6c0e;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(249,115,22,0.3);
}

.send-btn:hover:not(:disabled) {
  background: #ea6c0e;
  transform: scale(1.06);
  box-shadow: 0 4px 14px rgba(249,115,22,0.4);
}

.send-btn:disabled {
  background: #e5e7eb;
  color: #9ca3af;
  border-color: #d1d5db;
  cursor: not-allowed;
  box-shadow: none;
}
</style>
