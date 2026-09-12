#!/usr/bin/env python3
"""
Real PX4 -> GCS bridge.

test_bridge_server.py plays back a *scripted* flight so you can
exercise bridge_client.py's WebSocket path with fake data. This
script is the real thing: it reads live MAVLink telemetry from an
actual PX4 instance (SITL/Gazebo, or real hardware over a serial
link) and republishes it as the JSON-over-WebSocket contract the GCS
understands (see gcs/main_window.py's docstring for the full schema).

Why a raw MAVLink/UDP4 bridge alone never connects to the GCS:
gcs/bridge_client.py only ever speaks WebSocket + JSON. Handing it a
udp4 MAVLink endpoint (mavlink-router, PX4's own MAVLink UDP output,
QGroundControl's link, etc.) doesn't work no matter the IP/port,
because there's no WebSocket handshake happening there and nothing
on that port understands this app's JSON message shape. This script
is the missing translator in between:

    PX4 (MAVLink, UDP)  <-->  this bridge  <-->  GCS (JSON, WebSocket)

Usage:
    pip install pymavlink websockets
    python px4_bridge.py --mavlink udpin:0.0.0.0:14550 --ws-port 8765

Then in the GCS, enter ws://127.0.0.1:8765 (or this machine's LAN IP,
if the GCS runs on a different machine) and hit Connect.

--mavlink accepts any pymavlink connection string:
  - PX4 SITL (Gazebo) streams MAVLink to udp:127.0.0.1:14550 by
    default -> use --mavlink udpin:0.0.0.0:14550 to receive it.
  - A companion computer or telemetry radio -> a serial path, e.g.
    --mavlink /dev/ttyUSB0,57600
  - An existing mavlink-router/GCS output -> udpout:<ip>:<port>

Only telemetry/mission_status are populated here, since that's what
PX4 itself can supply. map_update / survivor / object messages depend
on your perception stack (SLAM, detection, etc.) — publish those from
wherever that pipeline lives, using the same _broadcast() pattern.
"""
import argparse
import asyncio
import json
import math
import threading
import time

import websockets
from pymavlink import mavutil


class Px4Bridge:
    def __init__(self, mavlink_conn: str):
        self.mavlink_conn = mavlink_conn
        self.clients = set()
        self.loop = None
        self._latest = {}
        self._start_time = time.time()

    # ---------------- MAVLink side (blocking, runs in a background thread) ----------------
    def run_mavlink(self):
        """Runs forever, reconnecting with backoff on any failure.

        The original version of this loop had no error handling at
        all: a bad --mavlink string, PX4 not being up yet, or PX4
        restarting mid-flight would raise inside this daemon thread,
        print nothing useful, and silently kill telemetry for the
        rest of the process's life with no way to recover short of
        restarting the whole bridge. This wraps every connection
        attempt so a single bad moment doesn't take the bridge down
        permanently.
        """
        backoff = 1
        while True:
            try:
                self._run_mavlink_once()
                backoff = 1  # a clean run resets the backoff
            except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
                print(f"[px4_bridge] MAVLink connection lost/failed: {exc!r} \u2014 retrying in {backoff}s\u2026")
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)

    def _run_mavlink_once(self):
        print(f"[px4_bridge] connecting to MAVLink at {self.mavlink_conn} \u2026")
        m = mavutil.mavlink_connection(self.mavlink_conn)
        try:
            if m.wait_heartbeat(timeout=10) is None:
                raise TimeoutError(f"no heartbeat from {self.mavlink_conn} within 10s")
            print(f"[px4_bridge] heartbeat received from system {m.target_system} \u2014 streaming telemetry.")

            while True:
                msg = m.recv_match(blocking=True, timeout=1)
                if msg is None:
                    continue
                mtype = msg.get_type()

                if mtype == "LOCAL_POSITION_NED":
                    # PX4's local NED frame maps directly onto the GCS's own
                    # local (x, y) frame, matching the "no GPS, no preloaded
                    # origin" model in state.py — no lat/lon conversion needed.
                    self._latest["x"] = msg.x
                    self._latest["y"] = msg.y
                    self._push_telemetry()

                elif mtype == "ATTITUDE":
                    self._latest["heading_deg"] = (math.degrees(msg.yaw) + 360) % 360

                elif mtype == "SYS_STATUS":
                    if msg.battery_remaining >= 0:
                        self._latest["battery_pct"] = msg.battery_remaining

                elif mtype == "RADIO_STATUS":
                    self._latest["rssi_pct"] = round(msg.remrssi / 255 * 100)

                elif mtype == "HEARTBEAT":
                    self._latest["estimated"] = not bool(
                        msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_GUIDED_ENABLED
                    )
        finally:
            m.close()

    def _push_telemetry(self):
        if "x" not in self._latest or "y" not in self._latest:
            return
        data = {
            "x": self._latest.get("x", 0.0),
            "y": self._latest.get("y", 0.0),
            "heading_deg": self._latest.get("heading_deg", 0.0),
            "estimated": self._latest.get("estimated", False),
            "battery_pct": self._latest.get("battery_pct", 100),
            "rssi_pct": self._latest.get("rssi_pct", 100),
        }
        self._broadcast("telemetry", data)
        self._broadcast("mission_status", {
            "phase": "SEARCHING",
            "coverage_pct": 0,
            "elapsed_s": time.time() - self._start_time,
        })

    def _broadcast(self, type_: str, data: dict) -> None:
        if self.loop is None:
            return  # WebSocket server not up yet; drop early telemetry
        payload = json.dumps({"type": type_, "data": data})
        asyncio.run_coroutine_threadsafe(self._send_all(payload), self.loop)

    async def _send_all(self, payload: str) -> None:
        # Iterate over a *copy* of self.clients, not the live set. Telemetry
        # broadcasts fire frequently and each `await ws.send(...)` yields
        # control back to the event loop — if another broadcast (or a
        # client connecting/disconnecting in handler()) mutates
        # self.clients while this loop is still going, iterating the live
        # set directly can raise "set changed size during iteration".
        dead = set()
        for ws in list(self.clients):
            try:
                await ws.send(payload)
            except websockets.exceptions.ConnectionClosed:
                dead.add(ws)
        self.clients -= dead

    # ---------------- WebSocket side (GCS-facing) ----------------
    async def handler(self, ws, path=None):
        # `path` only exists for compatibility with websockets<10, which
        # calls the handler as (ws, path); newer versions call it as (ws,)
        # and leave path at its default — same accommodation
        # test_bridge_server.py makes, so this works with whatever
        # `pip install websockets` happens to resolve.
        print(f"[px4_bridge] GCS connected from {ws.remote_address}")
        self.clients.add(ws)
        try:
            await ws.wait_closed()
        finally:
            self.clients.discard(ws)
            print("[px4_bridge] GCS disconnected.")

    async def serve(self, host: str, port: int) -> None:
        self.loop = asyncio.get_running_loop()
        async with websockets.serve(self.handler, host, port):
            print(f"[px4_bridge] GCS-facing WebSocket listening on ws://{host}:{port}")
            await asyncio.Future()  # run forever


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mavlink", default="udpin:0.0.0.0:14550",
                     help="pymavlink connection string for the PX4 MAVLink stream")
    ap.add_argument("--ws-host", default="0.0.0.0")
    ap.add_argument("--ws-port", type=int, default=8765)
    args = ap.parse_args()

    bridge = Px4Bridge(args.mavlink)
    t = threading.Thread(target=bridge.run_mavlink, daemon=True)
    t.start()
    asyncio.run(bridge.serve(args.ws_host, args.ws_port))


if __name__ == "__main__":
    main()
