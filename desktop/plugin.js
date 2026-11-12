/**
 * Tuned Local Llama.cpp — two statusbar chips.
 * "LLM …"  ON = tuned llama.cpp router (b12255) serving the staged Qwen3.5 models with
 *          n-gram lookup drafting / q4 KV / full-window MoE presets. OFF = managed
 *          Hermes runtime is used as usual.
 * "WG …"   Opt-in bypass of Hermes' read-before-write guard, scoped by the plugin's
 *          hooks to write_file/patch calls from sessions on the staged local models
 *          (Codex and every other provider keep the guard).
 * Registered as TWO items, each with a single click handler on its own root element:
 * a handler nested inside the router chip did not fire in the packaged Desktop (no
 * /file-guard request ever reached the backend), so the controls must not share an
 * element. Backend: /api/plugins/llamacpp-tuned/.
 */
import { cn, STATUSBAR_AREAS, queryClient, useQuery, useValue, host } from '@hermes/plugin-sdk'
import { jsx } from 'react/jsx-runtime'

const STATUS_KEY = ['llamacpp-tuned-status']

function useStatus(api, refetchInterval) {
  return useQuery({
    queryKey: STATUS_KEY,
    queryFn: () => api('/status'),
    refetchInterval,
    retry: 1,
  })
}

function Chip({ api }) {
  const { data, isLoading, isError, refetch } = useStatus(api, 10_000)
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

function WgChip({ api }) {
  // Same query key as the router chip, so one poll feeds both.
  const { data, refetch } = useStatus(api, 30_000)
  const bypass = data?.write_guard_local_bypass ?? false
  return jsx('div', {
    onClick: (e) => {
      e.preventDefault()
      api('/file-guard', { method: 'POST', body: { enabled: !bypass } })
        .catch(() => {})
        .finally(() => {
          queryClient.invalidateQueries({ queryKey: STATUS_KEY })
          refetch()
        })
    },
    style: {
      display: 'flex', alignItems: 'center', cursor: 'pointer',
      padding: '0 6px', fontSize: 10, whiteSpace: 'nowrap', userSelect: 'none',
      color: bypass
        ? 'var(--ui-warn, var(--ui-text-secondary))'
        : 'var(--ui-text-quaternary)',
    },
    title: bypass
      ? 'Write guard: BYPASSED for staged local-router models — write_file/patch from those sessions stop refusing overwrites it cannot baseline (the Windows fstat/st_ctime bug). Codex and every other provider keep the guard. Click to restore it everywhere.'
      : 'Write guard: ON (default) for every provider. Click to let staged local-router sessions bypass it if write_file keeps refusing legitimate overwrites with "has not seen its full current content" — Codex is not affected either way.',
    children: bypass ? 'WG local' : 'WG on',
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
  ctx.register({
    id: 'llamacpp-tuned-wg', area: STATUSBAR_AREAS.right, order: 51,
    render: () => jsx(WgChip, { api }),
  })
}

export default { id: 'llamacpp-tuned', name: 'Tuned Local Llama.cpp', register }
