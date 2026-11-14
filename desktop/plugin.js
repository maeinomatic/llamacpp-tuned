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
import { useEffect, useState } from 'react'
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

function ShareChip({ api }) {
  // Same query key as the router chip, so one poll feeds all.
  const { data, refetch } = useStatus(api, 30_000)
  // Surface failures instead of swallowing them (a 404 from an unmounted route,
  // a 409 when the router is off, etc. otherwise looks like a dead chip).
  const [err, setErr] = useState(null)
  const on = data?.share ?? false
  const enabled = data?.enabled ?? false

  const flashError = (msg) => {
    setErr(String(msg || 'failed').slice(0, 140))
    setTimeout(() => setErr(null), 5000)
  }

  const label = err ? 'SHARE !' : on ? 'SHARE ●' : 'SHARE off'
  const color = err
    ? 'var(--ui-red, var(--ui-warn, var(--ui-text-secondary)))'
    : on ? 'var(--ui-green, var(--ui-text-secondary))'
    : 'var(--ui-text-quaternary)'

  return jsx('div', {
    onClick: (e) => {
      e.preventDefault()
      if (!enabled) {
        flashError('Enable the LLM chip (tuned router) before sharing')
        return
      }
      api('/share', { method: 'POST', body: { enabled: !on } })
        .then((res) => {
          if (!res || res.share !== !on) flashError('Backend did not confirm the change')
        })
        .catch((ex) => {
          const m = ex && (ex.message || ex.detail || ex)
          flashError(m || 'Share toggle failed (has the gateway been restarted?)')
        })
        .finally(() => {
          queryClient.invalidateQueries({ queryKey: STATUS_KEY })
          refetch()
        })
    },
    style: {
      display: 'flex', alignItems: 'center', cursor: err ? 'default' : 'pointer',
      padding: '0 6px', fontSize: 10, whiteSpace: 'nowrap', userSelect: 'none',
      color,
    },
    title: err
      ? `SHARE error: ${err}`
      : on
        ? `Sharing the tuned proxy on port ${data?.share_port ?? 8090} to the LAN for a remote Hermes gateway${data?.share_token_set ? ' (bearer token required)' : ''}. Click to stop sharing.`
        : `Share the tuned proxy (port ${data?.share_port ?? 8090}) to the LAN so another Hermes gateway (e.g. the NAS) can use these models. Requires the LLM chip ON and a firewall rule for the port. Click to enable.`,
    children: label,
  })
}

function UnloadChip({ api }) {
  useEffect(() => {
    const close = () => {
      document.getElementById('llamacpp-tuned-unload-menu')?.remove()
      document.getElementById('llamacpp-tuned-unload-backdrop')?.remove()
    }
    const escape = (event) => { if (event.key === 'Escape') close() }
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('keydown', escape)
      close()
    }
  }, [])
  // Same query key as the router chip, so one poll feeds both.
  //
  // WHY THE POPUP IS BUILT BY HAND: in the packaged Desktop the statusbar host
  // does not preserve nested element children of a registered chip (a native
  // <select> lost its <option> list — bare chevron, empty popup), so the menu
  // cannot go through the React tree. The chip itself renders a plain-string
  // label (the proven pattern) and onClick builds a real popup directly in
  // document.body, positioned under the chip, styled with the app's theme
  // variables so it follows light/dark automatically.
  const STEPS = [
    { seconds: 900, label: '15m (default)' },
    { seconds: 1800, label: '30m' },
    { seconds: 3600, label: '1h' },
    { seconds: 7200, label: '2h' },
    { seconds: 10800, label: '3h' },
    { seconds: 0, label: 'never' },
  ]
  const { data, refetch } = useStatus(api, 30_000)
  const seconds = data?.idle_unload_s ?? 900
  const current = STEPS.find((s) => s.seconds === seconds) || STEPS[0]

  function openMenu(anchor) {
    // remove any stale menu/backdrop from a previous open or plugin reload
    document.getElementById('llamacpp-tuned-unload-menu')?.remove()
    document.getElementById('llamacpp-tuned-unload-backdrop')?.remove()
    const rect = anchor.getBoundingClientRect()
    const menu = document.createElement('div')
    menu.id = 'llamacpp-tuned-unload-menu'
    menu.style.cssText = [
      'position:fixed', `left:${Math.round(rect.left)}px`,
      `top:${Math.round(rect.bottom + 4)}px`, 'z-index:99999',
      'min-width:150px', 'border-radius:6px', 'overflow:hidden',
      'box-shadow:0 4px 16px rgba(0,0,0,.4)',
      `background:var(--card, #1e1e1e)`,
      `color:var(--foreground, #ddd)`,
      `border:1px solid var(--border, rgba(128,128,128,.4))`,
      'font-size:11px',
    ].join(';')
    for (const s of STEPS) {
      const row = document.createElement('div')
      row.textContent = `UNLOAD ${s.label}` + (s.seconds === seconds ? '  ✓' : '')
      row.style.cssText = 'padding:5px 10px; cursor:pointer; white-space:nowrap;'
        + (s.seconds === seconds
          ? `background:color-mix(in srgb, var(--accent, #7aa2f7) 18%, var(--card, #1e1e1e));`
          : '')
      row.onmouseenter = () => {
        if (s.seconds !== seconds) row.style.background = 'color-mix(in srgb, var(--foreground, #ddd) 8%, var(--card, #1e1e1e))'
      }
      row.onmouseleave = () => {
        row.style.background = s.seconds === seconds
          ? 'color-mix(in srgb, var(--accent, #7aa2f7) 18%, var(--card, #1e1e1e))' : ''
      }
      row.onclick = (ev) => {
        ev.stopPropagation()
        menu.remove()
        document.getElementById('llamacpp-tuned-unload-backdrop')?.remove()
        if (s.seconds === seconds) return
        api('/idle-unload', { method: 'POST', body: { seconds: s.seconds } })
          .catch(() => {})
          .finally(() => {
            queryClient.invalidateQueries({ queryKey: STATUS_KEY })
            refetch()
          })
      }
      menu.appendChild(row)
    }
    const backdrop = document.createElement('div')
    backdrop.id = 'llamacpp-tuned-unload-backdrop'
    backdrop.style.cssText = 'position:fixed; inset:0; z-index:99998;'
    backdrop.onclick = () => { backdrop.remove(); menu.remove() }
    document.body.appendChild(backdrop)
    document.body.appendChild(menu)
    // The statusbar sits at the window's bottom edge — opening below the chip
    // puts the menu outside the window. Measure, then open UPWARD; fall back
    // to below only if there is no room above either.
    const mh = menu.offsetHeight
    const above = rect.top - mh - 6
    menu.style.top = `${Math.round(above >= 0 ? above : rect.bottom + 4)}px`
    // clamp horizontally so the menu never pokes past the right edge
    const maxLeft = window.innerWidth - menu.offsetWidth - 8
    if (rect.left > maxLeft) menu.style.left = `${Math.round(Math.max(8, maxLeft))}px`
  }

  return jsx('div', {
    // onClick prop (NOT a ref: the statusbar host strips refs and nested
    // children alike — the select and the ref wiring were both dead). The WG
    // chip proves onClick on the chip root fires in the packaged Desktop.
    onClick: (e) => {
      e.preventDefault()
      e.stopPropagation()
      if (document.getElementById('llamacpp-tuned-unload-menu')) {
        document.getElementById('llamacpp-tuned-unload-menu').remove()
        document.getElementById('llamacpp-tuned-unload-backdrop')?.remove()
        return
      }
      openMenu(e.currentTarget)
    },
    style: {
      display: 'flex', alignItems: 'center', cursor: 'pointer', gap: 3,
      padding: '0 6px', fontSize: 10, whiteSpace: 'nowrap', userSelect: 'none',
      color: seconds <= 0 ? 'var(--ui-warn, var(--muted-foreground))'
        : 'var(--ui-text-secondary, var(--foreground))',
    },
    title: `Idle unload: models stay in VRAM ${current.seconds === 0 ? 'indefinitely (until the gateway dies)' : current.label + ' without token activity, then free VRAM; the next request reloads automatically'}. Click for the options. Applies to the running router within ~1 minute.`,
    children: `UNLOAD ${current.label} ▾`,
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
  ctx.register({
    id: 'llamacpp-tuned-share', area: STATUSBAR_AREAS.right, order: 50.3,
    render: () => jsx(ShareChip, { api }),
  })
}

export default { id: 'llamacpp-tuned', name: 'Tuned Local Llama.cpp', register }
