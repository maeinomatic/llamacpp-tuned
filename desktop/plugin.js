/**
 * Tuned Local Llama.cpp — three statusbar chips.
 * "LLM …"  ON = tuned llama.cpp router (b12255) serving the staged Qwen3.5 models with
 *          n-gram lookup drafting / q4 KV / full-window MoE presets. OFF = managed
 *          Hermes runtime is used as usual.
 * "WG …"   Opt-in bypass of Hermes' read-before-write guard, scoped by the plugin's
 *          hooks to write_file/patch calls from sessions on the staged local models
 *          (Codex and every other provider keep the guard).
 * "UNLOAD" Idle-unload dropdown: 15m (default) / 30m / 1h / 2h / 3h / never — how long
 *          loaded models stay in VRAM without token activity before the router frees
 *          them.
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
  const fixed = data?.local_guard_fix ?? false
  return jsx('div', {
    onClick: (e) => {
      e.preventDefault()
      api('/file-guard', { method: 'POST', body: { enabled: !fixed } })
        .catch(() => {})
        .finally(() => {
          queryClient.invalidateQueries({ queryKey: STATUS_KEY })
          refetch()
        })
    },
    style: {
      display: 'flex', alignItems: 'center', cursor: 'pointer',
      padding: '0 6px', fontSize: 10, whiteSpace: 'nowrap', userSelect: 'none',
      color: fixed
        ? 'var(--ui-warn, var(--ui-text-secondary))'
        : 'var(--ui-text-quaternary)',
    },
    title: fixed
      ? 'Write guard: FIXED for staged local-router models. Hermes\' guard cannot record a whole-file baseline on this filesystem (its os.fstat/os.stat st_ctime_ns mismatch), so write_file refuses legitimate overwrites; for local-model write calls the plugin swaps in a helper that takes one metadata view and still checks byte identity, so a genuinely stale overwrite is still refused. Codex and every other provider keep the shipped helper. Click to revert.'
      : 'Write guard: STOCK (default) — the shipped helper, for every provider. Click to make local-router sessions use the corrected baseline check if write_file keeps refusing legitimate overwrites with "has not seen its full current content". Codex is not affected either way.',
    children: fixed ? 'WG fixed' : 'WG stock',
  })
}

function UnloadChip({ api }) {
  // Same query key as the router chip, so one poll feeds both.
  const { data, refetch } = useStatus(api, 30_000)
  const seconds = data?.idle_unload_s ?? 900
  const label = seconds <= 0 ? 'UNLOAD never'
    : seconds >= 3600 ? `UNLOAD ${seconds / 3600}h`
    : `UNLOAD ${Math.round(seconds / 60)}m`
  // Option styling: native selects render the popup with the OPTION's own
  // background/color in Chromium, so leave the select transparent (it blends
  // with the status bar in every theme) and paint the options with theme vars
  // — otherwise items are invisible on dark themes.
  const optStyle = {
    background: 'var(--ui-bg, var(--ui-card, var(--background, #1e1e1e)))',
    color: 'var(--ui-foreground, var(--ui-text-primary, var(--foreground, #ddd)))',
  }
  return jsx('select', {
    value: String(seconds),
    onChange: (e) => {
      e.preventDefault()
      const v = parseInt(e.target.value, 10)
      if (v === seconds) return
      api('/idle-unload', { method: 'POST', body: { seconds: v } })
        .catch(() => {})
        .finally(() => {
          queryClient.invalidateQueries({ queryKey: STATUS_KEY })
          refetch()
        })
    },
    style: {
      cursor: 'pointer', margin: '0 2px', border: 'none', padding: '0 2px',
      fontSize: 10, whiteSpace: 'nowrap', userSelect: 'none',
      background: 'transparent',
      color: seconds <= 0 ? 'var(--ui-warn, var(--ui-text-secondary))'
        : 'var(--ui-text-secondary, var(--foreground))',
    },
    title: 'Idle unload for loaded models. After this many minutes without token activity the router frees VRAM; the next request reloads the model automatically. "never" keeps models resident until the gateway dies (VRAM stays occupied). Applies to the running router within ~1 minute.',
    children: [
      jsx('option', { value: '900', style: optStyle }, 'UNLOAD 15m (default)'),
      jsx('option', { value: '1800', style: optStyle }, 'UNLOAD 30m'),
      jsx('option', { value: '3600', style: optStyle }, 'UNLOAD 1h'),
      jsx('option', { value: '7200', style: optStyle }, 'UNLOAD 2h'),
      jsx('option', { value: '10800', style: optStyle }, 'UNLOAD 3h'),
      jsx('option', { value: '0', style: optStyle }, 'UNLOAD never'),
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
  ctx.register({
    id: 'llamacpp-tuned-wg', area: STATUSBAR_AREAS.right, order: 50.1,
    render: () => jsx(WgChip, { api }),
  })
  ctx.register({
    id: 'llamacpp-tuned-unload', area: STATUSBAR_AREAS.right, order: 50.2,
    render: () => jsx(UnloadChip, { api }),
  })
}

export default { id: 'llamacpp-tuned', name: 'Tuned Local Llama.cpp', register }
