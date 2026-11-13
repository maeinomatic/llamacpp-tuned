"""Regression tests use local HTTP fixtures, never a GPU/model or live Hermes."""
import asyncio
import importlib.util
import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import httpx
import uvicorn

ROOT = Path(__file__).resolve().parents[1]

def plugin():
    spec = importlib.util.spec_from_file_location('tuned_test', ROOT / 'dashboard/plugin_api.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

@contextmanager
def serve(app):
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='critical', lifespan='off', timeout_graceful_shutdown=1))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError('fixture ASGI server did not start')
        time.sleep(.01)
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        server.should_exit = True
        thread.join(5)
        sock.close()
        if thread.is_alive():
            raise RuntimeError('fixture ASGI server failed to stop')

class Fixture:
    def __init__(self):
        self.loaded = 'fixture'
        self.load_calls = 0
        self.chat_calls = 0
        self.active = 0
        self.maximum = 0
        self.delay = .25
        self.prefill = 0
        self.load_delay = .25
        self.status = 200
        self.load_status = 200
        self.unload_delay = 0.0
        self.unloading = False
        self.split_event = False
        self.first_sent = 0
        self.authorization = None
        self.loaded_at_chat = []
        self.load_started_active = []
        self.paths = []
        state = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def reply(self, data, status=200):
                body = json.dumps(data).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass  # expected when a timeout/disconnect test closes the socket
            def do_GET(self):
                if self.path == '/models/sse':
                    return self.events()
                self.reply({'status':'ok'} if self.path == '/health' else {'data':[
                    {'id':m, 'status':{'value':('unloading' if state.unloading else 'loaded') if state.loaded == m else 'unloaded'}} for m in ('fixture','second')]})
            def events(self):
                if state.status >= 400:
                    return self.reply({'error':{'message':'fixture upstream diagnostic'}},state.status)
                time.sleep(state.prefill)
                self.send_response(state.status)
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                try:
                    state.first_sent = time.monotonic()
                    if state.split_event:
                        self.wfile.write(b'data: {"choices":[')
                        self.wfile.flush()
                        time.sleep(.2)
                        self.wfile.write(b'{"delta":{"content":"fixture"}}]}\n\n')
                    else:
                        self.wfile.write(b'data: {"choices":[{"delta":{"content":"fixture"}}]}\n\n')
                    self.wfile.flush()
                    time.sleep(state.delay)
                    self.wfile.write(b'data: [DONE]\n\n')
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
            def do_POST(self):
                state.paths.append(self.path)
                body = json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}')
                if self.path == '/models/load':
                    if state.unloading:
                        return self.reply({'error':{'message':'model limit reached'}},500)
                    state.load_calls += 1
                    state.load_started_active.append(state.active)
                    time.sleep(state.load_delay)
                    if state.load_status == 200:
                        state.loaded = body['model']
                    return self.reply({'success':state.load_status == 200}, state.load_status)
                if self.path == '/models/unload':
                    def finish():
                        time.sleep(state.unload_delay)
                        state.loaded = None
                        state.unloading = False
                    if state.unload_delay:
                        state.unloading = True
                        threading.Thread(target=finish,daemon=True).start()
                    else:
                        state.loaded = None
                    return self.reply({'success':True})
                state.chat_calls += 1
                state.loaded_at_chat.append(state.loaded)
                state.authorization = self.headers.get('Authorization')
                state.active += 1
                state.maximum = max(state.maximum, state.active)
                try:
                    if body.get('stream'):
                        return self.events()
                    time.sleep(state.delay)
                    return self.reply({'choices':[{'message':{'content':'fixture'}}]}, state.status)
                finally:
                    state.active -= 1
        self.server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
    def __enter__(self):
        self.thread.start()
        return self
    def __exit__(self,*args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
    @property
    def url(self): return f'http://127.0.0.1:{self.server.server_port}'

class RoutingTests(unittest.TestCase):
    def test_chat_dispatches_to_specific_handler(self):
        from starlette.routing import Match
        p = plugin()
        for path in ('/v1/chat/completions', '/completion'):
            selected = next(r for r in p._proxy_app.routes if r.matches({'type':'http','path':path,'method':'POST','root_path':''})[0] == Match.FULL)
            self.assertEqual(selected.endpoint.__name__, '_proxy_chat')

class StreamingTests(unittest.TestCase):
    def test_model_events_are_forwarded_before_upstream_finishes(self):
        p = plugin()
        with Fixture() as fixture:
            fixture.delay = .6
            p._upstream = lambda: fixture.url
            with serve(p._proxy_app) as url, httpx.Client(timeout=5) as client:
                with client.stream('GET', url + '/models/sse') as response:
                    chunks = response.iter_raw()
                    first = next(chunks)
                    self.assertNotIn(b'[DONE]', first)
                    self.assertLess(time.monotonic() - fixture.first_sent, .45)

    def test_cold_load_sends_heartbeat_before_model_is_ready(self):
        p = plugin()
        p._HEARTBEAT_S = .05
        with Fixture() as fixture:
            fixture.loaded = None
            fixture.load_delay = .7
            p._upstream = lambda: fixture.url
            with serve(p._proxy_app) as url, httpx.Client(timeout=5) as client:
                start = time.monotonic()
                with client.stream('POST', url + '/v1/chat/completions', json={'model':'fixture','stream':True}) as response:
                    chunks = response.iter_raw()
                    first = next(chunks)
                    self.assertLess(time.monotonic() - start, .5)
                    self.assertTrue(first.startswith(b': ping'))
                    # Drain the stream so this test also observes the completed load.
                    b''.join(chunks)

    def test_prefill_sends_heartbeats_before_first_token(self):
        p = plugin()
        p._HEARTBEAT_S = .05
        with Fixture() as fixture:
            fixture.prefill = .6
            p._upstream = lambda: fixture.url
            with serve(p._proxy_app) as url, httpx.Client(timeout=5) as client:
                start = time.monotonic()
                with client.stream('POST', url + '/v1/chat/completions', json={'model':'fixture','stream':True}) as response:
                    chunks = response.iter_raw()
                    self.assertTrue(next(chunks).startswith(b': ping'))
                    self.assertLess(time.monotonic() - start, .5)
                    self.assertIn(b'[DONE]', b''.join(chunks))

    def test_chat_tokens_are_not_buffered(self):
        p = plugin()
        with Fixture() as fixture:
            fixture.delay = .6
            p._upstream = lambda: fixture.url
            with serve(p._proxy_app) as url, httpx.Client(timeout=5) as client:
                with client.stream('POST', url + '/v1/chat/completions', json={'model':'fixture','stream':True}) as response:
                    chunks = response.iter_raw()
                    first = next(chunks)
                    self.assertNotIn(b'[DONE]', first)
                    self.assertLess(time.monotonic() - fixture.first_sent, .45)
                    b''.join(chunks)

class ConcurrencyTests(unittest.TestCase):
    def test_different_models_share_one_residency_slot(self):
        p = plugin()
        with Fixture() as fixture:
            fixture.delay = .6
            fixture.load_delay = .05
            p._upstream = lambda: fixture.url
            with serve(p._proxy_app) as url:
                async def run():
                    async with httpx.AsyncClient(timeout=5) as client:
                        return await asyncio.gather(*[client.post(url+'/v1/chat/completions',json={'model':m,'stream':False}) for m in ('fixture','second')])
                responses = asyncio.run(run())
                self.assertEqual([r.status_code for r in responses], [200,200])
                self.assertEqual(fixture.maximum, 1)

    def test_explicit_preload_does_not_evict_active_chat(self):
        p = plugin()
        with Fixture() as fixture:
            fixture.delay = .6
            p._upstream = lambda: fixture.url
            with serve(p._proxy_app) as url:
                async def run():
                    async with httpx.AsyncClient(timeout=5) as client:
                        chat = asyncio.create_task(client.post(url+'/v1/chat/completions',json={'model':'fixture'}))
                        while not fixture.active:
                            await asyncio.sleep(.01)
                        load = await client.post(url+'/models/load',json={'model':'second'})
                        return await chat, load
                responses = asyncio.run(run())
                self.assertEqual([r.status_code for r in responses],[200,200])
                self.assertEqual(fixture.load_started_active, [0])

class LifecycleTests(unittest.TestCase):
    def test_enable_keeps_public_proxy_running(self):
        p = plugin()
        proc = type('Process', (), {'poll':lambda s:None})()
        p._proc = proc
        with patch.object(p,'_resolve_engine',return_value=sys.executable), patch.object(p,'_ensure_threads'), patch.object(p,'_proxy_start',create=True) as start, patch.object(p,'_proxy_stop',create=True) as stop, patch.object(p,'_read_state',return_value={'enabled':True}):
            asyncio.run(p.set_mode(p.ModeRequest(enabled=True)))
            stop.assert_not_called()

    def test_stop_joins_listener_before_reenable(self):
        p = plugin()
        with Fixture() as fixture:
            with socket.socket() as reserve:
                reserve.bind(('127.0.0.1', 0))
                port = reserve.getsockname()[1]
            p._settings = lambda: {'port':port}
            p._upstream = lambda: fixture.url
            try:
                for _ in range(2):
                    p._proxy_start()
                    deadline = time.monotonic() + 5
                    while not p._proxy_server.started and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertTrue(p._proxy_server.started)
                    thread = p._proxy_thread
                    p._proxy_stop()
                    self.assertFalse(thread.is_alive())
                    with socket.socket() as probe:
                        self.assertNotEqual(probe.connect_ex(('127.0.0.1', port)), 0)
            finally:
                p._proxy_stop()
                if p._proxy_thread:
                    p._proxy_thread.join(5)

    def test_failed_proxy_bind_does_not_orphan_router(self):
        p = plugin()
        proc = type('Process', (), {'pid':123, 'terminate':lambda s:None, 'wait':lambda s,timeout=None:0})()
        from unittest.mock import Mock
        proc.terminate = Mock()
        with tempfile.TemporaryDirectory() as directory:
            p.ENGINE_DIR = Path(directory)
            p.LOG = Path(directory) / 'test.log'
            with patch.object(p,'_generate_presets'), patch.object(p,'_resolve_engine',return_value=sys.executable), patch.object(p,'_attach_watchdog'), patch.object(p.subprocess,'Popen',return_value=proc), patch.object(p,'_proxy_start',side_effect=RuntimeError('occupied')):
                with self.assertRaisesRegex(RuntimeError,'occupied'):
                    p._spawn()
                proc.terminate.assert_called_once()

if __name__ == '__main__': unittest.main()
