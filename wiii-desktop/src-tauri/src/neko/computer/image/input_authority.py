from contextlib import contextmanager
import threading
import time


class InputRevoked(RuntimeError):
    pass


class InputAuthority:
    def __init__(self):
        self.condition = threading.Condition(threading.RLock())
        self.local = threading.local()
        self.lease = None
        self.cancelled = threading.Event()
        self.cancelled.set()
        self.active = False
        self.cleanup_failed = False
        self.revocation_pending = False

    def activate(self, lease):
        if not isinstance(lease, str) or not 1 <= len(lease) <= 200:
            raise ValueError("Invalid input lease")
        with self.condition:
            if self.cleanup_failed or self.revocation_pending:
                raise RuntimeError("Input cleanup is unconfirmed")
            if lease == self.lease:
                if self.cancelled.is_set():
                    raise InputRevoked("Input lease has been revoked")
                return
            if self.active or not self.cancelled.is_set():
                raise RuntimeError("Another input lease is active")
            self.lease = lease
            self.cancelled = threading.Event()

    def revoke(self, lease, timeout=8, cleanup=None):
        with self.condition:
            if self.lease != lease:
                if self.active or not self.cancelled.is_set() or self.revocation_pending or self.cleanup_failed:
                    raise RuntimeError("A different input authority requires reconciliation")
                return
            self.cancelled.set()
            self.revocation_pending = True
            self.condition.notify_all()
            if not self.condition.wait_for(lambda: not self.active, timeout):
                raise TimeoutError("Input revocation is not yet quiescent")
            if self.cleanup_failed:
                raise RuntimeError("Input cleanup is unconfirmed")
            if cleanup is not None:
                cleanup()
            self.revocation_pending = False

    def run(self, lease, action):
        with self.condition:
            if lease != self.lease or self.cancelled.is_set() or self.active:
                raise InputRevoked("Input lease is not current")
            self.active = True
            self.local.cancelled = self.cancelled
        try:
            return action()
        finally:
            del self.local.cancelled
            with self.condition:
                self.active = False
                self.condition.notify_all()

    def checkpoint(self):
        cancelled = getattr(self.local, "cancelled", None)
        if cancelled is not None and cancelled.is_set() and not getattr(self.local, "cleaning", False):
            raise InputRevoked("Input lease has been revoked")

    def dispatch(self, action, *args, **kwargs):
        with self.condition:
            self.checkpoint()
        return action(*args, **kwargs)

    def wait(self, seconds):
        cancelled = getattr(self.local, "cancelled", None)
        if cancelled is None:
            time.sleep(seconds)
        elif cancelled.wait(seconds):
            self.checkpoint()

    @contextmanager
    def cleanup(self):
        self.local.cleaning = True
        try:
            yield
        except BaseException:
            with self.condition:
                self.cleanup_failed = True
            raise
        finally:
            self.local.cleaning = False
