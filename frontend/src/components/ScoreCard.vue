<script setup>
defineProps({
  dimension: String,
  score:     Number,    // 1.0–10.0
  peso:      Number,    // 0–100 (peso aplicado tras renormalización)
  fuente:    String,
  consultadoEn: String, // YYYY-MM-DD
  datoBruto: String,
  detalle:   String,
})

const colorByScore = (s) =>
  s >= 8.5 ? '#15803d' :
  s >= 7.0 ? '#22c55e' :
  s >= 5.5 ? '#f59e0b' :
  s >= 4.0 ? '#f97316' : '#ef4444'

const etiqueta = (s) =>
  s >= 8.5 ? 'Excelente' :
  s >= 7.0 ? 'Bueno' :
  s >= 5.5 ? 'Aceptable' :
  s >= 4.0 ? 'Preocupante' : 'Evitar'
</script>

<template>
  <div class="score-card">
    <header class="sc-header">
      <p class="dimension">{{ dimension }}</p>
      <span class="peso">Peso: {{ peso }}%</span>
    </header>

    <div class="score-row">
      <span class="score" :style="{ color: colorByScore(score) }">
        {{ score.toFixed(1) }}<small>/10</small>
      </span>
      <span class="badge" :style="{ background: colorByScore(score) }">
        {{ etiqueta(score) }}
      </span>
    </div>

    <div class="info-section">
      <p class="dato-bruto">{{ datoBruto }}</p>
      <p class="detalle">{{ detalle }}</p>
    </div>
    
    <p class="fuente">
      Fuente: {{ fuente }} · {{ consultadoEn }}
    </p>
  </div>
</template>

<style scoped>
.score-card {
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
  color: #e2e8f0;
}

.score-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.sc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.dimension {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: #ffffff;
  letter-spacing: -0.01em;
}

.peso {
  font-size: 0.75rem;
  color: #94a3b8;
  background: rgba(0,0,0,0.2);
  padding: 4px 8px;
  border-radius: 12px;
  font-weight: 500;
}

.score-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.score {
  font-size: 2.5rem;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.05em;
}

.score small {
  font-size: 1.2rem;
  opacity: 0.6;
  font-weight: 500;
  margin-left: 2px;
}

.badge {
  color: white;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  box-shadow: 0 2px 5px rgba(0,0,0,0.2);
}

.info-section {
  background: rgba(0,0,0,0.15);
  padding: 10px 12px;
  border-radius: 8px;
  margin-top: 4px;
}

.dato-bruto {
  margin: 0 0 4px 0;
  font-size: 0.9rem;
  font-weight: 500;
  color: #f8fafc;
}

.detalle {
  margin: 0;
  font-size: 0.85rem;
  color: #cbd5e1;
  line-height: 1.4;
}

.fuente {
  margin: 6px 0 0 0;
  font-size: 0.7rem;
  color: #64748b;
  text-align: right;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
</style>
