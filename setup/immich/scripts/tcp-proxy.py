#!/usr/bin/env python3
"""
TCP proxy: forwards 0.0.0.0:2283 → Immich container at 192.168.97.6:3001
Handles HTTP and WebSockets transparently (TCP-level, not HTTP-level).
"""
import asyncio
import sys

LISTEN_HOST = '0.0.0.0'
LISTEN_PORT = 2283
BACKEND_HOST = '192.168.138.6'
BACKEND_PORT = 80

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
    server = await asyncio.start_server(handle_client, LISTEN_HOST, LISTEN_PORT)
    print(f'Immich proxy: {LISTEN_HOST}:{LISTEN_PORT} -> {BACKEND_HOST}:{BACKEND_PORT}', flush=True)
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
