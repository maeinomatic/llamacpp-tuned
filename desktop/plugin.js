/**
 * Tuned Local Llama.cpp — statusbar chip.
 * ON = tuned llama.cpp router (b12255) serving the staged Qwen3.5 models with
 * n-gram lookup drafting / q4 KV / full-window 35B MoE preset. OFF = managed
 * Hermes runtime is used as usual. Backend: /api/plugins/llamacpp-tuned/.
 */
import { cn, STATUSBAR_AREAS, queryClient, useQuery, useValue, host } from '@hermes/plugin-sdk'
import { jsx } from 'react/jsx-runtime'

const STATUS_KEY = ['llamacpp-tuned-status']

function Chip({ api }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: STATUS_KEY,
    queryFn: () => api('/status'),
    refetchInterval: 10_000,
    retry: 1,
  })
  // Pre-load the focused session's model when it's one of the router's staged
  // models, so Hermes' chat request arrives to a warm model instead of dying
  // in a multi-minute cold-load retry loop.
  const selected = useValue(host.state.model)
  const modelId = typeof selected === 'string' ? selected : selected?.id || selected?.model
  const models = data?.models || []
  const shouldPreload = data?.enabled && modelId && models.includes(modelId)
  const needsLoad = shouldPreload && !(data?.loaded || []).includes(modelId)
      && !(data?.loading || []).includes(modelId)
  if (needsLoad) {
    // fire once; the loading list in the next status poll stops re-fires
    queryClient.setQueryData(STATUS_KEY, {
      ...data, loading: [...(data?.loading || []), modelId],
    })
    api('/load', { method: 'POST', body: { model: modelId } })
      .catch(() => {})
      .finally(() => queryClient.invalidateQueries({ queryKey: STATUS_KEY }))
  }
  const busy = isLoading || data?.busy
  const on = data?.enabled
  const loaded = (data?.loaded || []).length
  const loading = (data?.loading || []).length
  const progress = data?.progress || {}
  // highest in-flight load percent across models
  const pct = Math.max(0, ...Object.values(progress).map((p) => p.percent || 0))
  const label = busy ? 'LLM …'
    : isError ? 'LLM !'
    : on && loading ? `LLM ⏳ ${pct}%`
    : on ? (loaded ? `LLM ● ${loaded}` : 'LLM ○ tuned')
    : 'LLM ○ off'
  const color = isError ? 'var(--ui-red, var(--ui-text-secondary))'
    : on && loading ? 'var(--ui-warn, var(--ui-text-secondary))'
    : on ? 'var(--ui-green, var(--ui-text-secondary))'
    : 'var(--ui-text-quaternary)'
  return jsx('div', {
    onClick: (e) => {
      e.preventDefault()
      if (busy) return
      // optimistic paint so the click feels immediate
      queryClient.setQueryData(STATUS_KEY, { ...data, busy: true })
      api('/mode', { method: 'POST', body: { enabled: !on } })
        .catch(() => {})
        .finally(() => {
          queryClient.invalidateQueries({ queryKey: STATUS_KEY })
          refetch()
        })
    },
    style: {
      display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer',
      padding: '0 8px', fontSize: 11, whiteSpace: 'nowrap', userSelect: 'none',
      color,
    },
    title: on
      ? 'Tuned llama.cpp router: ON — click to disable (managed runtime takes over)'
      : 'Tuned llama.cpp router: OFF — click to enable tuned serving (256K window, n-gram lookup drafting)',
    children: label,
  })
}

export function register(ctx) {
  // ctx.rest is scoped to /api/plugins/llamacpp-tuned and carries auth — raw
  // fetch() from the renderer cannot reach the backend.
  const api = (path, opts = {}) => ctx.rest(path, {
    method: opts.method || 'GET',
    ...(opts.body !== undefined ? { body: opts.body } : {}),
  })
  ctx.register({
    id: 'llamacpp-tuned-chip', area: STATUSBAR_AREAS.right, order: 50,
    render: () => jsx(Chip, { api }),
  })
}

export default { id: 'llamacpp-tuned', name: 'Tuned Local Llama.cpp', register }
