import concurrent.futures
import http.client
from http.server import ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch


IMAGE = Path(__file__).resolve().parents[1] / "src-tauri/src/neko/computer/image"
sys.path.insert(0, str(IMAGE))
from input_authority import InputAuthority, InputRevoked

spec = importlib.util.spec_from_file_location("revocation_bridge", IMAGE / "semantic_bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class InputRevocationTest(unittest.TestCase):
    def setUp(self):
        self.authority = InputAuthority()
        self.authority.activate("lease-one")
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.addCleanup(self.pool.shutdown, wait=True)

    def test_missing_stale_and_revoked_leases_cannot_dispatch(self):
        for lease in (None, "", "lease-old"):
            with self.assertRaises(InputRevoked):
                self.authority.run(lease, self.fail)
        self.authority.revoke("lease-one")
        with self.assertRaises(InputRevoked):
            self.authority.run("lease-one", self.fail)
        with self.assertRaises(InputRevoked):
            self.authority.activate("lease-one")

    def test_delayed_old_release_cannot_revoke_new_lease(self):
        self.authority.revoke("lease-one")
        self.authority.activate("lease-two")
        with self.assertRaisesRegex(RuntimeError, "different input authority"):
            self.authority.revoke("lease-one")
        self.assertEqual(self.authority.run("lease-two", lambda: 42), 42)

    def test_takeover_interrupts_hold_and_releases_keys_before_ack(self):
        started = threading.Event()
        events = []

        class Cdp:
            def call(self, method, params):
                events.append((method, params["type"], params["key"]))
                if params["type"] == "keyDown":
                    started.set()

        steps = [{"keys": ["a"], "holdMs": 2000, "waitMs": 1000},
                 {"keys": ["b"], "holdMs": 2000, "waitMs": 0}]
        with patch.object(bridge, "INPUT_AUTHORITY", self.authority):
            running = self.pool.submit(self.authority.run, "lease-one",
                                       lambda: bridge.dispatch_input_sequence(Cdp(), steps))
            self.assertTrue(started.wait(2))
            self.authority.revoke("lease-one")
            with self.assertRaises(InputRevoked):
                running.result(timeout=1)
        self.assertEqual([event[1:] for event in events], [("keyDown", "a"), ("keyUp", "a")])

    def test_unknown_keydown_delivery_still_gets_keyup(self):
        events = []

        class Cdp:
            def call(self, _method, params):
                events.append(params["type"])
                if params["type"] == "keyDown":
                    raise TimeoutError("reply lost after delivery")

        with patch.object(bridge, "INPUT_AUTHORITY", self.authority):
            with self.assertRaises(TimeoutError):
                self.authority.run("lease-one", lambda: bridge.dispatch_input_sequence(
                    Cdp(), [{"keys": ["a"], "holdMs": 16, "waitMs": 0}]))
        self.authority.revoke("lease-one")
        self.assertEqual(events, ["keyDown", "keyUp"])

    def test_failed_keyup_blocks_ack_and_future_activation(self):
        class Cdp:
            def call(self, _method, params):
                if params["type"] == "keyUp":
                    raise TimeoutError("cleanup reply lost")

        with patch.object(bridge, "INPUT_AUTHORITY", self.authority):
            with self.assertRaises(TimeoutError):
                self.authority.run("lease-one", lambda: bridge.dispatch_input_sequence(
                    Cdp(), [{"keys": ["a"], "holdMs": 16, "waitMs": 0}]))
        with self.assertRaisesRegex(RuntimeError, "cleanup"):
            self.authority.revoke("lease-one")
        with self.assertRaisesRegex(RuntimeError, "cleanup"):
            self.authority.activate("lease-two")

    def test_timeout_is_not_a_false_quiescence_ack(self):
        started = threading.Event()
        finish = threading.Event()

        def active():
            started.set()
            finish.wait(2)

        running = self.pool.submit(self.authority.run, "lease-one", active)
        self.assertTrue(started.wait(1))
        try:
            with self.assertRaises(TimeoutError):
                self.authority.revoke("lease-one", timeout=0.01)
            with self.assertRaises(InputRevoked):
                self.authority.run("lease-one", self.fail)
        finally:
            finish.set()
        running.result(timeout=1)
        self.authority.revoke("lease-one")

    def test_clock_cleanup_failure_requires_successful_reconciliation(self):
        def failed_cleanup():
            raise TimeoutError("clock cleanup uncertain")
        with self.assertRaises(TimeoutError):
            self.authority.revoke("lease-one", cleanup=failed_cleanup)
        with self.assertRaises(RuntimeError):
            self.authority.activate("lease-two")
        self.authority.revoke("lease-one", cleanup=lambda: None)
        self.authority.activate("lease-two")

    def test_blocked_dispatch_does_not_block_revocation_deadline(self):
        entered = threading.Event()
        finish = threading.Event()
        effects = []

        def native_call():
            entered.set()
            finish.wait(3)
            effects.append("in-flight")

        def active():
            self.authority.dispatch(native_call)
            self.authority.dispatch(effects.append, "must-not-run")

        running = self.pool.submit(self.authority.run, "lease-one", active)
        self.assertTrue(entered.wait(1))
        revoke = self.pool.submit(self.authority.revoke, "lease-one", timeout=0.01)
        try:
            self.assertTrue(self.authority.cancelled.wait(0.5))
            with self.assertRaises(TimeoutError):
                revoke.result(timeout=1)
            with self.assertRaises(RuntimeError):
                self.authority.activate("lease-two")
        finally:
            finish.set()
        with self.assertRaises(InputRevoked):
            running.result(timeout=1)
        self.authority.revoke("lease-one")
        self.assertEqual(effects, ["in-flight"])

    def test_pointer_release_runs_even_when_press_response_is_lost(self):
        events = []

        class Cdp:
            def call(self, method, params=None):
                if method == "DOM.getBoxModel":
                    return {"model": {"content": [0, 0, 20, 0, 20, 20, 0, 20]}}
                if method == "Input.dispatchMouseEvent":
                    events.append(params["type"])
                    if params["type"] == "mousePressed":
                        raise TimeoutError("press response lost")
                return {}

        with patch.object(bridge, "INPUT_AUTHORITY", self.authority):
            with self.assertRaises(TimeoutError):
                self.authority.run("lease-one", lambda: bridge.cdp_invoke(Cdp(), 1))
        self.authority.revoke("lease-one")
        self.assertEqual(events, ["mouseMoved", "mousePressed", "mouseReleased"])

    def test_dispatch_after_revocation_signal_never_reaches_native_target(self):
        started = threading.Event()
        continue_action = threading.Event()
        effects = []

        def active():
            started.set()
            continue_action.wait(2)
            self.authority.dispatch(effects.append, "late-click")

        running = self.pool.submit(self.authority.run, "lease-one", active)
        self.assertTrue(started.wait(1))
        revoke = self.pool.submit(self.authority.revoke, "lease-one")
        self.assertTrue(self.authority.cancelled.wait(1))
        continue_action.set()
        revoke.result(timeout=1)
        with self.assertRaises(InputRevoked):
            running.result(timeout=1)
        self.assertEqual(effects, [])

    def test_http_revoke_bypasses_action_lock_and_invalidates_queued_request(self):
        started = threading.Event()
        effects = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), bridge.SemanticBridgeHandler)
        server_thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
        server_thread.start()

        def post(route, body):
            connection = http.client.HTTPConnection(*server.server_address, timeout=3)
            try:
                connection.request("POST", route, json.dumps(body), {"Content-Type": "application/json"})
                response = connection.getresponse()
                return response.status, json.loads(response.read())
            finally:
                connection.close()

        def action(_request):
            effects.append("started")
            started.set()
            self.authority.wait(5)
            effects.append("must-not-run")

        request = {"leaseId": "lease-one", "action": "press_key", "stateVersion": "sha256:fixture"}
        try:
            with patch.object(bridge, "INPUT_AUTHORITY", self.authority), \
                 patch.object(bridge, "act", side_effect=action), \
                 patch.object(bridge, "quiesce_realtime_clock"):
                first = self.pool.submit(post, "/act", request)
                self.assertTrue(started.wait(1))
                queued = self.pool.submit(post, "/act", request)
                status, response = post("/input/revoke", {"leaseId": "lease-one"})
                self.assertEqual((status, response), (200, {"status": "ok", "quiescent": True}))
                for pending in (first, queued):
                    status, response = pending.result(timeout=1)
                    self.assertEqual(status, 200)
                    self.assertEqual(response["result"]["code"], "semantic_lease_revoked")
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=1)
        self.assertEqual(effects, ["started"])


if __name__ == "__main__":
    unittest.main()
