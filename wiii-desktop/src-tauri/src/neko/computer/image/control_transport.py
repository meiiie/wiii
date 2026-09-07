from __future__ import annotations

import ctypes
import os
import socket
import socketserver
import stat
import struct

CONTROL_SOCKET = "/run/wiii-control/semantic.sock"
WORKLOAD_UID = 10001
WORKLOAD_GID = 10001
PR_SET_DUMPABLE = 4


class HostControlServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True

    def verify_request(self, request: socket.socket, _address: str) -> bool:
        credentials = request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        _pid, uid, _gid = struct.unpack("3i", credentials)
        return uid == 0


def private_server(handler: type) -> HostControlServer:
    if os.geteuid() != 0:
        raise PermissionError("Computer control must be initialized by the host")
    parent = os.path.dirname(CONTROL_SOCKET)
    info = os.stat(parent, follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
        raise PermissionError("Computer control directory is not private")
    previous = os.umask(0o177)
    try:
        server = HostControlServer(CONTROL_SOCKET, handler)
    finally:
        os.umask(previous)
    try:
        os.setgroups([])
        os.setgid(WORKLOAD_GID)
        os.setuid(WORKLOAD_UID)
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "Cannot protect Computer control descriptors")
        return server
    except BaseException:
        server.server_close()
        raise
