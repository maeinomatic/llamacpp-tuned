// Minimal DOM fixture: tests plugin ownership/cleanup, not Electron rendering.
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const path = require('node:path')
const nodes = new Map()
const listeners = new Map()
const cleanups = []
const document = {
  getElementById: (id) => nodes.get(id),
  createElement: () => ({ style: {}, offsetHeight: 120, offsetWidth: 150,
    appendChild() {}, remove() { nodes.delete(this.id) } }),
  body: { appendChild(node) { nodes.set(node.id, node) } },
  addEventListener(name, fn) { listeners.set(name, fn) },
  removeEventListener(name, fn) { if (listeners.get(name) === fn) listeners.delete(name) },
}
let source = fs.readFileSync(path.join(__dirname, '../desktop/plugin.js'), 'utf8')
source = source.replace(/^import .*$/gm, '').replace('export function register', 'function register')
source = source.replace('export default ', 'const defaultExport = ')
source += '\nglobalThis.testApi = { UnloadChip };'
const context = { document, window: { innerWidth: 1200 },
  useEffect(fn) { cleanups.push(fn()) },
  useQuery() { return { data: { idle_unload_s: 900 }, refetch() {} } },
  jsx: (type, props) => ({ type, props }), queryClient: { invalidateQueries() {} },
}
vm.runInNewContext(source, context)
const chip = context.testApi.UnloadChip({ api: () => Promise.resolve() })
const click = () => chip.props.onClick({ preventDefault() {}, stopPropagation() {},
  currentTarget: { getBoundingClientRect: () => ({left:100,top:500,bottom:520}) } })
click()
assert.equal(nodes.size, 2, 'opening menu creates menu and backdrop')
assert.equal(cleanups.length, 1, 'menu must register unmount cleanup')
assert.equal(typeof cleanups[0], 'function')
cleanups[0]()
assert.equal(nodes.size, 0, 'unmount must remove owned DOM overlays')
assert.equal(listeners.size, 0, 'unmount must remove listeners')
console.log('PASS: UNLOAD menu removes its overlay and listeners on unmount')
