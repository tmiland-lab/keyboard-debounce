#!/usr/bin/env python3
"""End-to-end test for kbd-debounce.py using a fake uinput keyboard.

Verifies:
  1. filter waits when the device is absent, then engages when it appears
  2. chatter (down-up-down within threshold) is suppressed
  3. normal presses pass through
  4. filter re-attaches after the device disappears and reappears

Run as root:  sudo python3 test_kbd_debounce.py
"""
import os
import selectors
import subprocess
import sys
import time

import evdev
from evdev import UInput, ecodes

FILTER = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "kbd-debounce.py"
)
NAME = "TestChatter KB"

if os.geteuid() != 0:
    print("run as root (sudo) — the filter needs to grab an input device")
    sys.exit(1)

fails = []


def check(label, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}: {label} {detail}")
    if not cond:
        fails.append(label)


def find_clone(timeout=12.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        for path in evdev.list_devices():
            try:
                d = evdev.InputDevice(path)
            except OSError:
                continue
            if "(debounced)" in (d.name or "") and NAME in d.name:
                return d
            d.close()
        time.sleep(0.5)
    return None


def collect(dev, duration):
    sel = selectors.DefaultSelector()
    sel.register(dev.fd, selectors.EVENT_READ)
    out = []
    end = time.monotonic() + duration
    while time.monotonic() < end:
        for _ in sel.select(timeout=max(0.0, end - time.monotonic())):
            for ev in dev.read():
                out.append(ev)
    sel.close()
    return out


# 1. start filter while device is absent
proc = subprocess.Popen(
    ["python3", FILTER, "--name", "TestChatter", "--threshold", "75", "--release-gap", "30"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)
time.sleep(1.0)

# 2. create fake keyboard pair -> filter must engage the BASE device, not the subdevice
# (filter requires >100 keys to accept a device, like a real keyboard)
KEYS = list(range(1, 128))
ui = UInput({ecodes.EV_KEY: KEYS}, name=NAME)
ui_sub = UInput({ecodes.EV_KEY: list(range(1, 160))}, name=f"{NAME} Consumer Control")
clone = find_clone()
check(
    "clone is the base device, not the subdevice",
    clone is not None and clone.name == f"{NAME} (debounced)",
    f"got {clone.name if clone else None}",
)
if clone is None:
    proc.terminate()
    try:
        out, _ = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate()
    print("---- filter log ----")
    print(out)
    sys.exit(1)
ui_sub.close()
time.sleep(1.0)

# 3. send test sequence on the fake keyboard (raw):
#    t=0.00 down#1 (200ms hold)  -> forwarded
#    t=0.25 down#2 (20ms blip)   -> forwarded (250ms since press#1, 50ms since release#1)
#    t=0.28 down#3 (200ms hold)  -> SUPPRESSED (10ms after release#2)
#    t=0.55 down#4 (200ms hold)  -> forwarded
#    t=0.85 down#5 (180ms hold)  -> forwarded
#    t=1.05 down#6 (20ms blip)   -> SUPPRESSED (22ms after release#5; 200ms since
#                                   press#5, so ONLY the release rule catches it)
#    t=1.35 down#7 (180ms hold)  -> forwarded
def press(delay_before, hold):
    time.sleep(delay_before)
    ui.write(ecodes.EV_KEY, ecodes.KEY_A, 1)
    ui.syn()
    time.sleep(hold)
    ui.write(ecodes.EV_KEY, ecodes.KEY_A, 0)
    ui.syn()

press(0.00, 0.20)
press(0.05, 0.02)
press(0.01, 0.20)
press(0.07, 0.20)
press(0.10, 0.18)
press(0.022, 0.02)
press(0.28, 0.18)

events = collect(clone, 2.5)
downs = [e for e in events if e.type == ecodes.EV_KEY and e.code == ecodes.KEY_A and e.value == 1]
ups = [e for e in events if e.type == ecodes.EV_KEY and e.code == ecodes.KEY_A and e.value == 0]
print(f"raw sent: 7 downs, 7 ups | clone saw: {len(downs)} downs, {len(ups)} ups")
check("chatter suppressed (5 of 7 downs forwarded)", len(downs) == 5, f"got {len(downs)}")

# 4. device disappears -> filter should disengage; then reappear -> re-engage
ui.close()
time.sleep(4.0)
ui2 = UInput({ecodes.EV_KEY: KEYS}, name=NAME)
clone2 = find_clone()
check("filter re-attached after re-enumeration", clone2 is not None)
if clone2 is not None:
    ui2.write(ecodes.EV_KEY, ecodes.KEY_A, 1)
    ui2.syn()
    time.sleep(0.05)
    ui2.write(ecodes.EV_KEY, ecodes.KEY_A, 0)
    ui2.syn()
    evs = collect(clone2, 1.0)
    got = [e for e in evs if e.type == ecodes.EV_KEY and e.code == ecodes.KEY_A and e.value == 1]
    check("press forwarded after re-attach", len(got) == 1, f"got {len(got)}")

# 5. cleanup + inspect filter log
ui2.close()
time.sleep(0.5)
proc.terminate()
try:
    out, _ = proc.communicate(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()
    out, _ = proc.communicate()
print("---- filter log ----")
print(out)
check("log shows suppression", "suppressed bounce" in out)
check("log shows disengage+re-engage", out.count("engaging") >= 2 and "disengaged" in out)

print("RESULT:", "ALL PASS" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
