#!/usr/bin/env python3
"""Finite idle entrypoint used only while the control plane invokes the canary."""
import signal
import time

stopping = False

def stop(_signum, _frame):
    global stopping
    stopping = True

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
deadline = time.monotonic() + 180
while not stopping and time.monotonic() < deadline:
    time.sleep(0.25)
