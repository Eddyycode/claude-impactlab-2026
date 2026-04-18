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

// Scroll to bottom when messages change
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
      <div v-if="messages.length === 0" class="empty-state">
        <div class="icon-pulse"></div>
        <h2>Analizador Urbano CDMX</h2>
        <p>Escribe una colonia o dirección para conocer su calidad de vida objetiva basada en datos abiertos del gobierno.</p>
        <div class="suggestions">
          <button @click="userInput = 'Narvarte Poniente'; onSubmit()">Narvarte Poniente</button>
          <button @click="userInput = 'Roma Norte'; onSubmit()">Roma Norte</button>
          <button @click="userInput = 'Coyoacán Centro'; onSubmit()">Coyoacán Centro</button>
        </div>
      </div>

      <div 
        v-for="(msg, idx) in messages" 
        :key="idx"
        class="message-wrapper"
        :class="msg.role"
      >
        <div class="message-bubble">
          <p class="content" v-html="msg.content"></p>
        </div>

        <!-- Render Report Data if available in message -->
        <div v-if="msg.reportData" class="report-container">
          
          <div class="global-score-bar">
            <h3>{{ msg.reportData.direccion }}</h3>
            <div class="global-badge">
              <strong>{{ msg.reportData.scores.global.toFixed(1) }}</strong> / 10
              <span>{{ msg.reportData.scores.etiqueta_global }}</span>
            </div>
          </div>

          <RiskMap 
            v-if="msg.reportData.lat && msg.reportData.lng"
            :lat="msg.reportData.lat" 
            :lng="msg.reportData.lng" 
          />
          
          <div class="resume-box" v-html="msg.reportData.resumen"></div>

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

          <div v-if="msg.reportData.scores.faltantes?.length" class="missing-data">
            <h4>Faltaron datos para:</h4>
            <ul>
              <li v-for="f in msg.reportData.scores.faltantes" :key="f.id">
                <strong>{{ f.id }}:</strong> {{ f.razon }}
              </li>
            </ul>
          </div>
        </div>
      </div>

      <div v-if="isTyping" class="message-wrapper assistant">
        <div class="typing-indicator">
          <span></span><span></span><span></span>
        </div>
      </div>
    </div>

    <form class="chat-input-area" @submit.prevent="onSubmit">
      <input 
        type="text" 
        v-model="userInput" 
        placeholder="Ej. Colonia Del Valle Centro..." 
        :disabled="isTyping"
        class="main-input"
      />
      <button type="submit" :disabled="isTyping || !userInput.trim()" class="send-btn">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="22" y1="2" x2="11" y2="13"></line>
          <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
        </svg>
      </button>
    </form>
  </div>
</template>

<style scoped>
.chat-interface {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #0f172a;
  color: #f8fafc;
  font-family: 'Inter', sans-serif;
  overflow: hidden;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 30px 20px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.empty-state {
  margin: auto;
  text-align: center;
  max-width: 450px;
  padding: 40px 20px;
}

.icon-pulse {
  width: 60px;
  height: 60px;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  border-radius: 50%;
  margin: 0 auto 24px;
  animation: pulse 2s infinite cubic-bezier(0.4, 0, 0.6, 1);
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.5); }
  70% { box-shadow: 0 0 0 20px rgba(59, 130, 246, 0); }
  100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
}

.empty-state h2 {
  font-size: 1.8rem;
  margin-bottom: 12px;
  font-weight: 700;
  background: -webkit-linear-gradient(#f8fafc, #94a3b8);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.empty-state p {
  color: #94a3b8;
  line-height: 1.6;
  margin-bottom: 30px;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}

.suggestions button {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  color: #cbd5e1;
  padding: 8px 16px;
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.suggestions button:hover {
  background: rgba(255,255,255,0.1);
  border-color: rgba(255,255,255,0.3);
  transform: translateY(-2px);
}

.message-wrapper {
  display: flex;
  flex-direction: column;
  max-width: 900px;
  width: 100%;
  margin: 0 auto;
}

.message-wrapper.user {
  align-items: flex-end;
}

.message-wrapper.assistant {
  align-items: flex-start;
}

.message-bubble {
  max-width: 80%;
  padding: 16px 20px;
  border-radius: 18px;
  line-height: 1.5;
  font-size: 1rem;
}

.user .message-bubble {
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: white;
  border-bottom-right-radius: 4px;
}

.assistant .message-bubble {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #e2e8f0;
  border-bottom-left-radius: 4px;
}

.content { margin: 0; }

.typing-indicator span {
  display: inline-block;
  width: 8px;
  height: 8px;
  background-color: #94a3b8;
  border-radius: 50%;
  margin: 0 2px;
  animation: bounce 1.4s infinite ease-in-out both;
}

.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.report-container {
  width: 100%;
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.global-score-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 16px 24px;
  border-radius: 12px;
}

.global-score-bar h3 {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 600;
  color: #f8fafc;
}

.global-badge {
  background: linear-gradient(135deg, #10b981, #059669);
  padding: 8px 16px;
  border-radius: 30px;
  color: white;
  display: flex;
  align-items: center;
  gap: 8px;
}

.global-badge strong { font-size: 1.2rem; }
.global-badge span { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }

.resume-box {
  background: rgba(255, 255, 255, 0.03);
  padding: 20px;
  border-radius: 12px;
  border-left: 4px solid #3b82f6;
  line-height: 1.6;
  color: #cbd5e1;
}
.resume-box :deep(h3) { margin-top: 0; color: white; font-size: 1.1rem; }

.dimensions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.missing-data {
  background: rgba(239, 68, 68, 0.1);
  border: 1px dashed rgba(239, 68, 68, 0.3);
  padding: 16px;
  border-radius: 8px;
  color: #fca5a5;
  font-size: 0.9rem;
}

.missing-data h4 { margin: 0 0 10px 0; color: #f87171; }
.missing-data ul { margin: 0; padding-left: 20px; }
.missing-data li { margin-bottom: 4px; }

.chat-input-area {
  padding: 20px;
  background: #0f172a;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  gap: 12px;
  align-items: center;
  max-width: 900px;
  width: 100%;
  margin: 0 auto;
}

.main-input {
  flex: 1;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 16px 24px;
  border-radius: 30px;
  color: white;
  font-size: 1rem;
  transition: all 0.2s;
  outline: none;
}

.main-input:focus {
  background: rgba(255, 255, 255, 0.08);
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.send-btn {
  background: #3b82f6;
  color: white;
  border: none;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: #2563eb;
  transform: scale(1.05);
}

.send-btn:disabled {
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.3);
  cursor: not-allowed;
}
</style>
