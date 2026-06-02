#!/usr/bin/env python3
"""
stm32_encoder.py
================
Professional Python bridge for the STM32 Encoder + Limit Switch firmware.
Optimized for ultra‑fast response (low latency, minimal printing).
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

# ── Defaults ──────────────────────────────────────────────────────
DEFAULT_PORT = '/dev/ttyAMA2'
DEFAULT_BAUD = 115200               # متوافق مع سرعة الـ Firmware الحالية (115200)
NUM_CHANNELS = 6
NUM_LIMITS   = 8
RESPONSE_TIMEOUT = 1.5              # تم التخفيض من 3.0 إلى 1.5 ثانية لتسريع الاستجابة
TX_THROTTLE_S    = 0.01             # تم التخفيض من 0.02

# ── ANSI colors (للطباعة الاختيارية – معطلة افتراضياً) ───────────
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

def _print_rx(line: str, verbose: bool):
    if not verbose:
        return
    # ... (نفس الكود القديم مع إضافة شرط verbose)
    if line.startswith('[STM32 ERROR]'): clr = C.RED
    elif line.startswith('[STM32 DEBUG]'): clr = C.DIM + C.YEL
    elif line.startswith('[STM32 ECHO]'):  clr = C.DIM
    elif line.startswith('[STM32 TX]'):    clr = C.DIM + C.BLU
    elif 'ACTIVE' in line and 'NOT' not in line: clr = C.GRN
    elif 'NOT_ACTIVE' in line:             clr = C.DIM
    elif '_COUNT:' in line:                clr = C.CYAN
    elif '_STATE:' in line:                clr = C.MAG
    else:                                  clr = C.WHT
    print(f'  {C.DIM}{_ts()}{C.RST}  {clr}{line}{C.RST}')

class LimitState(Enum):
    ACTIVE     = 'ACTIVE'
    NOT_ACTIVE = 'NOT_ACTIVE'
    UNKNOWN    = 'UNKNOWN'

class EncoderLevel(Enum):
    LOW    = 'LOW'
    HIGH   = 'HIGH'
    UNKNOWN = 'UNKNOWN'

@dataclass
class LimitStatus:
    channel: int
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
    raw_lines:      List[str]                   = field(default_factory=list)
    limits:         Dict[int, LimitStatus]      = field(default_factory=dict)
    encoder_levels: Dict[int, EncoderStatus]    = field(default_factory=dict)
    counts:         Dict[int, CountStatus]      = field(default_factory=dict)
    errors:         List[str]                   = field(default_factory=list)
    ok:             bool                        = True

_RE_LIMIT   = re.compile(r'^LIMIT_(\d+):\s*(ACTIVE|NOT_ACTIVE)')
_RE_ENC_ST  = re.compile(r'^ENCODER_(\d+)_STATE:\s*(LOW|HIGH)')
_RE_COUNT   = re.compile(r'^ENCODER_(\d+)_COUNT:\s*(-?\d+)')
_RE_ERROR   = re.compile(r'^\[STM32 ERROR\]\s*(.*)')

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
    return resp

class STM32Bridge:
    def __init__(
        self,
        port:     str   = DEFAULT_PORT,
        baudrate: int   = DEFAULT_BAUD,
        timeout:  float = RESPONSE_TIMEOUT,
        verbose:  bool  = False,          # ← تم تغيير الافتراضي إلى False لتسريع الأداء
        on_heartbeat: Optional[Callable[[str], None]] = None,
        on_debug:     Optional[Callable[[str], None]] = None,
    ):
        self._port    = port
        self._timeout = timeout
        self._verbose = verbose
        self._running = True
        self._on_heartbeat = on_heartbeat
        self._on_debug     = on_debug
        self._resp_lock  = threading.Lock()
        self._resp_lines: List[str] = []
        self._resp_event = threading.Event()
        self._collecting = False
        self._tx_queue: queue.Queue[str] = queue.Queue()
        self._gripper_state = "UNKNOWN"
        self._gripper_count = 0
        try:
            self._ser = serial.Serial(port, baudrate, timeout=0.5)   # تقليل timeout
            time.sleep(0.5)
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
        except serial.SerialException as e:
            raise RuntimeError(f'Cannot open {port}: {e}') from e
        threading.Thread(target=self._rx_thread, daemon=True, name='STM32-RX').start()
        threading.Thread(target=self._tx_thread, daemon=True, name='STM32-TX').start()
        if self._verbose:
            print(f'{C.GRN}✔ STM32Bridge connected  →  {port} @ {baudrate}{C.RST}')

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
                cmd = self._tx_queue.get(timeout=0.2)   # تقليل timeout
                self._ser.write((cmd + '\n').encode())
                self._ser.flush()
            except queue.Empty:
                continue
            except Exception:
                pass

    def _dispatch(self, line: str):
        # طباعة فقط إذا كان verbose مفعّلاً
        if self._verbose:
            _print_rx(line, self._verbose)
        is_noise = (
            line.startswith('[STM32 TX]') or
            line.startswith('[STM32 DEBUG]') or
            line.startswith('[STM32 ECHO]')
        )
        if line.startswith('[STM32 TX]') and self._on_heartbeat:
            self._on_heartbeat(line)
            return
        if line.startswith('[STM32 DEBUG]') and self._on_debug:
            self._on_debug(line)
        if "[GRIPPER]" in line:
            self._parse_gripper_line(line)
        if self._collecting and not is_noise:
            with self._resp_lock:
                self._resp_lines.append(line)
            if (line.startswith('[STM32]') or line.startswith('[STM32 ERROR]')):
                self._resp_event.set()

    def _parse_gripper_line(self, line: str):
        if "STATE:" in line:
            if "OPENING" in line:
                self._gripper_state = "OPENING"
            elif "CLOSING" in line:
                self._gripper_state = "CLOSING"
            elif "OPEN" in line and "CLOSING" not in line:
                self._gripper_state = "OPEN"
            elif "CLOSED" in line:
                self._gripper_state = "CLOSED"
            if "count=" in line:
                try:
                    cnt_str = line.split("count=")[1].split()[0]
                    self._gripper_count = int(cnt_str)
                except:
                    pass
        elif "target reached" in line:
            if "OPEN" in line:
                self._gripper_state = "OPEN"
            elif "CLOSED" in line:
                self._gripper_state = "CLOSED"
            if "count=" in line:
                try:
                    cnt_str = line.split("count=")[1].split()[0]
                    self._gripper_count = int(cnt_str)
                except:
                    pass
        elif "COUNT:" in line:
            try:
                cnt_str = line.split("COUNT:")[1].strip()
                self._gripper_count = int(cnt_str)
            except:
                pass
        elif "Stopped" in line:
            self._gripper_state = "STOPPED"

    def _send(self, cmd: str) -> STM32Response:
        with self._resp_lock:
            self._resp_lines.clear()
        self._resp_event.clear()
        self._collecting = True
        self._tx_queue.put(cmd)
        if self._verbose:
            print(f'{C.CYAN}  → {cmd}{C.RST}')
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
        with self._resp_lock:
            self._resp_lines.clear()
        self._resp_event.clear()
        self._collecting = True
        self._tx_queue.put(cmd)
        if self._verbose:
            print(f'{C.CYAN}  → {cmd}{C.RST}')
        deadline = time.time() + self._timeout
        last_len = 0
        while time.time() < deadline:
            time.sleep(0.02)                     # تقليل زمن الانتظار من 0.05 إلى 0.02
            with self._resp_lock:
                cur_len = len(self._resp_lines)
            if cur_len != last_len:
                last_len = cur_len
                deadline = time.time() + 0.1      # تمديد وقت إضافي 100 مللي ثانية
        self._collecting = False
        with self._resp_lock:
            lines = list(self._resp_lines)
        return parse_lines(lines)

    # ── Public API (بدون تغيير) ────────────────────────────────────
    def get_limit(self, ch: int) -> LimitState:
        if ch < 1 or ch > NUM_LIMITS:
            raise ValueError(f"Limit channel must be 1..{NUM_LIMITS}")
        r = self._send_query(f'LIMIT {ch}')
        return r.limits.get(ch, LimitStatus(ch)).state

    def get_all_limits(self) -> Dict[int, LimitState]:
        r = self._send_query('LIMIT ALL')
        return {ch: s.state for ch, s in r.limits.items()}

    def get_encoder_level(self, ch: int) -> EncoderLevel:
        if ch < 1 or ch > NUM_CHANNELS:
            raise ValueError(f"Encoder channel must be 1..{NUM_CHANNELS}")
        r = self._send_query(f'ENCODER {ch}')
        return r.encoder_levels.get(ch, EncoderStatus(ch)).level

    def get_all_encoder_levels(self) -> Dict[int, EncoderLevel]:
        r = self._send_query('ENCODER ALL')
        return {ch: s.level for ch, s in r.encoder_levels.items()}

    def get_count(self, ch: int) -> int:
        if ch < 1 or ch > NUM_CHANNELS:
            raise ValueError(f"Encoder channel must be 1..{NUM_CHANNELS}")
        r = self._send_query(f'COUNT {ch}')
        return r.counts.get(ch, CountStatus(ch)).count

    def get_all_counts(self) -> Dict[int, int]:
        r = self._send_query('COUNT ALL')
        return {ch: s.count for ch, s in r.counts.items()}

    def reset_count(self, ch: int) -> bool:
        if ch < 1 or ch > NUM_CHANNELS:
            return False
        r = self._send(f'RESET {ch}')
        return r.ok and not r.errors

    def reset_all(self) -> bool:
        r = self._send('RESET ALL')
        return r.ok and not r.errors

    def gripper_command(self, cmd: str) -> bool:
        cmd = cmd.upper().strip()
        valid = ("OPEN", "CLOSE", "STOP", "STATE", "COUNT", "RESET")
        if cmd not in valid:
            if self._verbose:
                print(f'{C.RED}✗ Invalid gripper command: {cmd}{C.RST}')
            return False
        self._tx_queue.put(f"GRIPPER {cmd}")
        if self._verbose:
            print(f'{C.CYAN}  → GRIPPER {cmd}{C.RST}')
        # إزالة أو تقليل sleep لتحسين سرعة الاستجابة
        # time.sleep(0.05)   # تم التعليق
        return True

    def get_gripper_state(self) -> tuple:
        return self._gripper_state, self._gripper_count

    def raw(self, cmd: str) -> STM32Response:
        return self._send_query(cmd)

    def print_all_status(self):
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
            print(f'  {C.BOLD}{ch:>2}{C.RST}  │  {lm_c}{lm.value:<15}{C.RST}│  {lv_c}{lv.value:<15}{C.RST}│  {cnt_c}{cnt}{C.RST}')
        for ch in range(NUM_CHANNELS+1, NUM_LIMITS+1):
            lm = limits.get(ch, LimitState.UNKNOWN)
            lm_c = C.GRN if lm == LimitState.ACTIVE else C.DIM
            print(f'  {C.BOLD}{ch:>2}{C.RST}  │  {lm_c}{lm.value:<15}{C.RST}│  {"":<15}│  {"":<10}{C.RST}')
        print(f'{C.BOLD}{"─"*62}{C.RST}\n')

    def close(self):
        self._running = False
        time.sleep(0.1)
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


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default=DEFAULT_PORT)
    ap.add_argument('--baud', default=DEFAULT_BAUD, type=int)
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()
    bridge = STM32Bridge(port=args.port, baudrate=args.baud, verbose=not args.quiet)
    bridge.print_all_status()
    bridge.close()