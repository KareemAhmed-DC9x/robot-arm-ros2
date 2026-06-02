#!/usr/bin/env python3
"""
stm32_encoder.py
================
Professional Python bridge for the STM32 Encoder + Limit Switch firmware.
Raspberry Pi 5  ←UART→  STM32

Features
--------
  • Threaded non-blocking RX / TX
  • Full command API  (LIMIT / ENCODER / COUNT / RESET / GRIPPER)
  • Response parser  with typed data classes
  • Callback system for live events
  • Colorised terminal output
  • Interactive CLI

Usage
-----
  # Interactive CLI
  python3 stm32_encoder.py

  # As a module
  from stm32_encoder import STM32Bridge
  bridge = STM32Bridge('/dev/ttyAMA0')
  counts = bridge.get_all_counts()
"""

import queue
import re
import serial
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional

# ══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════
DEFAULT_PORT     = '/dev/ttyAMA2'
DEFAULT_BAUD     = 115200
NUM_CHANNELS     = 6
RESPONSE_TIMEOUT = 3.0    # seconds to wait for a reply
TX_THROTTLE_S    = 0.02   # min delay between sends

# ══════════════════════════════════════════════════════════════
#  TERMINAL COLOURS
# ══════════════════════════════════════════════════════════════
class C:
    RST  = '\033[0m'
    BOLD = '\033[1m'
    DIM  = '\033[2m'
    CYAN = '\033[96m'
    GRN  = '\033[92m'
    YEL  = '\033[93m'
    RED  = '\033[91m'
    MAG  = '\033[95m'
    BLU  = '\033[94m'
    WHT  = '\033[97m'

def _ts() -> str:
    return datetime.now().strftime('%H:%M:%S.%f')[:-3]

def _print_rx(line: str):
    """Colour-coded RX display."""
    if   line.startswith('[STM32 ERROR]'): clr = C.RED
    elif line.startswith('[STM32 DEBUG]'): clr = C.DIM + C.YEL
    elif line.startswith('[STM32 ECHO]'):  clr = C.DIM
    elif line.startswith('[STM32 TX]'):    clr = C.DIM + C.BLU
    elif 'ACTIVE' in line and 'NOT' not in line: clr = C.GRN
    elif 'NOT_ACTIVE' in line:             clr = C.DIM
    elif '_COUNT:' in line:                clr = C.CYAN
    elif '_STATE:' in line:                clr = C.MAG
    else:                                  clr = C.WHT
    print(f'  {C.DIM}{_ts()}{C.RST}  {clr}{line}{C.RST}')


# ══════════════════════════════════════════════════════════════
#  DATA TYPES
# ══════════════════════════════════════════════════════════════
class LimitState(Enum):
    ACTIVE     = 'ACTIVE'
    NOT_ACTIVE = 'NOT_ACTIVE'
    UNKNOWN    = 'UNKNOWN'

class EncoderLevel(Enum):
    LOW    = 'LOW'
    HIGH   = 'HIGH'
    UNKNOWN = 'UNKNOWN'

class GripperState(Enum):
    OPEN     = 'OPEN'
    CLOSED   = 'CLOSED'
    OPENING  = 'OPENING'
    CLOSING  = 'CLOSING'
    UNKNOWN  = 'UNKNOWN'

@dataclass
class GripperStatus:
    state: GripperState = GripperState.UNKNOWN
    count: int = 0

@dataclass
class LimitStatus:
    channel: int                         # 1-based
    state:   LimitState = LimitState.UNKNOWN

@dataclass
class EncoderStatus:
    channel: int
    level:   EncoderLevel = EncoderLevel.UNKNOWN

@dataclass
class CountStatus:
    channel: int
    count:   int = 0

@dataclass
class STM32Response:
    """Parsed aggregate response from a multi-line reply."""
    raw_lines:      List[str]                   = field(default_factory=list)
    limits:         Dict[int, LimitStatus]      = field(default_factory=dict)
    encoder_levels: Dict[int, EncoderStatus]    = field(default_factory=dict)
    counts:         Dict[int, CountStatus]      = field(default_factory=dict)
    gripper:        Optional[GripperStatus]     = None
    errors:         List[str]                   = field(default_factory=list)
    ok:             bool                        = True


# ══════════════════════════════════════════════════════════════
#  RESPONSE PARSER
# ══════════════════════════════════════════════════════════════
# Compiled patterns
_RE_LIMIT   = re.compile(r'^LIMIT_(\d+):\s*(ACTIVE|NOT_ACTIVE)')
_RE_ENC_ST  = re.compile(r'^ENCODER_(\d+)_STATE:\s*(LOW|HIGH)')
_RE_COUNT   = re.compile(r'^ENCODER_(\d+)_COUNT:\s*(-?\d+)')
_RE_ERROR   = re.compile(r'^\[STM32 ERROR\]\s*(.*)')
_RE_RESET   = re.compile(r'^\[STM32\].*reset', re.I)

_RE_GRIPPER_STATE = re.compile(
    r'^\[GRIPPER\]\s*STATE:\s*(OPEN|CLOSED)(?:\s*\[(OPENING|CLOSING)\])?\s*count=(-?\d+)',
    re.I
)
_RE_GRIPPER_COUNT = re.compile(
    r'^\[GRIPPER\]\s*COUNT:\s*(-?\d+)',
    re.I
)
_RE_GRIPPER_DONE = re.compile(
    r'^\[GRIPPER\]\s*(OPEN|CLOSED).*count=(-?\d+)',
    re.I
)

def parse_lines(lines: List[str]) -> STM32Response:
    resp = STM32Response(raw_lines=lines)
    for line in lines:
        m = _RE_LIMIT.match(line)
        if m:
            ch  = int(m.group(1))
            st  = LimitState.ACTIVE if m.group(2) == 'ACTIVE' else LimitState.NOT_ACTIVE
            resp.limits[ch] = LimitStatus(ch, st)
            continue

        m = _RE_ENC_ST.match(line)
        if m:
            ch  = int(m.group(1))
            lv  = EncoderLevel.LOW if m.group(2) == 'LOW' else EncoderLevel.HIGH
            resp.encoder_levels[ch] = EncoderStatus(ch, lv)
            continue

        m = _RE_COUNT.match(line)
        if m:
            ch  = int(m.group(1))
            cnt = int(m.group(2))
            resp.counts[ch] = CountStatus(ch, cnt)
            continue

        m = _RE_ERROR.match(line)
        if m:
            resp.errors.append(m.group(1))
            resp.ok = False
            continue

        # Gripper parsing
        m = _RE_GRIPPER_STATE.match(line)
        if m:
            base_state = m.group(1).upper()
            moving     = m.group(2)
            cnt        = int(m.group(3))
            if moving:
                st = GripperState.OPENING if moving.upper() == 'OPENING' else GripperState.CLOSING
            else:
                st = GripperState.OPEN if base_state == 'OPEN' else GripperState.CLOSED
            resp.gripper = GripperStatus(st, cnt)
            continue
        m = _RE_GRIPPER_COUNT.match(line)
        if m:
            cnt = int(m.group(1))
            resp.gripper = GripperStatus(GripperState.UNKNOWN, cnt)
            continue
        m = _RE_GRIPPER_DONE.match(line)
        if m:
            st  = GripperState.OPEN if m.group(1).upper() == 'OPEN' else GripperState.CLOSED
            cnt = int(m.group(2))
            resp.gripper = GripperStatus(st, cnt)
            continue

    return resp


# ══════════════════════════════════════════════════════════════
#  STM32 BRIDGE
# ══════════════════════════════════════════════════════════════
class STM32Bridge:
    """
    Thread-safe UART bridge to STM32 encoder/limit/gripper firmware.

    Quick start
    -----------
    bridge = STM32Bridge()
    bridge.reset_all()
    counts = bridge.get_all_counts()        # {1: 0, 2: 0, ...}
    limits = bridge.get_all_limits()        # {1: LimitState.NOT_ACTIVE, ...}
    bridge.gripper_open()
    bridge.close()
    """

    def __init__(
        self,
        port:     str   = DEFAULT_PORT,
        baudrate: int   = DEFAULT_BAUD,
        timeout:  float = RESPONSE_TIMEOUT,
        verbose:  bool  = True,
        on_heartbeat: Optional[Callable[[str], None]] = None,
        on_debug:     Optional[Callable[[str], None]] = None,
    ):
        self._port    = port
        self._timeout = timeout
        self._verbose = verbose
        self._running = True

        # Callbacks for unsolicited messages
        self._on_heartbeat = on_heartbeat
        self._on_debug     = on_debug

        # Response collection
        self._resp_lock  = threading.Lock()
        self._resp_lines: List[str] = []
        self._resp_event = threading.Event()
        self._collecting = False          # True while awaiting reply

        # TX queue
        self._tx_queue: queue.Queue[str] = queue.Queue()

        # Open serial
        try:
            self._ser = serial.Serial(port, baudrate, timeout=1)
            time.sleep(1.0)
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
        except serial.SerialException as e:
            raise RuntimeError(f'Cannot open {port}: {e}') from e

        # Start threads
        threading.Thread(target=self._rx_thread, daemon=True, name='STM32-RX').start()
        threading.Thread(target=self._tx_thread, daemon=True, name='STM32-TX').start()

        if self._verbose:
            print(f'{C.GRN}✔ STM32Bridge connected  →  {port} @ {baudrate}{C.RST}')

    # ── Internal threads ────────────────────────────────────────
    def _rx_thread(self):
        while self._running:
            try:
                raw  = self._ser.readline()
                line = raw.decode(errors='ignore').strip()
                if not line:
                    continue
                self._dispatch(line)
            except Exception:
                pass

    def _tx_thread(self):
        while self._running:
            try:
                cmd = self._tx_queue.get(timeout=0.5)
                self._ser.write((cmd + '\n').encode())
                self._ser.flush()
            except queue.Empty:
                continue
            except Exception:
                pass

    def _dispatch(self, line: str):
        """Route incoming line to correct handler."""
        # Always print if verbose
        if self._verbose:
            _print_rx(line)

        is_noise = (
            line.startswith('[STM32 TX]')   or
            line.startswith('[STM32 DEBUG]') or
            line.startswith('[STM32 ECHO]')
        )

        # Heartbeat callback
        if line.startswith('[STM32 TX]') and self._on_heartbeat:
            self._on_heartbeat(line)
            return

        # Debug callback
        if line.startswith('[STM32 DEBUG]') and self._on_debug:
            self._on_debug(line)

        # If we're collecting a response, accumulate data lines
        if self._collecting and not is_noise:
            with self._resp_lock:
                self._resp_lines.append(line)
            # Signal when we see the end sentinel or error
            if (line.startswith('[STM32]') or
                    line.startswith('[STM32 ERROR]')):
                self._resp_event.set()

    # ── Low-level send ───────────────────────────────────────────
    def _send(self, cmd: str) -> STM32Response:
        """
        Send a command, wait for full response, return parsed STM32Response.
        """
        with self._resp_lock:
            self._resp_lines.clear()
        self._resp_event.clear()
        self._collecting = True

        self._tx_queue.put(cmd)
        if self._verbose:
            print(f'{C.CYAN}  → {cmd}{C.RST}')

        # Wait for terminal line or timeout
        got = self._resp_event.wait(timeout=self._timeout)
        self._collecting = False

        with self._resp_lock:
            lines = list(self._resp_lines)

        if not got and not lines:
            if self._verbose:
                print(f'{C.RED}  ⚠ Timeout waiting for response to: {cmd}{C.RST}')
            return STM32Response(ok=False, errors=['Timeout'])

        return parse_lines(lines)

    def _send_query(self, cmd: str) -> STM32Response:
        """
        For LIMIT/ENCODER/COUNT/GRIPPER queries:
        The reply ends with the last data line (no [STM32] footer).
        We use a timed collection window instead.
        """
        with self._resp_lock:
            self._resp_lines.clear()
        self._resp_event.clear()
        self._collecting = True

        self._tx_queue.put(cmd)
        if self._verbose:
            print(f'{C.CYAN}  → {cmd}{C.RST}')

        # Collect for a short window after last byte
        deadline = time.time() + self._timeout
        last_len = 0
        while time.time() < deadline:
            time.sleep(0.05)
            with self._resp_lock:
                cur_len = len(self._resp_lines)
            if cur_len != last_len:
                last_len  = cur_len
                deadline  = time.time() + 0.2   # extend on new data

        self._collecting = False

        with self._resp_lock:
            lines = list(self._resp_lines)

        return parse_lines(lines)

    # ══════════════════════════════════════════════════════════
    #  PUBLIC API
    # ══════════════════════════════════════════════════════════

    # ── Limit Switches ─────────────────────────────────────────
    def get_limit(self, ch: int) -> LimitState:
        """Read single limit switch state. ch = 1-6."""
        r = self._send_query(f'LIMIT {ch}')
        return r.limits.get(ch, LimitStatus(ch)).state

    def get_all_limits(self) -> Dict[int, LimitState]:
        """Read all 6 limit switch states. Returns {1: LimitState, ...}"""
        r = self._send_query('LIMIT ALL')
        return {ch: s.state for ch, s in r.limits.items()}

    # ── Encoder Logic Level ────────────────────────────────────
    def get_encoder_level(self, ch: int) -> EncoderLevel:
        """Read current pin logic level of encoder ch. ch = 1-6."""
        r = self._send_query(f'ENCODER {ch}')
        return r.encoder_levels.get(ch, EncoderStatus(ch)).level

    def get_all_encoder_levels(self) -> Dict[int, EncoderLevel]:
        """Read all 6 encoder logic levels."""
        r = self._send_query('ENCODER ALL')
        return {ch: s.level for ch, s in r.encoder_levels.items()}

    # ── Encoder Counts ─────────────────────────────────────────
    def get_count(self, ch: int) -> int:
        """Read pulse count for encoder ch. ch = 1-6."""
        r = self._send_query(f'COUNT {ch}')
        return r.counts.get(ch, CountStatus(ch)).count

    def get_all_counts(self) -> Dict[int, int]:
        """Read all 6 encoder pulse counts. Returns {1: int, ...}"""
        r = self._send_query('COUNT ALL')
        return {ch: s.count for ch, s in r.counts.items()}

    # ── Reset ──────────────────────────────────────────────────
    def reset_count(self, ch: int) -> bool:
        """Reset single encoder counter. Returns True on success."""
        r = self._send(f'RESET {ch}')
        return r.ok and not r.errors

    def reset_all(self) -> bool:
        """Reset all 6 encoder counters."""
        r = self._send('RESET ALL')
        return r.ok and not r.errors

    # ── Gripper ──────────────────────────────────────────────
    def gripper_open(self) -> bool:
        """Open gripper."""
        r = self._send('GRIPPER OPEN')
        return r.ok and not r.errors

    def gripper_close(self) -> bool:
        """Close gripper."""
        r = self._send('GRIPPER CLOSE')
        return r.ok and not r.errors

    def gripper_stop(self) -> bool:
        """Stop gripper movement."""
        r = self._send('GRIPPER STOP')
        return r.ok and not r.errors

    def gripper_reset(self) -> bool:
        """Reset gripper counter (home)."""
        r = self._send('GRIPPER RESET')
        return r.ok and not r.errors

    def get_gripper_count(self) -> int:
        """Get current gripper count."""
        r = self._send_query('GRIPPER COUNT')
        if r.gripper:
            return r.gripper.count
        return 0

    def get_gripper_state(self) -> GripperStatus:
        """Get current gripper state and count."""
        r = self._send_query('GRIPPER STATE')
        if r.gripper:
            return r.gripper
        return GripperStatus()

    # ── Raw ────────────────────────────────────────────────────
    def raw(self, cmd: str) -> STM32Response:
        """Send any raw command string and return parsed response."""
        return self._send_query(cmd)

    # ── Helpers ────────────────────────────────────────────────
    def print_all_status(self):
        """Print a formatted status table of all channels and gripper."""
        counts = self.get_all_counts()
        limits = self.get_all_limits()
        levels = self.get_all_encoder_levels()

        print(f'\n{C.BOLD}{"─"*62}{C.RST}')
        print(f'{C.BOLD}  CH  │  LIMIT          │  ENCODER        │  COUNT{C.RST}')
        print(f'{C.BOLD}{"─"*62}{C.RST}')

        for ch in range(1, NUM_CHANNELS + 1):
            lm  = limits.get(ch, LimitState.UNKNOWN)
            lv  = levels.get(ch, EncoderLevel.UNKNOWN)
            cnt = counts.get(ch, 0)

            lm_c  = C.GRN  if lm  == LimitState.ACTIVE     else C.DIM
            lv_c  = C.MAG  if lv  == EncoderLevel.LOW       else C.DIM
            cnt_c = C.CYAN if cnt > 0                        else C.DIM

            print(
                f'  {C.BOLD}{ch:>2}{C.RST}  │  '
                f'{lm_c}{lm.value:<15}{C.RST}│  '
                f'{lv_c}{lv.value:<15}{C.RST}│  '
                f'{cnt_c}{cnt}{C.RST}'
            )

        # ── Gripper Status ────────────────────────────────
        g = self.get_gripper_state()
        if g.state in (GripperState.OPEN, GripperState.OPENING):
            gclr = C.GRN
        elif g.state in (GripperState.CLOSED, GripperState.CLOSING):
            gclr = C.RED
        else:
            gclr = C.DIM
        print(f'\n{C.BOLD}  GRIPPER STATUS{C.RST}')
        print(f'  STATE : {gclr}{g.state.value}{C.RST}')
        print(f'  COUNT : {C.CYAN}{g.count}{C.RST}')

        print(f'{C.BOLD}{"─"*62}{C.RST}\n')

    # ── Lifecycle ──────────────────────────────────────────────
    def close(self):
        self._running = False
        time.sleep(0.2)
        try:
            self._ser.close()
        except Exception:
            pass
        if self._verbose:
            print(f'{C.YEL}✔ STM32Bridge closed{C.RST}')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ══════════════════════════════════════════════════════════════
#  LIVE MONITOR
# ══════════════════════════════════════════════════════════════
def live_monitor(bridge: STM32Bridge, interval: float = 1.0):
    """
    Continuously poll all channels and print a refreshing table.
    Press Ctrl-C to stop.
    """
    print(f'{C.CYAN}Live monitor  —  {interval}s refresh  —  Ctrl-C to stop{C.RST}\n')
    try:
        while True:
            bridge.print_all_status()
            time.sleep(interval)
    except KeyboardInterrupt:
        print(f'\n{C.YEL}Monitor stopped.{C.RST}')


# ══════════════════════════════════════════════════════════════
#  INTERACTIVE CLI
# ══════════════════════════════════════════════════════════════
MENU = f"""
{C.BOLD}{C.CYAN}╔══════════════════════════════════════════╗
║   STM32  ENCODER + LIMIT + GRIPPER       ║
╠══════════════════════════════════════════╣{C.RST}
{C.BOLD}  ls{C.RST}  │  la    → Limit: single / all
{C.BOLD}  es{C.RST}  │  ea    → Encoder state: single / all
{C.BOLD}  cs{C.RST}  │  ca    → Count: single / all
{C.BOLD}  rs{C.RST}  │  ra    → Reset: single / all
{C.BOLD}  go{C.RST}  │  gc    → Gripper: open / close
{C.BOLD}  gs{C.RST}  │  gx    → Gripper: state / stop
{C.BOLD}  gr{C.RST}  │  gct   → Gripper: reset / count
{C.BOLD}  st{C.RST}          → Full status table
{C.BOLD}  mon{C.RST}         → Live monitor (1 s refresh)
{C.BOLD}  raw{C.RST}         → Send raw command
{C.BOLD}  q{C.RST}           → Quit
{C.CYAN}╚══════════════════════════════════════════╝{C.RST}
"""

def _ask_ch(prompt: str = 'Channel (1-6)') -> int:
    try:
        return int(input(f'  {prompt}: ').strip())
    except ValueError:
        return -1

def run_cli(bridge: STM32Bridge):
    print(MENU)

    while True:
        try:
            cmd = input(f'{C.CYAN}stm32 ❯{C.RST} ').strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if not cmd:
            continue

        # ── Limit ─────────────────────────────────────────────
        elif cmd == 'ls':
            ch = _ask_ch()
            if 1 <= ch <= 6:
                st = bridge.get_limit(ch)
                c  = C.GRN if st == LimitState.ACTIVE else C.DIM
                print(f'  LIMIT_{ch}: {c}{st.value}{C.RST}')
            else:
                print(f'{C.RED}  Invalid channel{C.RST}')

        elif cmd == 'la':
            all_limits = bridge.get_all_limits()
            for ch, st in sorted(all_limits.items()):
                c = C.GRN if st == LimitState.ACTIVE else C.DIM
                print(f'  LIMIT_{ch}: {c}{st.value}{C.RST}')

        # ── Encoder state ──────────────────────────────────────
        elif cmd == 'es':
            ch = _ask_ch()
            if 1 <= ch <= 6:
                lv = bridge.get_encoder_level(ch)
                c  = C.MAG if lv == EncoderLevel.LOW else C.DIM
                print(f'  ENCODER_{ch}_STATE: {c}{lv.value}{C.RST}')
            else:
                print(f'{C.RED}  Invalid channel{C.RST}')

        elif cmd == 'ea':
            all_levels = bridge.get_all_encoder_levels()
            for ch, lv in sorted(all_levels.items()):
                c = C.MAG if lv == EncoderLevel.LOW else C.DIM
                print(f'  ENCODER_{ch}_STATE: {c}{lv.value}{C.RST}')

        # ── Count ──────────────────────────────────────────────
        elif cmd == 'cs':
            ch = _ask_ch()
            if 1 <= ch <= 6:
                cnt = bridge.get_count(ch)
                print(f'  ENCODER_{ch}_COUNT: {C.CYAN}{cnt}{C.RST}')
            else:
                print(f'{C.RED}  Invalid channel{C.RST}')

        elif cmd == 'ca':
            all_counts = bridge.get_all_counts()
            for ch, cnt in sorted(all_counts.items()):
                c = C.CYAN if cnt > 0 else C.DIM
                print(f'  ENCODER_{ch}_COUNT: {c}{cnt}{C.RST}')

        # ── Reset ──────────────────────────────────────────────
        elif cmd == 'rs':
            ch = _ask_ch()
            if 1 <= ch <= 6:
                ok = bridge.reset_count(ch)
                print(f'  {"✔" if ok else "✗"} Encoder {ch} reset')
            else:
                print(f'{C.RED}  Invalid channel{C.RST}')

        elif cmd == 'ra':
            ok = bridge.reset_all()
            print(f'  {"✔" if ok else "✗"} All encoders reset')

        # ── Gripper ─────────────────────────────────────────
        elif cmd == 'go':
            ok = bridge.gripper_open()
            print(f'  {"✔" if ok else "✗"} Gripper OPEN')
        elif cmd == 'gc':
            ok = bridge.gripper_close()
            print(f'  {"✔" if ok else "✗"} Gripper CLOSE')
        elif cmd == 'gx':
            ok = bridge.gripper_stop()
            print(f'  {"✔" if ok else "✗"} Gripper STOP')
        elif cmd == 'gr':
            ok = bridge.gripper_reset()
            print(f'  {"✔" if ok else "✗"} Gripper RESET')
        elif cmd == 'gct':
            cnt = bridge.get_gripper_count()
            print(f'  GRIPPER_COUNT: {C.CYAN}{cnt}{C.RST}')
        elif cmd == 'gs':
            st = bridge.get_gripper_state()
            if st.state in (GripperState.OPEN, GripperState.OPENING):
                c = C.GRN
            elif st.state in (GripperState.CLOSED, GripperState.CLOSING):
                c = C.RED
            else:
                c = C.DIM
            print(f'  GRIPPER_STATE: {c}{st.state.value}{C.RST}')
            print(f'  GRIPPER_COUNT: {C.CYAN}{st.count}{C.RST}')

        # ── Status table ───────────────────────────────────────
        elif cmd == 'st':
            bridge.print_all_status()

        # ── Live monitor ───────────────────────────────────────
        elif cmd == 'mon':
            try:
                iv = float(input('  Refresh interval (s) [1.0]: ').strip() or '1.0')
            except ValueError:
                iv = 1.0
            live_monitor(bridge, iv)

        # ── Raw command ────────────────────────────────────────
        elif cmd == 'raw':
            raw_cmd = input('  Raw command: ').strip()
            if raw_cmd:
                bridge.raw(raw_cmd)

        elif cmd in ('q', 'quit', 'exit'):
            break

        elif cmd in ('?', 'h', 'help'):
            print(MENU)

        else:
            print(f'{C.DIM}  Unknown command — type h for help{C.RST}')

    bridge.close()


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════
def main():
    import argparse

    ap = argparse.ArgumentParser(
        description='STM32 Encoder + Limit Switch + Gripper Python Bridge'
    )
    ap.add_argument('--port',    default=DEFAULT_PORT, help='Serial port (default: /dev/ttyAMA0)')
    ap.add_argument('--baud',    default=DEFAULT_BAUD,  type=int, help='Baud rate (default: 115200)')
    ap.add_argument('--quiet',   action='store_true',   help='Suppress raw RX output')
    ap.add_argument('--monitor', action='store_true',   help='Start live monitor immediately')
    ap.add_argument('--status',  action='store_true',   help='Print status table and exit')
    ap.add_argument('--counts',  action='store_true',   help='Print counts and exit')
    ap.add_argument('--limits',  action='store_true',   help='Print limits and exit')
    ap.add_argument('--reset',   action='store_true',   help='Reset all counters and exit')
    args = ap.parse_args()

    try:
        bridge = STM32Bridge(
            port     = args.port,
            baudrate = args.baud,
            verbose  = not args.quiet,
        )
    except RuntimeError as e:
        print(f'{C.RED}✗ {e}{C.RST}')
        sys.exit(1)

    # Non-interactive modes
    if args.reset:
        bridge.reset_all()
        bridge.close()
        return

    if args.counts:
        counts = bridge.get_all_counts()
        for ch, cnt in sorted(counts.items()):
            print(f'ENCODER_{ch}_COUNT: {cnt}')
        bridge.close()
        return

    if args.limits:
        limits = bridge.get_all_limits()
        for ch, st in sorted(limits.items()):
            print(f'LIMIT_{ch}: {st.value}')
        bridge.close()
        return

    if args.status:
        bridge.print_all_status()
        bridge.close()
        return

    if args.monitor:
        live_monitor(bridge)
        bridge.close()
        return

    # Interactive CLI
    run_cli(bridge)


if __name__ == '__main__':
    main() 
