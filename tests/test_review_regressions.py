import asyncio
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
from fastapi import HTTPException
from test_proxy import Fixture, plugin, serve

class ReviewRegressions(unittest.TestCase):
    def test_heartbeat_never_splits_json_event(self):
        p=plugin()
        p._HEARTBEAT_S=.03
        with Fixture() as f:
            f.split_event=True
            p._upstream=lambda:f.url
            with serve(p._proxy_app) as url, httpx.Client(timeout=5) as c:
                r=c.post(url+'/v1/chat/completions',json={'model':'fixture','stream':True})
                for line in r.text.splitlines():
                    if line.startswith('data:') and line[5:].strip()!='[DONE]':
                        event=json.loads(line[5:])
                        self.assertNotIn('error',event)

    def test_model_switch_waits_for_async_unload(self):
        p=plugin()
        with Fixture() as f:
            f.unload_delay=.3
            p._upstream=lambda:f.url
            with serve(p._proxy_app) as url, httpx.Client(timeout=5) as c:
                self.assertEqual(c.post(url+'/models/unload',json={'model':'fixture'}).status_code,200)
                r=c.post(url+'/v1/chat/completions',json={'model':'second'})
                self.assertEqual(r.status_code,200,r.text)

    def test_model_switch_explicitly_frees_previous_resident(self):
        p=plugin()
        with Fixture() as f:
            p._upstream=lambda:f.url
            with serve(p._proxy_app) as url, httpx.Client(timeout=5) as c:
                self.assertEqual(c.post(url+'/v1/chat/completions',json={'model':'second'}).status_code,200)
                self.assertIn('/models/unload',f.paths)

    def test_stream_error_preserves_engine_diagnostic(self):
        p=plugin()
        with Fixture() as f:
            f.status=500
            p._upstream=lambda:f.url
            with serve(p._proxy_app) as url, httpx.Client(timeout=5) as c:
                r=c.post(url+'/v1/chat/completions',json={'model':'fixture','stream':True})
                self.assertIn('fixture upstream diagnostic',r.text)

    def test_empty_model_control_request_rejected(self):
        p=plugin()
        with serve(p._proxy_app) as url, httpx.Client(timeout=5) as c:
            for payload in ({},{'model':''}):
                self.assertEqual(c.post(url+'/models/load',json=payload).status_code,400)

    def test_failed_health_rolls_back_partial_enable(self):
        p=plugin()
        proc=Mock()
        proc.poll.return_value=None
        with patch.object(p,'_resolve_engine',return_value=sys.executable),patch.object(p,'_spawn',return_value=proc),patch.object(p,'_wait_healthy',return_value=False),patch.object(p,'_proxy_stop'):
            with self.assertRaises(HTTPException):
                asyncio.run(p.set_mode(p.ModeRequest(enabled=True)))
            self.assertIsNone(p._proc)
            proc.terminate.assert_called_once()

    def test_nonstream_disconnect_during_cold_load_does_not_generate(self):
        p=plugin()
        with Fixture() as f:
            f.loaded=None
            f.load_delay=.5
            p._upstream=lambda:f.url
            with serve(p._proxy_app) as url:
                async def run():
                    async with httpx.AsyncClient(timeout=5) as c:
                        task=asyncio.create_task(c.post(url+'/v1/chat/completions',json={'model':'fixture'}))
                        while not f.load_calls: await asyncio.sleep(.01)
                        task.cancel()
                        try: await task
                        except asyncio.CancelledError: pass
                        await asyncio.sleep(.9)
                asyncio.run(run())
                self.assertEqual(f.chat_calls,0)

if __name__=='__main__': unittest.main()
