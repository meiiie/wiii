from __future__ import annotations

import http.client
from contextlib import closing
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

IMAGE = Path(__file__).resolve().parents[1] / "src-tauri/src/neko/computer/image"
SOCKET = "/run/wiii-control/semantic.sock"


class UnixConnection(http.client.HTTPConnection):
    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(2)
        self.sock.connect(SOCKET)


@unittest.skipUnless(sys.platform == "linux" and os.geteuid() == 0,
                     "requires an isolated Linux container with a private control tmpfs")
class ControlTransportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if os.environ.get("WIII_ISOLATED_CONTROL_TEST") != "1":
            raise RuntimeError("Run only in a disposable test container")
        program = (
            "from control_transport import private_server; "
            "from semantic_bridge import SemanticBridgeHandler; "
            "server=private_server(SemanticBridgeHandler); server.serve_forever()"
        )
        cls.server = subprocess.Popen([sys.executable, "-B", "-c", program], cwd=IMAGE)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            connection = UnixConnection("localhost")
            try:
                connection.request("GET", "/health")
                response = connection.getresponse()
                response.read()
                connection.close()
                if response.status == 200:
                    return
            except (OSError, http.client.HTTPException):
                if cls.server.poll() is not None:
                    raise RuntimeError("Private server exited before readiness")
                time.sleep(0.02)
            finally:
                connection.close()
        cls.tearDownClass()
        raise TimeoutError("Private server did not become ready")

    @classmethod
    def tearDownClass(cls) -> None:
        subprocess.run(
            ["setpriv", "--reuid=10001", "--regid=10001", "--clear-groups",
             "kill", "-TERM", str(cls.server.pid)], check=True, timeout=5,
        )
        cls.server.wait(timeout=5)

    def workload(self, program: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["setpriv", "--reuid=10001", "--regid=10001", "--clear-groups",
             sys.executable, "-B", "-c", program], cwd=IMAGE,
            capture_output=True, text=True, timeout=5, check=False,
        )

    def test_host_can_read_actual_handler_health(self) -> None:
        with closing(UnixConnection("localhost")) as connection:
            connection.request("GET", "/health")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())["status"], "ok")

    def test_root_curl_ignores_workload_configuration(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wiii-curl-config-") as home:
            os.chmod(home, 0o777)
            marker = str(Path(home) / "hijacked-output")
            result = self.workload(
                "from pathlib import Path; "
                f"Path({str(Path(home) / '.curlrc')!r}).write_text('output = {marker}\\n')"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            command = ["/usr/bin/curl", "--unix-socket", SOCKET, "--fail", "--silent",
                       "--max-time", "2", "http://localhost/health"]
            environment = {**os.environ, "CURL_HOME": home}
            vulnerable = subprocess.run(command, env=environment, capture_output=True,
                                        text=True, timeout=5, check=True)
            self.assertEqual(vulnerable.stdout, "")
            self.assertTrue(Path(marker).exists())
            Path(marker).unlink()
            protected = subprocess.run([command[0], "--disable", *command[1:]], env=environment,
                                       capture_output=True, text=True, timeout=5, check=True)
            self.assertEqual(json.loads(protected.stdout)["status"], "ok")
            self.assertFalse(Path(marker).exists())

    def test_workload_cannot_connect_or_replace_endpoint(self) -> None:
        for program in [
            f"import socket; s=socket.socket(socket.AF_UNIX); s.connect({SOCKET!r})",
            f"import os; os.unlink({SOCKET!r})",
            f"import os; os.chmod({str(Path(SOCKET).parent)!r}, 0o777)",
        ]:
            with self.subTest(program=program):
                result = self.workload(program)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("PermissionError", result.stderr)

    def test_workload_cannot_recover_control_descriptors(self) -> None:
        result = self.workload(f"import os; print(os.listdir('/proc/{self.server.pid}/fd'))")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PermissionError", result.stderr)

    def test_kernel_peer_check_also_rejects_an_unprivileged_connection(self) -> None:
        os.chmod(Path(SOCKET).parent, 0o711)
        os.chmod(SOCKET, 0o666)
        try:
            result = self.workload(
                "import socket; s=socket.socket(socket.AF_UNIX); s.settimeout(2); "
                f"s.connect({SOCKET!r}); print('connected', flush=True); "
                "s.sendall(b'GET /health HTTP/1.0\\r\\n\\r\\n'); "
                "print(s.recv(1024))"
            )
            self.assertTrue(result.stdout.startswith("connected\n"), result)
            self.assertNotIn('"status":"ok"', result.stdout)
            self.assertTrue(result.returncode != 0 or result.stdout.strip().endswith("b''"), result)
        finally:
            os.chmod(SOCKET, 0o600)
            os.chmod(Path(SOCKET).parent, 0o700)

    def test_control_worker_and_workload_have_no_effective_capabilities(self) -> None:
        status = Path(f"/proc/{self.server.pid}/status").read_text()
        self.assertIn("Uid:\t10001\t10001\t10001\t10001", status)
        self.assertIn("Gid:\t10001\t10001\t10001\t10001", status)
        self.assertIn("CapEff:\t0000000000000000", status)
        result = self.workload("from pathlib import Path; print(Path('/proc/self/status').read_text())")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CapEff:\t0000000000000000", result.stdout)

    def test_no_guest_tcp_control_listener(self) -> None:
        with socket.socket() as connection:
            connection.settimeout(1)
            self.assertNotEqual(connection.connect_ex(("127.0.0.1", 9234)), 0)

    def test_workload_cannot_initialize_another_control_server(self) -> None:
        result = self.workload(
            "from control_transport import private_server; "
            "from semantic_bridge import SemanticBridgeHandler; private_server(SemanticBridgeHandler)"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be initialized by the host", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
