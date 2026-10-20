#!/usr/bin/env python3
"""Keyboard debounce filter for Linux (key chatter / double-typing fix).

Grabs a keyboard's evdev device, creates a virtual clone via uinput, and
suppresses rapid duplicate key-down events for the same key. Normal typing,
held-key repeats and key-up events pass through unchanged.

Unlike simple filters, this one:
  * waits for the keyboard to appear (safe to start before it's plugged in)
  * re-attaches automatically after disconnects / USB re-enumerations

Usage:
    kbd-debounce.py --list
    kbd-debounce.py --name "Logitech G915 X LS" [--threshold 75]

Approach adapted from markdborden/kb-debounce (MIT).
"""
import argparse
import selectors
import signal
import sys
import time

import evdev
from evdev import UInput, ecodes

VERSION = "1.0.0"
STOP = False
MIN_KEYS = 100  # a full keyboard map; filters out media-key subdevices


def log(msg):
    print(msg, flush=True)


def list_keyboards():
    """List candidate keyboard devices (full keymaps only)."""
    print("Candidate keyboard devices:\n")
    found = False
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
        except OSError:
            continue
        name = dev.name or ""
        if "(debounced)" in name:
            dev.close()
            continue
        keys = dev.capabilities(verbose=False).get(ecodes.EV_KEY, [])
        if len(keys) > MIN_KEYS:
            print(f"  {path}  {name}  ({len(keys)} keys)")
            found = True
        dev.close()
    if not found:
        print("  (none found)")
    print('\nUse:  kbd-debounce.py --name "<part of the name>"')


def find_device(name_fragment):
    """Find the main keyboard evdev device whose name contains the fragment.

    Subdevices (e.g. 'X Consumer Control') share the base name as a prefix,
    so prefer an exact name match, then the shortest matching name.
    """
    candidates = []
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
        except OSError:
            continue
        name = dev.name or ""
        if "(debounced)" in name or name_fragment.lower() not in name.lower():
            dev.close()
            continue
        keys = dev.capabilities(verbose=False).get(ecodes.EV_KEY, [])
        if len(keys) > MIN_KEYS:
            candidates.append(dev)
        else:
            dev.close()
    if not candidates:
        return None
    candidates.sort(key=lambda d: (d.name.lower() != name_fragment.lower(), len(d.name)))
    best = candidates[0]
    for extra in candidates[1:]:
        extra.close()
    return best


def run(dev, threshold_ms):
    log(f"engaging: {dev.path} {dev.name!r} threshold={threshold_ms}ms")
    ui = UInput.from_device(dev, name=f"{dev.name} (debounced)")
    dev.grab()
    sel = selectors.DefaultSelector()
    sel.register(dev.fd, selectors.EVENT_READ)
    last_down = {}
    threshold = threshold_ms / 1000.0
    try:
        while not STOP:
            for _ in sel.select(timeout=1.0):
                for event in dev.read():
                    if event.type == ecodes.EV_KEY and event.value == 1:
                        now = time.monotonic()
                        prev = last_down.get(event.code)
                        if prev is not None and now - prev < threshold:
                            keyname = ecodes.KEY.get(event.code, event.code)
                            log(
                                f"suppressed bounce: key {keyname} "
                                f"{(now - prev) * 1000:.1f}ms after previous press"
                            )
                            continue
                        last_down[event.code] = now
                    ui.write_event(event)
                    ui.syn()
    except OSError as exc:
        log(f"device lost: {exc}")
    finally:
        sel.close()
        try:
            dev.ungrab()
        except OSError:
            pass
        ui.close()
        dev.close()
        log("disengaged")


def main():
    ap = argparse.ArgumentParser(description="Debounce filter for chattering keyboards")
    ap.add_argument("--name", help="substring of the keyboard device name")
    ap.add_argument("--threshold", type=int, default=75, help="debounce threshold in ms (default 75)")
    ap.add_argument("--list", action="store_true", help="list candidate keyboard devices and exit")
    ap.add_argument("--version", action="version", version=f"kbd-debounce {VERSION}")
    args = ap.parse_args()

    if args.list:
        list_keyboards()
        return
    if not args.name:
        ap.error("--name is required (or use --list)")

    def stop(*_):
        global STOP
        STOP = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    log(f"kbd-debounce {VERSION}: waiting for keyboard matching {args.name!r} ...")
    while not STOP:
        dev = find_device(args.name)
        if dev is None:
            time.sleep(2)
            continue
        run(dev, args.threshold)
        if not STOP:
            time.sleep(2)
    log("stopped")


if __name__ == "__main__":
    main()
