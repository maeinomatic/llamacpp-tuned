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
  // Opt-in bypass, scoped by the plugin's hooks to write calls from sessions on
  // the router's staged local models — Codex and other providers keep the guard.
  const wgBypass = data?.write_guard_local_bypass ?? false
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
  // The two controls are SIBLINGS, never nested: a click on the WG segment must not
  // be able to reach a router-mode handler at all. The statusbar wrapper carries no
  // click handler of its own, so no propagation trick is needed (and stopPropagation
  // alone was not enough here).
  return jsx('div', {
    style: {
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '0 8px', fontSize: 11, whiteSpace: 'nowrap', userSelect: 'none',
      color,
    },
    children: [
      jsx('span', {
        onClick: (e) => {
          e.preventDefault()
          e.stopPropagation()
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
        style: { cursor: 'pointer' },
        title: on
          ? 'Tuned llama.cpp router: ON — click to disable (managed runtime takes over)'
          : 'Tuned llama.cpp router: OFF — click to enable tuned serving (256K window, n-gram lookup drafting)',
        children: label,
      }),
      jsx('span', {
        onClick: (e) => {
          e.preventDefault()
          e.stopPropagation()
          api('/file-guard', { method: 'POST', body: { enabled: !wgBypass } })
            .catch(() => {})
            .finally(() => {
              queryClient.invalidateQueries({ queryKey: STATUS_KEY })
              refetch()
            })
        },
        style: {
          padding: '0 4px', borderRadius: 3, fontSize: 10, cursor: 'pointer',
          border: '1px solid currentColor', opacity: wgBypass ? 1 : 0.6,
          color: wgBypass ? 'var(--ui-warn, var(--ui-text-secondary))' : 'inherit',
        },
        title: wgBypass
          ? 'Write guard: BYPASSED for staged local-router models — write_file/patch from those sessions stop refusing overwrites it cannot baseline (the Windows fstat/st_ctime bug). Codex and every other provider keep the guard. Click to restore it everywhere.'
          : 'Write guard: ON (default) for every provider. Click to let staged local-router sessions bypass it if write_file keeps refusing legitimate overwrites with "has not seen its full current content" — Codex is not affected either way.',
        children: wgBypass ? 'WG local' : 'WG on',
      }),
    ],
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
