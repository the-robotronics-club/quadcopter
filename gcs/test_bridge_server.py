#!/usr/bin/env python3
"""
Mock PX4 companion bridge — for testing the GCS's *actual* WebSocket
connect path (not the built-in Simulate button, which only exercises
the app's internal logic).

Run this, then in the GCS enter ws://127.0.0.1:8765 and hit Connect.
It plays back the same scripted flight the Simulate button uses, but
over a real socket, so you're exercising bridge_client.py for real.

Usage:
    pip install websockets
    python test_bridge_server.py
"""
import asyncio
import json
import math
import random

import websockets

HOST, PORT = "127.0.0.1", 8765


async def run_mission(ws):
    t = 0
    x = y = heading = 0.0
    seeded = set()
    obj_id = 0

    async def send(type_, data):
        await ws.send(json.dumps({"type": type_, "data": data}))

    while True:
        t += 1
        heading = (heading + 8) % 360
        x += math.cos(math.radians(heading)) * 0.3
        y += math.sin(math.radians(heading)) * 0.3

        await send("telemetry", {
            "x": x, "y": y, "heading_deg": heading,
            "estimated": (t % 15 < 3),
            "battery_pct": max(20, 100 - t * 0.3),
            "rssi_pct": 70 + round(math.sin(t / 5) * 15),
        })

        cx, cy = round(x), round(y)
        new_cells = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                key = (cx + dx, cy + dy)
                if key in seeded:
                    continue
                seeded.add(key)
                r = random.random()
                if dx == 0 and dy == 0:
                    kind = "corridor"
                elif r < 0.10:
                    kind = "door"
                elif r < 0.16:
                    kind = "window"
                elif r < 0.30:
                    kind = "wall"
                elif r < 0.45:
                    kind = "room"
                else:
                    kind = "floor"
                new_cells.append({"x": cx + dx, "y": cy + dy, "kind": kind})
        if new_cells:
            await send("map_update", {"cell_size_m": 1.0, "cells": new_cells})

        await send("mission_status", {
            "phase": "SEARCHING", "coverage_pct": min(100, t * 0.8), "elapsed_s": t,
        })

        if t == 8:
            await send("waypoint", {"role": "entry", "x": cx, "y": cy, "t": t})
        if t == 40:
            await send("survivor", {
                "id": 1, "grid_box": f"C{cy}", "x": cx, "y": cy,
                "confidence": 0.87, "t": t,
            })
        if t == 70:
            await send("waypoint", {"role": "exit", "x": cx, "y": cy, "t": t})
        if t % 12 == 0:
            obj_id += 1
            kinds = ["obj_crate", "obj_rubble", "obj_barrel"]
            await send("object", {
                "id": obj_id, "kind": kinds[obj_id % 3],
                "x": cx + (random.random() - 0.5), "y": cy + (random.random() - 0.5), "t": t,
            })

        if t >= 120:
            print("[mock bridge] mission script complete, looping.")
            t = 0
            x = y = heading = 0.0
            seeded.clear()

        await asyncio.sleep(0.4)


async def handler(ws, path=None):
    # `path` only exists for compatibility with websockets<10, which
    # calls the handler as (ws, path); newer versions call it as (ws,)
    # and Python happily leaves path at its default. Keeps this script
    # working regardless of which websockets version pip resolves.
    print(f"[mock bridge] GCS connected from {ws.remote_address}")
    try:
        await run_mission(ws)
    except websockets.exceptions.ConnectionClosed:
        print("[mock bridge] GCS disconnected.")


async def main():
    print(f"[mock bridge] listening on ws://{HOST}:{PORT} — connect the GCS to this address.")
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
