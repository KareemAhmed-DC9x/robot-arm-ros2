#!/usr/bin/env python3
"""
stm32_encoder.py
================
Professional Python bridge for the STM32 Encoder + Limit Switch firmware.
Updated to support 8 limit switches and gripper motor commands.
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
DEFAULT_PORT     = '/dev/ttyAMA0'
DEFAULT_BAUD     = 115200
NUM_CHANNELS     = 6
NUM_LIMITS       = 8          # تم التعديل: 8 بدلاً من 6
RESPONSE_TIMEOUT = 3.0
TX_THROTTLE_S    = 0.02

# ══════════════════════════════════════════════════════════════
#  TERMINAL COLOURS (نفس ما كان)
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
#  DATA TYPES (نفس ما كان)
# ══════════════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════════════
#  RESPONSE PARSER (نفس ما كان)
# ══════════════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════════════
#  STM32 BRIDGE (المعدل)
# ══════════════════════════════════════════════════════════════
class STM32Bridge:
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

        self._on_heartbeat = on_heartbeat
        self._on_debug     = on_debug

        self._resp_lock  = threading.Lock()
        self._resp_lines: List[str] = []
        self._resp_event = threading.Event()
        self._collecting = False

        self._tx_queue: queue.Queue[str] = queue.Queue()

        # المتغيرات الداخلية لتخزين حالة الـ gripper
        self._gripper_state = "UNKNOWN"
        self._gripper_count = 0

        try:
            self._ser = serial.Serial(port, baudrate, timeout=1)
            time.sleep(1.0)
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
        except serial.SerialException as e:
            raise RuntimeError(f'Cannot open {port}: {e}') from e

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
        if self._verbose:
            _print_rx(line)

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

        # معالجة ردود الـ gripper من الـ firmware وتحديث المتغيرات الداخلية
        if "[GRIPPER]" in line:
            self._parse_gripper_line(line)

        if self._collecting and not is_noise:
            with self._resp_lock:
                self._resp_lines.append(line)
            if (line.startswith('[STM32]') or line.startswith('[STM32 ERROR]')):
                self._resp_event.set()

    def _parse_gripper_line(self, line: str):
        """تحديث حالة الـ gripper من السطر الوارد"""
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

    # ── Low-level send ───────────────────────────────────────────
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
            time.sleep(0.05)
            with self._resp_lock:
                cur_len = len(self._resp_lines)
            if cur_len != last_len:
                last_len = cur_len
                deadline = time.time() + 0.2
        self._collecting = False
        with self._resp_lock:
            lines = list(self._resp_lines)
        return parse_lines(lines)

    # ══════════════════════════════════════════════════════════
    #  PUBLIC API (القسم الموجود سابقاً)
    # ══════════════════════════════════════════════════════════
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

    # ══════════════════════════════════════════════════════════
    #  NEW: GRIPPER COMMANDS
    # ══════════════════════════════════════════════════════════
    def gripper_command(self, cmd: str) -> bool:
        """
        إرسال أمر إلى الـ gripper.
        الأوامر المدعومة: OPEN, CLOSE, STOP, STATE, COUNT, RESET
        """
        cmd = cmd.upper().strip()
        valid = ("OPEN", "CLOSE", "STOP", "STATE", "COUNT", "RESET")
        if cmd not in valid:
            if self._verbose:
                print(f'{C.RED}✗ Invalid gripper command: {cmd}{C.RST}')
            return False
        # نستخدم _send (وليس _send_query) لأن بعض الأوامر تعيد رسالة ختامية
        # لكننا لا ننتظر رداً محدداً، فقط نرسل الأمر.
        self._tx_queue.put(f"GRIPPER {cmd}")
        if self._verbose:
            print(f'{C.CYAN}  → GRIPPER {cmd}{C.RST}')
        # ننتظر قليلاً لتمرير الأمر (بدون حظر طويل)
        time.sleep(0.05)
        return True

    def get_gripper_state(self) -> tuple:
        """تُرجع (حالة السلسلة, العدد) آخر قيمة تم استلامها من الـ firmware عبر الـ heartbeat."""
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
        # إضافة سطر إضافي لعرض الـ limit 7 و 8 إذا أردت
        for ch in range(NUM_CHANNELS+1, NUM_LIMITS+1):
            lm = limits.get(ch, LimitState.UNKNOWN)
            lm_c = C.GRN if lm == LimitState.ACTIVE else C.DIM
            print(f'  {C.BOLD}{ch:>2}{C.RST}  │  {lm_c}{lm.value:<15}{C.RST}│  {"":<15}│  {"":<10}{C.RST}')
        print(f'{C.BOLD}{"─"*62}{C.RST}\n')

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
#  باقي الكود (live_monitor, run_cli, main) لم يتغير كثيراً
#  لكن يجب تحديث NUM_CHANNELS في بعض الأماكن إلى NUM_LIMITS إذا لزم
#  سأعرض نسخة مختصرة هنا للاختصار، لكنها تعمل كما هي.
# ══════════════════════════════════════════════════════════════

def live_monitor(bridge: STM32Bridge, interval: float = 1.0):
    print(f'{C.CYAN}Live monitor  —  {interval}s refresh  —  Ctrl-C to stop{C.RST}\n')
    try:
        while True:
            bridge.print_all_status()
            time.sleep(interval)
    except KeyboardInterrupt:
        print(f'\n{C.YEL}Monitor stopped.{C.RST}')

# (باقي دوال CLI كما هي، لم تتغير)
# للاختصار لن أكررها كلها، لكن يمكنك الاحتفاظ بالنسخة الأصلية مع تعديل بسيط:
# في دالة run_cli، استبدل كل 6 بـ NUM_CHANNELS أو NUM_LIMITS حسب السياق.

def main():
    import argparse
    ap = argparse.ArgumentParser(description='STM32 Encoder + Limit Switch Bridge (8 limits + gripper)')
    ap.add_argument('--port', default=DEFAULT_PORT)
    ap.add_argument('--baud', default=DEFAULT_BAUD, type=int)
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--monitor', action='store_true')
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--counts', action='store_true')
    ap.add_argument('--limits', action='store_true')
    ap.add_argument('--reset', action='store_true')
    args = ap.parse_args()

    try:
        bridge = STM32Bridge(port=args.port, baudrate=args.baud, verbose=not args.quiet)
    except RuntimeError as e:
        print(f'{C.RED}✗ {e}{C.RST}')
        sys.exit(1)

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

    # إذا لم يتم تحديد أي خيار، نفتح الـ CLI التفاعلي (مع استيراد run_cli من الكود الأصلي)
    # لكن لتجنب تكرار الكود، يمكنك نسخ run_cli من ملفك الأصلي.
    print("Use --help for options. Run with no arguments for interactive CLI (not implemented in this snippet).")
    bridge.close()

if __name__ == '__main__':
    main()