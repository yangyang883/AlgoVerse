<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { ExperimentResult } from './types/contracts'

const health = ref('检查中')
const input = ref('3,1,2')
const result = ref<ExperimentResult | null>(null)
const error = ref('')

onMounted(async () => {
  try {
    const response = await fetch('/api/v1/health')
    health.value = (await response.json()).data.status === 'ok' ? '正常' : '异常'
  } catch { health.value = '未连接' }
})

async function run() {
  error.value = ''
  result.value = null
  const values = input.value.split(',').map(s => Number(s.trim()))
  if (values.some(n => !Number.isSafeInteger(n))) { error.value = '请输入逗号分隔的整数'; return }
  try {
    const response = await fetch('/api/v1/experiments/run', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ algorithm: 'bubble_sort', input: { values } }),
    })
    const body = await response.json()
    if (!response.ok) throw new Error(body.error?.message ?? '运行失败')
    result.value = body.data as ExperimentResult
  } catch (e) { error.value = e instanceof Error ? e.message : '运行失败' }
}
</script>

<template>
  <main>
    <h1>AlgoVerse</h1>
    <p>后端健康状态：{{ health }}</p>
    <el-card>
      <h2>D1 冒泡排序实验</h2>
      <p>输入整数数组，执行真实排序并查看校验和轨迹。</p>
      <el-input v-model="input" aria-label="整数数组" placeholder="例如 3,1,2" />
      <el-button type="primary" @click="run">运行实验</el-button>
      <el-alert v-if="error" :title="error" type="error" show-icon />
      <div v-if="result">
        <p>输出：{{ result.output.join(', ') }}</p>
        <p>验证：{{ result.validation.valid ? '通过' : '失败' }}</p>
        <p>比较 {{ result.metrics.comparisons }} 次；交换 {{ result.metrics.swaps }} 次</p>
        <p>轨迹事件：{{ result.trace.length }}；截断：{{ result.trace_truncated ? '是' : '否' }}</p>
        <pre>{{ JSON.stringify(result.trace, null, 2) }}</pre>
      </div>
    </el-card>
  </main>
</template>

<style scoped>
main { max-width: 850px; margin: 3rem auto; font-family: sans-serif; padding: 0 1rem; }
.el-input { max-width: 400px; margin-right: 1rem; }
.el-card { margin-top: 2rem; }
pre { max-height: 18rem; overflow: auto; background: #f5f7fa; padding: 1rem; }
</style>
