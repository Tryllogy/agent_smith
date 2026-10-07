import socket


def _blocked(*args, **kwargs):
    raise PermissionError("network access is blocked in the sandbox")


def block_network():
    socket.socket = _blocked
    socket.create_connection = _blocked
    socket.socketpair = _blocked
