<script setup>
defineProps({
  dimension: String,
  score:     Number,
  peso:      Number,
  fuente:    String,
  consultadoEn: String,
  datoBruto: String,
  detalle:   String,
})

const colorByScore = (s) =>
  s >= 8.5 ? '#15803d' :
  s >= 7.0 ? '#22c55e' :
  s >= 5.5 ? '#f59e0b' :
  s >= 4.0 ? '#f97316' : '#ef4444'

const bgByScore = (s) =>
  s >= 8.5 ? 'rgba(21,128,61,0.08)' :
  s >= 7.0 ? 'rgba(34,197,94,0.08)' :
  s >= 5.5 ? 'rgba(245,158,11,0.08)' :
  s >= 4.0 ? 'rgba(249,115,22,0.08)' : 'rgba(239,68,68,0.08)'

const etiqueta = (s) =>
  s >= 8.5 ? 'Excelente' :
  s >= 7.0 ? 'Bueno' :
  s >= 5.5 ? 'Aceptable' :
  s >= 4.0 ? 'Preocupante' : 'Evitar'
</script>

<template>
  <div class="score-card" :style="{ background: bgByScore(score) }">
    <header class="sc-header">
      <p class="dimension">{{ dimension }}</p>
      <span class="peso">{{ peso }}%</span>
    </header>

    <div class="score-row">
      <span class="score-num" :style="{ color: colorByScore(score) }">
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
      {{ fuente }} · {{ consultadoEn }}
    </p>
  </div>
</template>

<style scoped>
.score-card {
  border: 1px solid #1a1a1a18;
  border-radius: 14px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  backdrop-filter: blur(6px);
  background-clip: padding-box;
}

.score-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(0,0,0,0.08);
  border-color: #1a1a1a30;
}

.sc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dimension {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
  color: #111827;
  letter-spacing: -0.01em;
}

.peso {
  font-size: 0.72rem;
  color: #6b7280;
  background: rgba(0,0,0,0.06);
  border: 1px solid #1a1a1a15;
  padding: 3px 8px;
  border-radius: 12px;
  font-weight: 600;
}

.score-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.score-num {
  font-size: 2.2rem;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.05em;
}

.score-num small {
  font-size: 1rem;
  opacity: 0.55;
  font-weight: 500;
  margin-left: 1px;
}

.badge {
  color: white;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.info-section {
  background: rgba(255,255,255,0.6);
  border: 1px solid #1a1a1a0f;
  padding: 10px 12px;
  border-radius: 8px;
}

.dato-bruto {
  margin: 0 0 3px 0;
  font-size: 0.88rem;
  font-weight: 600;
  color: #1f2937;
}

.detalle {
  margin: 0;
  font-size: 0.82rem;
  color: #6b7280;
  line-height: 1.4;
}

.fuente {
  margin: 0;
  font-size: 0.68rem;
  color: #9ca3af;
  text-align: right;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
</style>
