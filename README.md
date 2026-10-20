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
3. Forwards every event to the clone — except same-key key-down events caught by two bounce rules:
   - **repeat rule** — a press arriving within `--threshold` ms (default **75**) of the previous *press*;
   - **release rule** — a press arriving within `--release-gap` ms (default **30**) of the previous *release*. This catches "release-bounce" blips that arrive long after the previous press but immediately after its release (observed signature on real hardware: exactly 22 ms, while legitimate fast typing never went below 39 ms).
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

| Option | Default | Use case |
|---|---|---|
| `--threshold` | 75 ms | repeat rule — mild chatter, fast-paced gaming |
| `--release-gap` | 30 ms | release rule — release-bounce blips; raise toward 35–40 only if your fastest legitimate same-key retaps exceed 40 ms |

Edit `/etc/systemd/system/kbd-debounce.service`, then:

```bash
sudo systemctl daemon-reload && sudo systemctl restart kbd-debounce
```

## Limitations

- Bounce artifacts arriving **more than 30 ms after a release** (or >75 ms after a press) are indistinguishable from deliberate fast retaps and pass through. On the hardware this was built for, every observed artifact fell well inside those windows; if yours doesn't, raise the thresholds carefully — too high and fast double letters get eaten.
- When the blip comes *first* and the real press second, the filter keeps the short blip as the registered press (text is correct; a long hold on that press is not preserved).
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
