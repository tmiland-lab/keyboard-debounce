# kbd-debounce

Software debounce filter for chattering mechanical keyboards on Linux. Fixes double-typing / repeated letters caused by switch contact bounce — without replacing the switch.

## The problem

Key chatter: one physical keypress registers as two (or more). You type `p` and get `pp`. It's caused by worn or dirty switch contacts that bounce on press/release, combined with a firmware debounce that is too weak to filter it out.

Typical raw evidence, captured at the kernel evdev level with all software excluded:

```
press  5: t=...043.774  hold= 22.0ms   <- spurious blip
press  6: t=...043.818  hold=220.0ms   <- the real press, only 44ms later
```

Two key-down events 44 ms apart from one physical press = 22 taps per second. Physically impossible by hand — that's the switch bouncing.

## How it works

1. Finds your keyboard's evdev device (matched by a substring of its name).
2. Grabs it exclusively and creates a virtual clone via `uinput`.
3. Forwards every event to the clone — except same-key key-down events arriving within the threshold (default **75 ms**) of the previous press, which are dropped as bounces.
4. Waits for the keyboard to appear and **re-attaches automatically** after disconnects / USB re-enumerations.

Normal typing, held keys and key repeats are unaffected: deliberate double-taps are ≥100–150 ms apart, well above the default threshold.

## Requirements

- Linux with evdev + uinput
- Python 3 with [python-evdev](https://python-evdev.readthedocs.io/) — `sudo apt install python3-evdev` on Debian/Ubuntu
- root for the systemd service (or membership in the `input` group for manual runs)

## Install

```bash
# list candidate keyboards to get the exact name
sudo python3 kbd-debounce.py --list

# install as a systemd service
sudo ./install.sh --name "Logitech G915 X LS" --threshold 75
```

## Verify it's working

```bash
journalctl -u kbd-debounce.service -f
```

While you type, caught bounces appear in real time:

```
suppressed bounce: key KEY_P 44.0ms after previous press
```

## Tuning

| Threshold | Use case |
|---|---|
| 50 ms | mild chatter, fast-paced gaming |
| **75 ms** | default — most worn switches |
| 100 ms | severe chatter (may start eating very fast deliberate double-taps) |

Edit `/etc/systemd/system/kbd-debounce.service`, then:

```bash
sudo systemctl daemon-reload && sudo systemctl restart kbd-debounce
```

## Limitations

- Only **fast** bounces are filtered. Slow release-bounce artifacts (e.g. 200–450 ms after a press) are indistinguishable from deliberate fast double-presses and pass through.
- While engaged, the physical device is grabbed: software that reads `/dev/input/eventN` directly must use the `(debounced)` clone instead.
- This is a **band-aid, not a repair**. For a genuinely worn switch, cleaning (compressed air / 99% isopropyl alcohol) or a warranty replacement is the real fix.

## Uninstall

```bash
sudo ./uninstall.sh
```

## Test

End-to-end test using a fake `uinput` keyboard — no real keyboard is touched:

```bash
sudo python3 test_kbd_debounce.py
```

It verifies: wait-for-device, grab + clone, chatter suppression, normal pass-through, and automatic re-attach after re-enumeration.

## Credits

- Approach adapted from [kb-debounce](https://github.com/markdborden/kb-debounce) (MIT).
- Similar tools: [KeyboardChatteringFix-Linux](https://github.com/finkrer/KeyboardChatteringFix-Linux) (Linux), G915 Stutter Fix (Windows), Windows FilterKeys.

## License

MIT — see [LICENSE](LICENSE).
