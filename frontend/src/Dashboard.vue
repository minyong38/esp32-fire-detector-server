<template>
  <div class="dashboard">
    <!-- 헤더 -->
    <div class="header">
      <div class="title">
        <span class="fire-icon">🔥</span>
        <h1>ESP32 화재 감지 시스템</h1>
      </div>
      <div class="status" :class="{ connected: isConnected }">
        <span class="status-indicator"></span>
        <span>{{ isConnected ? '연결됨' : '연결 끊김' }}</span>
      </div>
    </div>

    <!-- 상단 영역: 4개 센서 카드 + 풀폭 화재 위험 섹션 -->
    <section class="top-area">
      <!-- 4개 센서 카드 그리드 -->
      <div class="sensor-grid">
        <!-- 온도 -->
        <div class="sensor-card temperature">
          <div class="sensor-header">
            <span class="sensor-icon">🌡️</span>
            <h3>온도</h3>
          </div>
          <div class="sensor-value">
            {{ currentData.temperature.toFixed(2) }}°C
            <span class="trend" :class="{ positive: temperatureTrend > 0, negative: temperatureTrend < 0 }">
              {{ temperatureTrend > 0 ? '+' : '' }}{{ temperatureTrend.toFixed(1) }}
            </span>
          </div>
          <div class="sensor-status" :class="temperatureStatus.class">
            <span class="status-icon">{{ temperatureStatus.icon }}</span>
            <span>{{ temperatureStatus.text }}</span>
          </div>
        </div>

        <!-- 습도 -->
        <div class="sensor-card humidity">
          <div class="sensor-header">
            <span class="sensor-icon">💧</span>
            <h3>습도</h3>
          </div>
          <div class="sensor-value">
            {{ currentData.humidity.toFixed(1) }}%
            <span class="trend" :class="{ positive: humidityTrend > 0, negative: humidityTrend < 0 }">
              {{ humidityTrend > 0 ? '+' : '' }}{{ humidityTrend.toFixed(1) }}
            </span>
          </div>
          <div class="sensor-status" :class="humidityStatus.class">
            <span class="status-icon">{{ humidityStatus.icon }}</span>
            <span>{{ humidityStatus.text }}</span>
          </div>
        </div>

        <!-- eCO2 -->
        <div class="sensor-card eco2">
          <div class="sensor-header">
            <span class="sensor-icon">🌿</span>
            <h3>eCO2</h3>
          </div>
          <div class="sensor-value">
            {{ currentData.eco2 }}ppm
            <span class="trend" :class="{ positive: eco2Trend > 0, negative: eco2Trend < 0 }">
              {{ eco2Trend > 0 ? '+' : '' }}{{ eco2Trend.toFixed(1) }}
            </span>
          </div>
          <div class="sensor-status" :class="eco2Status.class">
            <span class="status-icon">{{ eco2Status.icon }}</span>
            <span>{{ eco2Status.text }}</span>
          </div>
        </div>

        <!-- TVOC -->
        <div class="sensor-card tvoc">
          <div class="sensor-header">
            <span class="sensor-icon">☁️</span>
            <h3>TVOC</h3>
          </div>
          <div class="sensor-value">
            {{ currentData.tvoc }}ppb
            <span class="trend" :class="{ positive: tvocTrend > 0, negative: tvocTrend < 0 }">
              {{ tvocTrend > 0 ? '+' : '' }}{{ tvocTrend.toFixed(1) }}
            </span>
          </div>
          <div class="sensor-status" :class="tvocStatus.class">
            <span class="status-icon">{{ tvocStatus.icon }}</span>
            <span>{{ tvocStatus.text }}</span>
          </div>
        </div>
      </div>

      <!-- 🔥 풀폭 화재 위험 섹션 (카드 4개 바로 아래, 빈공간 없이 꽉 채우기) -->
      <div class="fire-section" :class="riskContainerClass">
        <div class="fire-left">
          <div class="fire-title">
            <span class="fire-emoji">🚒</span>
            <h3>화재 위험도</h3>
            <span class="pill" :class="riskPillClass">{{ riskIcon }} {{ fireRisk.risk_level }}</span>
          </div>
          <p class="fire-message">{{ fireRisk.message }}</p>

          <div class="progress">
            <div class="progress-inner" :class="progressClass" :style="{ width: fireRisk.risk_score + '%' }"></div>
          </div>
          <div class="progress-meta">
            <span>0</span>
            <span>점수: <b>{{ Math.round(fireRisk.risk_score) }}</b>/100</span>
            <span>100</span>
          </div>
        </div>

        <div class="fire-right">
          <ul v-if="fireRisk.risk_factors.length" class="risk-factors">
            <li v-for="(f, i) in fireRisk.risk_factors" :key="i">• {{ f }}</li>
          </ul>
          <div v-else class="risk-factors safe-note">
            ✅ 현재 특이사항 없음
          </div>
        </div>
      </div>
    </section>

    <!-- 차트 -->
    <div class="charts-section">
      <div class="chart-container">
        <h3>🌡️ 온도 추이</h3>
        <canvas ref="tempChart" width="400" height="240"></canvas>
      </div>

      <div class="chart-container">
        <h3>🌿 eCO2 추이</h3>
        <canvas ref="eco2Chart" width="400" height="240"></canvas>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, toRaw } from 'vue'
import Chart from 'chart.js/auto'

/* ------------------ 상태 ------------------ */
const currentData = reactive({
  id: 0,
  device_id: 'esp32_fire_detector_01',
  temperature: 25.0,
  humidity: 50.0,
  eco2: 400,
  tvoc: 10,
  created_at: new Date().toISOString()
})
const previousData = reactive({ temperature: 25, humidity: 50, eco2: 400, tvoc: 10 })

const tempChart = ref(null)
const eco2Chart = ref(null)
let tempChartInstance = null
let eco2ChartInstance = null

const tempData = ref([])
const eco2Data = ref([])
const timeLabels = ref([])

const isConnected = ref(false)
const connectionStartTime = ref(null)
const dataFetchTimer = ref(null)
const totalDataCount = ref(1)

/* ------------------ computed ------------------ */
const temperatureTrend = computed(() => currentData.temperature - previousData.temperature)
const humidityTrend = computed(() => currentData.humidity - previousData.humidity)
const eco2Trend = computed(() => currentData.eco2 - previousData.eco2)
const tvocTrend = computed(() => currentData.tvoc - previousData.tvoc)

const temperatureStatus = computed(() => {
  const t = currentData.temperature
  if (t > 30) return { class: 'danger', icon: '🚨', text: '위험' }
  if (t > 25) return { class: 'warning', icon: '⚠️', text: '주의' }
  return { class: 'normal', icon: '✅', text: '정상' }
})
const humidityStatus = computed(() => {
  const h = currentData.humidity
  if (h > 70 || h < 30) return { class: 'warning', icon: '⚠️', text: '주의' }
  return { class: 'normal', icon: '✅', text: '정상' }
})
const eco2Status = computed(() => {
  const v = currentData.eco2
  if (v > 1000) return { class: 'danger', icon: '🚨', text: '위험' }
  if (v > 600) return { class: 'warning', icon: '⚠️', text: '주의' }
  return { class: 'normal', icon: '✅', text: '정상' }
})
const tvocStatus = computed(() => {
  const v = currentData.tvoc
  if (v > 220) return { class: 'danger', icon: '🚨', text: '위험' }
  if (v > 65) return { class: 'warning', icon: '⚠️', text: '주의' }
  return { class: 'normal', icon: '✅', text: '정상' }
})

/* ------------------ 화재 위험도 계산 ------------------ */
const FIRE_THRESHOLDS = Object.freeze({
  temperature: 30.0,   // °C
  tvoc: 300.0,         // ppb
  eco2: 1000.0,        // ppm
  humidity_low: 30.0   // %
})
const FIRE_WEIGHTS = Object.freeze({
  temperature: 40, tvoc: 30, eco2: 20, humidity_low: 10
})
const DELTA_THRESHOLDS = Object.freeze({
  temperature: 2.0, tvoc: 100.0, eco2: 200.0
})
const DELTA_BONUS = 10

const isValid = (x) => typeof x === 'number' && !Number.isNaN(x)
const gt = (v, th) => isValid(v) && v > th
const lt = (v, th) => isValid(v) && v < th

const fireRisk = computed(() => {
  let risk_score = 0
  const factors = []
  const comp = { temperature: 0, tvoc: 0, eco2: 0, humidity_low: 0 }

  const t = currentData.temperature
  const h = currentData.humidity
  const e = currentData.eco2
  const v = currentData.tvoc

  if (gt(t, FIRE_THRESHOLDS.temperature)) {
    risk_score += FIRE_WEIGHTS.temperature
    comp.temperature = FIRE_WEIGHTS.temperature
    factors.push(`고온 감지 (${t.toFixed(2)}°C > ${FIRE_THRESHOLDS.temperature}°C)`)
  }
  if (gt(v, FIRE_THRESHOLDS.tvoc)) {
    risk_score += FIRE_WEIGHTS.tvoc
    comp.tvoc = FIRE_WEIGHTS.tvoc
    factors.push(`TVOC 상승 (${Math.round(v)}ppb > ${FIRE_THRESHOLDS.tvoc}ppb)`)
  }
  if (gt(e, FIRE_THRESHOLDS.eco2)) {
    risk_score += FIRE_WEIGHTS.eco2
    comp.eco2 = FIRE_WEIGHTS.eco2
    factors.push(`eCO2 상승 (${Math.round(e)}ppm > ${FIRE_THRESHOLDS.eco2}ppm)`)
  }
  if (lt(h, FIRE_THRESHOLDS.humidity_low)) {
    risk_score += FIRE_WEIGHTS.humidity_low
    comp.humidity_low = FIRE_WEIGHTS.humidity_low
    factors.push(`낮은 습도 (${h.toFixed(1)}% < ${FIRE_THRESHOLDS.humidity_low}%)`)
  }

  // 트렌드 보정
  if (isValid(t) && isValid(previousData.temperature) && t - previousData.temperature >= DELTA_THRESHOLDS.temperature) {
    risk_score += DELTA_BONUS; factors.push(`온도 급상승 +${(t - previousData.temperature).toFixed(1)}°C`)
  }
  if (isValid(v) && isValid(previousData.tvoc) && v - previousData.tvoc >= DELTA_THRESHOLDS.tvoc) {
    risk_score += DELTA_BONUS; factors.push(`TVOC 급상승 +${Math.round(v - previousData.tvoc)}ppb`)
  }
  if (isValid(e) && isValid(previousData.eco2) && e - previousData.eco2 >= DELTA_THRESHOLDS.eco2) {
    risk_score += DELTA_BONUS; factors.push(`eCO2 급상승 +${Math.round(e - previousData.eco2)}ppm`)
  }

  risk_score = Math.max(0, Math.min(100, risk_score))

  const twoStrong = (comp.temperature > 0) && (comp.tvoc > 0 || comp.eco2 > 0)
  let level, message
  if (twoStrong || risk_score >= 70) {
    level = 'HIGH';   message = '🚨 화재 위험 - 즉시 확인 필요!'
  } else if (risk_score >= 40) {
    level = 'MEDIUM'; message = '⚠️ 주의 - 모니터링 강화'
  } else if (risk_score >= 20) {
    level = 'LOW';    message = '📊 경미한 이상 - 관찰 필요'
  } else {
    level = 'SAFE';   message = '✅ 정상 범위'
  }

  return { risk_level: level, risk_score, message, risk_factors: factors }
})

const riskIcon = computed(() => ({ HIGH:'🔴', MEDIUM:'🟡', LOW:'🟠', SAFE:'🟢' }[fireRisk.value.risk_level] || '⚪'))
const riskPillClass = computed(() => ({
  HIGH:'pill-danger', MEDIUM:'pill-warning', LOW:'pill-low', SAFE:'pill-safe'
}[fireRisk.value.risk_level] || 'pill-safe'))
const riskContainerClass = computed(() => ({
  'fire-high': fireRisk.value.risk_level === 'HIGH',
  'fire-medium': fireRisk.value.risk_level === 'MEDIUM',
  'fire-low': fireRisk.value.risk_level === 'LOW',
  'fire-safe': fireRisk.value.risk_level === 'SAFE'
}))
const progressClass = computed(() => ({
  'progress-danger': fireRisk.value.risk_level === 'HIGH',
  'progress-warning': fireRisk.value.risk_level === 'MEDIUM',
  'progress-low': fireRisk.value.risk_level === 'LOW',
  'progress-safe': fireRisk.value.risk_level === 'SAFE'
}))

/* ------------------ 유틸/차트/폴링 (변경 없음 - 안정화 버전) ------------------ */
const nowLabel = (d = new Date()) =>
  d.getHours().toString().padStart(2, '0') + ':' +
  d.getMinutes().toString().padStart(2, '0') + ':' +
  d.getSeconds().toString().padStart(2, '0')

const deepClone = (obj) => JSON.parse(JSON.stringify(obj))
const plain = (refArr) => { const raw = toRaw(refArr); return Array.isArray(raw) ? raw.slice() : [] }

const seedInitialPoints = () => {
  if (timeLabels.value.length) return
  const t0 = new Date(), t1 = new Date(t0.getTime() - 1000)
  timeLabels.value.push(nowLabel(t1), nowLabel(t0))
  tempData.value.push(currentData.temperature, currentData.temperature)
  eco2Data.value.push(currentData.eco2, currentData.eco2)
}

const fetchLatestData = async () => {
  try {
    const res = await fetch('http://localhost:8080/latest', { cache: 'no-store' })
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
    const json = await res.json()
    if (json?.latest_data) {
      const d = json.latest_data
      const newTemp = Number(d.temperature), newHum = Number(d.humidity)
      const newEco2 = Number(d.eco2), newTvoc = Number(d.tvoc)
      const hasChanged = d.id !== currentData.id || d.created_at !== currentData.created_at
      if (hasChanged) {
        Object.assign(previousData, { temperature: currentData.temperature, humidity: currentData.humidity, eco2: currentData.eco2, tvoc: currentData.tvoc })
        Object.assign(currentData, {
          id: d.id, device_id: d.device_id,
          temperature: Number.isFinite(newTemp) ? newTemp : currentData.temperature,
          humidity: Number.isFinite(newHum) ? newHum : currentData.humidity,
          eco2: Number.isFinite(newEco2) ? newEco2 : currentData.eco2,
          tvoc: Number.isFinite(newTvoc) ? newTvoc : currentData.tvoc,
          created_at: d.created_at
        })
      }
      await nextTick(); appendPoint()
    }
  } catch (e) { console.error('데이터 가져오기 실패:', e) }
}

const startPolling = () => { if (dataFetchTimer.value) clearInterval(dataFetchTimer.value); dataFetchTimer.value = setInterval(fetchLatestData, 2000); isConnected.value = true; connectionStartTime.value = new Date() }
const stopPolling = () => { if (dataFetchTimer.value) clearInterval(dataFetchTimer.value); dataFetchTimer.value = null; isConnected.value = false }

const ensureCharts = () => {
  if (!tempChartInstance && tempChart.value) {
    const ctx = tempChart.value.getContext('2d')
    tempChartInstance = new Chart(ctx, {
      type: 'line',
      data: deepClone({ labels: plain(timeLabels.value), datasets:[{ label:'온도 (°C)', data: plain(tempData.value), borderWidth:2, pointRadius:2, fill:false, tension:0.25 }] }),
      options: deepClone({ responsive:true, maintainAspectRatio:false, scales:{ y:{ title:{ display:true, text:'°C' }}, x:{ title:{ display:true, text:'시간' }}}, plugins:{ legend:{ display:false }}})
    })
  }
  if (!eco2ChartInstance && eco2Chart.value) {
    const ctx2 = eco2Chart.value.getContext('2d')
    eco2ChartInstance = new Chart(ctx2, {
      type: 'line',
      data: deepClone({ labels: plain(timeLabels.value), datasets:[{ label:'eCO2 (ppm)', data: plain(eco2Data.value), borderWidth:2, pointRadius:2, fill:false, tension:0.25 }] }),
      options: deepClone({ responsive:true, maintainAspectRatio:false, scales:{ y:{ title:{ display:true, text:'ppm' }}, x:{ title:{ display:true, text:'시간' }}}, plugins:{ legend:{ display:false }}})
    })
  }
}
const destroyCharts = () => { try { tempChartInstance?.destroy() } catch {} ; try { eco2ChartInstance?.destroy() } catch {} ; tempChartInstance = null; eco2ChartInstance = null }
const initCharts = () => { destroyCharts(); ensureCharts() }

const appendPoint = () => {
  const label = nowLabel()
  timeLabels.value.push(label); tempData.value.push(currentData.temperature); eco2Data.value.push(currentData.eco2)
  const MAX = 30
  while (timeLabels.value.length > MAX) timeLabels.value.shift()
  while (tempData.value.length > MAX) tempData.value.shift()
  while (eco2Data.value.length > MAX) eco2Data.value.shift()
  totalDataCount.value++
  if (!tempChartInstance || !eco2ChartInstance) ensureCharts()
  if (tempChartInstance) { tempChartInstance.data.labels = plain(timeLabels.value); tempChartInstance.data.datasets[0].data = plain(tempData.value); tempChartInstance.update('none') }
  if (eco2ChartInstance)  { eco2ChartInstance.data.labels  = plain(timeLabels.value); eco2ChartInstance.data.datasets[0].data  = plain(eco2Data.value); eco2ChartInstance.update('none') }
}

/* ------------------ 라이프사이클 ------------------ */
onMounted(async () => { seedInitialPoints(); await nextTick(); initCharts(); await fetchLatestData(); startPolling() })
onUnmounted(() => { stopPolling(); destroyCharts() })
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
.header {
  display: flex; justify-content: space-between; align-items: center;
  background: rgba(255,255,255,0.95); padding: 20px 30px;
  border-radius: 15px; margin-bottom: 30px; box-shadow: 0 8px 32px rgba(0,0,0,.1);
}
.title { display: flex; align-items: center; gap: 15px; }
.fire-icon { font-size: 2rem; }
.title h1 { margin: 0; color: #333; font-size: 1.8rem; font-weight: 700; }
.status { display: flex; align-items: center; gap: 10px; padding: 8px 16px; border-radius: 20px; background: #f3f4f6; font-weight: 600; }
.status.connected { background: #dcfce7; color: #16a34a; }
.status-indicator { width: 8px; height: 8px; border-radius: 50%; background: #ef4444; }
.status.connected .status-indicator { background: #22c55e; }

/* 상단영역: 4카드 + 바로 이어지는 풀폭 섹션 */
.top-area { display: grid; gap: 0; } /* 카드와 화재 섹션 사이 '빈공간 없음' */
.sensor-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(220px, 1fr));
  gap: 20px;
  margin-bottom: 30px; /* fire-section과 간격 제거 */
}
@media (max-width: 1100px) {
  .sensor-grid { grid-template-columns: repeat(2, minmax(220px, 1fr)); }
}
@media (max-width: 640px) {
  .sensor-grid { grid-template-columns: 1fr; }
}

.sensor-card {
  background: rgba(255,255,255,0.95);
  padding: 25px;
  border-radius: 15px 15px 0 0; /* 아래 섹션과 자연스럽게 맞물리도록 위는 둥글게 */
  box-shadow: 0 8px 32px rgba(0,0,0,.08);
  border-left: 5px solid;
}
.sensor-card.temperature { border-left-color: #ef4444; }
.sensor-card.humidity { border-left-color: #3b82f6; }
.sensor-card.eco2 { border-left-color: #22c55e; }
.sensor-card.tvoc { border-left-color: #f59e0b; }

.sensor-header { display: flex; align-items: center; gap: 10px; margin-bottom: 15px; }
.sensor-icon { font-size: 1.5rem; }
.sensor-header h3 { margin: 0; color: #374151; font-size: 1.1rem; }
.sensor-value { font-size: 2.5rem; font-weight: 700; color: #111827; margin-bottom: 10px; display: flex; align-items: baseline; gap: 10px; }

.trend { font-size: 1rem; font-weight: 500; padding: 2px 8px; border-radius: 12px; background: #f3f4f6; color: #6b7280; }
.trend.positive { background: #dcfce7; color: #16a34a; }
.trend.negative { background: #fef2f2; color: #dc2626; }

.sensor-status { display: flex; align-items: center; gap: 8px; font-weight: 600; padding: 5px 12px; border-radius: 20px; }
.sensor-status.normal { background: #dcfce7; color: #16a34a; }
.sensor-status.warning { background: #fef3c7; color: #d97706; }
.sensor-status.danger  { background: #fee2e2; color: #b91c1c; }

/* ==== 풀폭 화재 위험 섹션 ==== */
.fire-section {
  display: grid;
  grid-template-columns: 1.2fr 1fr; /* 왼쪽 정보 크게, 오른쪽 위험요소 */
  gap: 24px;
  margin-top: -10px;          /* 위 카드와 시각적으로 연결 */
  padding: 26px 28px;
  border-radius: 0 0 15px 15px; /* 카드의 아래쪽 라운드 */
  background: linear-gradient(90deg, rgba(255,255,255,0.98), rgba(255,255,255,0.96));
  box-shadow: 0 10px 40px rgba(0,0,0,.10);
  border: 2px solid transparent; /* 레벨별 강조 테두리 */
}
.fire-title { display: flex; align-items: center; gap: 12px; }
.fire-emoji { font-size: 1.6rem; }
.fire-title h3 { margin: 0; font-size: 1.2rem; color: #111827; }
.pill { padding: 6px 12px; border-radius: 9999px; font-weight: 800; font-size: .95rem; letter-spacing: .3px; }
.pill-safe    { background:#dcfce7; color:#166534; }
.pill-low     { background:#ffedd5; color:#9a3412; }
.pill-warning { background:#fef3c7; color:#92400e; }
.pill-danger  { background:#fee2e2; color:#991b1b; }

.fire-message { margin: 10px 0 12px; font-size: 1.1rem; color:#111827; }

.progress { width: 100%; height: 14px; background: #f3f4f6; border-radius: 9999px; overflow: hidden; }
.progress-inner { height: 100%; border-radius: 9999px; transition: width .4s ease; }
.progress-safe   { background: #22c55e; }
.progress-low    { background: #f59e0b; }
.progress-warning{ background: #fbbf24; }
.progress-danger { background: #ef4444; }
.progress-meta { display:flex; justify-content:space-between; margin-top:6px; color:#6b7280; font-weight:600; }

.fire-right .risk-factors { margin: 0; padding-left: 18px; color:#374151; font-size: 1rem; line-height: 1.6; }
.fire-right .safe-note { color:#16a34a; font-weight:700; }

.fire-safe   { border-color: #86efac; }
.fire-low    { border-color: #fdba74; }
.fire-medium { border-color: #facc15; animation: pulse 1.5s infinite; }
.fire-high   { border-color: #ef4444; animation: pulse-strong 1.2s infinite; }

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(250, 204, 21, 0.5); }
  70%{ box-shadow: 0 0 0 16px rgba(250, 204, 21, 0); }
  100%{ box-shadow: 0 0 0 0 rgba(250, 204, 21, 0); }
}
@keyframes pulse-strong {
  0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, .6); }
  60%{ box-shadow: 0 0 0 22px rgba(239, 68, 68, 0); }
  100%{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}

/* 차트 영역 */
.charts-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 20px;
  margin-top: 22px;
  margin-bottom: 30px;
}
.chart-container {
  background: rgba(255,255,255,0.95);
  padding: 25px;
  border-radius: 15px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.1);
  min-height: 280px;
}
.chart-container h3 { margin: 0 0 16px 0; color: #374151; }
.chart-container canvas { width: 100% !important; height: 240px !important; display: block; }

@media (max-width: 1024px) {
  .fire-section { grid-template-columns: 1fr; }
}

@media (max-width: 768px) {
  .header { flex-direction: column; gap: 15px; text-align: center; }
}
</style>
