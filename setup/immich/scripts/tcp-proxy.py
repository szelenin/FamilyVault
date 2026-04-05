#!/usr/bin/env python3
"""
TCP proxy: forwards 0.0.0.0:2283 → Immich container via OrbStack DNS.
Handles HTTP and WebSockets transparently (TCP-level, not HTTP-level).
Backend hostname is resolved at startup so it works after reboots even if
OrbStack assigns a new IP to the container.
"""
import asyncio
import socket
import sys

LISTEN_HOST = '0.0.0.0'
LISTEN_PORT = 2283
BACKEND_HOSTNAME = 'immich-immich-server-1.orb.local'
BACKEND_PORT = 80

def resolve_backend():
    try:
        return socket.gethostbyname(BACKEND_HOSTNAME)
    except socket.gaierror:
        return BACKEND_HOSTNAME  # fall back; asyncio will try to resolve it

async def pipe(reader, writer):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass

async def handle_client(client_reader, client_writer):
    try:
        backend_reader, backend_writer = await asyncio.open_connection(BACKEND_HOST, BACKEND_PORT)
        await asyncio.gather(
            pipe(client_reader, backend_writer),
            pipe(backend_reader, client_writer),
        )
    except (ConnectionRefusedError, OSError):
        client_writer.close()

async def main():
    backend_host = resolve_backend()
    global BACKEND_HOST
    BACKEND_HOST = backend_host
    server = await asyncio.start_server(handle_client, LISTEN_HOST, LISTEN_PORT)
    print(f'Immich proxy: {LISTEN_HOST}:{LISTEN_PORT} -> {BACKEND_HOST}:{BACKEND_PORT} (resolved from {BACKEND_HOSTNAME})', flush=True)
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
