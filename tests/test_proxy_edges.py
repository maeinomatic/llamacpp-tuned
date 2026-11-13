"""Edge-case acceptance using explicit HTTP fixtures, not real models."""
import asyncio
import json
import socket
import time
import unittest

import httpx
from test_proxy import Fixture, plugin, serve

class ErrorTests(unittest.TestCase):
    def test_upstream_error_preserved_for_nonstreaming(self):
        p=plugin()
        with Fixture() as f:
            f.status=500
            p._upstream=lambda:f.url
            with serve(p._proxy_app) as url, httpx.Client(timeout=5) as c:
                r=c.post(url+'/v1/chat/completions',json={'model':'fixture'})
                self.assertEqual(r.status_code,500)

    def test_upstream_error_is_explicit_in_stream(self):
        p=plugin()
        with Fixture() as f:
            f.status=500
            p._upstream=lambda:f.url
            with serve(p._proxy_app) as url, httpx.Client(timeout=5) as c:
                r=c.post(url+'/v1/chat/completions',json={'model':'fixture','stream':True})
                events=[json.loads(s[5:]) for s in r.text.splitlines() if s.startswith('data:')]
                self.assertEqual(events[-1]['error']['code'],500)
                self.assertNotIn('[DONE]',r.text)

    def test_unknown_model_fails_without_loading(self):
        p=plugin()
        with Fixture() as f:
            p._upstream=lambda:f.url
            with serve(p._proxy_app) as url, httpx.Client(timeout=5) as c:
                start=time.monotonic()
                r=c.post(url+'/v1/chat/completions',json={'model':'missing'})
                self.assertEqual(r.status_code,404)
                self.assertEqual(f.load_calls,0)
                self.assertLess(time.monotonic()-start,2)

    def test_failed_load_does_not_attempt_generation(self):
        p=plugin()
        with Fixture() as f:
            f.loaded=None
            f.load_status=500
            p._upstream=lambda:f.url
            with serve(p._proxy_app) as url, httpx.Client(timeout=5) as c:
                self.assertEqual(c.post(url+'/v1/chat/completions',json={'model':'fixture'}).status_code,500)
                self.assertEqual(f.chat_calls,0)

    def test_load_timeout_is_bounded(self):
        p=plugin()
        p._LOAD_TIMEOUT_S=.1
        with Fixture() as f:
            f.loaded=None
            f.load_delay=.5
            p._upstream=lambda:f.url
            with serve(p._proxy_app) as url, httpx.Client(timeout=5) as c:
                self.assertEqual(c.post(url+'/v1/chat/completions',json={'model':'fixture'}).status_code,504)
                self.assertEqual(f.chat_calls,0)
                # Allow fixture's response to finish after expected timeout/cancellation.
                time.sleep(.5)

    def test_malformed_requests_fail_before_upstream(self):
        p=plugin()
        with serve(p._proxy_app) as url, httpx.Client(timeout=5) as c:
            for value in ([],{'model':['bad']},42):
                self.assertEqual(c.post(url+'/v1/chat/completions',json=value).status_code,400)

    def test_authorization_forwarded(self):
        p=plugin()
        with Fixture() as f:
            p._upstream=lambda:f.url
            with serve(p._proxy_app) as url, httpx.Client(timeout=5) as c:
                self.assertEqual(c.post(url+'/v1/chat/completions',json={'model':'fixture'},headers={'Authorization':'Bearer fixture-token'}).status_code,200)
                self.assertEqual(f.authorization,'Bearer fixture-token')

class ConcurrencyEdges(unittest.TestCase):
    def test_cold_requests_deduplicate_load(self):
        p=plugin()
        p._HEARTBEAT_S=.05
        with Fixture() as f:
            f.loaded=None
            p._upstream=lambda:f.url
            with serve(p._proxy_app) as url:
                async def run():
                    async with httpx.AsyncClient(timeout=5) as c:
                        return await asyncio.gather(*[c.post(url+'/v1/chat/completions',json={'model':'fixture','stream':True}) for _ in range(3)])
                responses=asyncio.run(run())
                self.assertTrue(all('[DONE]' in r.text for r in responses))
                self.assertEqual(f.load_calls,1)
                self.assertEqual(f.maximum,1)

    def test_disconnected_queued_stream_does_not_generate(self):
        p=plugin()
        p._HEARTBEAT_S=.05
        with Fixture() as f:
            f.delay=.6
            p._upstream=lambda:f.url
            with serve(p._proxy_app) as url:
                async def run():
                    async with httpx.AsyncClient(timeout=5) as c:
                        first=asyncio.create_task(c.post(url+'/v1/chat/completions',json={'model':'fixture','stream':True}))
                        while not f.active: await asyncio.sleep(.01)
                        async with c.stream('POST',url+'/v1/chat/completions',json={'model':'fixture','stream':True}) as r:
                            async for line in r.aiter_lines():
                                if line.startswith(': ping'): break
                        await first
                        await asyncio.sleep(.2)
                asyncio.run(run())
                self.assertEqual(f.chat_calls,1)

    def test_disconnected_cold_stream_load_is_reused(self):
        p=plugin()
        p._HEARTBEAT_S=.05
        with Fixture() as f:
            f.loaded=None
            f.load_delay=.6
            p._upstream=lambda:f.url
            with serve(p._proxy_app) as url:
                async def run():
                    async with httpx.AsyncClient(timeout=5) as c:
                        async with c.stream('POST',url+'/v1/chat/completions',json={'model':'fixture','stream':True}) as r:
                            async for line in r.aiter_lines():
                                if line.startswith(': ping') and f.load_calls: break
                        response=await c.post(url+'/v1/chat/completions',json={'model':'fixture'})
                        self.assertEqual(response.status_code,200)
                asyncio.run(run())
                self.assertEqual(f.load_calls,1)
                self.assertEqual(f.chat_calls,1)

    def test_unload_waits_for_generation(self):
        p=plugin()
        with Fixture() as f:
            f.delay=.6
            p._upstream=lambda:f.url
            with serve(p._proxy_app) as url:
                async def run():
                    async with httpx.AsyncClient(timeout=5) as c:
                        first=asyncio.create_task(c.post(url+'/v1/chat/completions',json={'model':'fixture'}))
                        while not f.active: await asyncio.sleep(.01)
                        await c.post(url+'/models/unload',json={'model':'fixture'})
                        self.assertEqual(f.active,0)
                        await first
                asyncio.run(run())

class LifecycleEdges(unittest.TestCase):
    def test_occupied_port_fails_synchronously(self):
        p=plugin()
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0))
            listener.listen()
            p._settings=lambda:{'port':listener.getsockname()[1]}
            with self.assertRaisesRegex(RuntimeError,'bind'):
                p._proxy_start()
            self.assertIsNone(p._proxy_thread)

if __name__=='__main__': unittest.main()
