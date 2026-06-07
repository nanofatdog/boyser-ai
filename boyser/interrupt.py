"""ดักปุ่ม ESC ระหว่างโมเดลกำลังตอบ — Interrupt class และฟังก์ชันช่วย"""

import os
import sys
import threading
import time

__all__ = [
    "Interrupt",
    "hard_close",
    "esc_watch",
    "_active_interrupt",
]

IS_WIN = os.name == "nt"

_active_interrupt = None  # Interrupt ที่ทำงานอยู่ (ให้ confirm() หยุดมันชั่วคราวได้)


class Interrupt:
    """ดักปุ่ม ESC ระหว่างโมเดลกำลังตอบ (อ่าน stdin ใน thread แยก) — กด ESC = หยุด turn นี้
    หยุดอ่านชั่วคราวได้ด้วย pause()/resume() เพื่อไม่แย่งปุ่มตอน input() ถาม y/n"""

    def __init__(self):
        self.event = threading.Event()
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._thread = None
        self._fd = None
        self._old = None

    def __enter__(self):
        global _active_interrupt
        if sys.stdin.isatty():
            if IS_WIN:  # Windows: msvcrt อ่านปุ่มจาก console ได้เลย ไม่ต้องสลับโหมด terminal
                self._thread = threading.Thread(target=self._run_win, daemon=True)
                self._thread.start()
            else:
                import termios
                import tty

                try:
                    self._fd = sys.stdin.fileno()
                    self._old = termios.tcgetattr(self._fd)
                    tty.setcbreak(self._fd)  # อ่านทีละปุ่มโดยไม่ต้องกด Enter
                    self._thread = threading.Thread(target=self._run, daemon=True)
                    self._thread.start()
                except Exception:
                    self._old = None
        _active_interrupt = self
        return self

    def _run(self):
        import select

        while not self._stop.is_set():
            if self._paused.is_set():
                time.sleep(0.05)
                continue
            r, _, _ = select.select([sys.stdin], [], [], 0.1)
            if r and not self._paused.is_set():
                ch = os.read(self._fd, 1)
                if ch == b"\x1b":  # ESC
                    self.event.set()
                    return

    def _run_win(self):
        import msvcrt

        while not self._stop.is_set():
            if self._paused.is_set() or not msvcrt.kbhit():
                time.sleep(0.05)
                continue
            if msvcrt.getwch() == "\x1b":  # ESC
                self.event.set()
                return

    def stopped(self) -> bool:
        return self.event.is_set()

    def pause(self):
        """หยุดอ่านปุ่ม + คืนโหมด terminal ปกติ เพื่อให้ input() (ถาม y/n) ใช้ได้"""
        if not self._thread:
            return
        self._paused.set()
        if self._old is not None:  # POSIX เท่านั้นที่ต้องคืนโหมด terminal
            import termios

            try:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)
            except Exception:
                pass
        time.sleep(0.06)  # ให้ reader หลุดจาก select/kbhit รอบปัจจุบันก่อน input()

    def resume(self):
        if not self._thread:
            return
        if self._old is not None:
            import tty

            try:
                tty.setcbreak(self._fd)
            except Exception:
                pass
        self._paused.clear()

    def __exit__(self, *a):
        global _active_interrupt
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.3)
        if self._old is not None:
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)
        _active_interrupt = None


def hard_close(resp) -> None:
    """ปิด httpx response แบบ shutdown socket — ปลุก recv ที่ block อยู่ได้จริง
    (resp.close() เฉยๆ ไม่ปลุก recv ที่ค้าง: ทดสอบแล้ว block ต่อจน server ส่งข้อมูล)"""
    import socket as _socket

    try:
        ns = resp.extensions.get("network_stream")
        s = ns.get_extra_info("socket") if ns else None
        if s:
            s.shutdown(_socket.SHUT_RDWR)
    except Exception:
        pass
    try:
        resp.close()
    except Exception:
        pass


def esc_watch(intr, close_fn) -> threading.Event:
    """เฝ้า ESC ระหว่าง stream block รอ token แรก (โหลดโมเดล/prompt eval) — กดแล้วปิด stream
    ให้ iter หลุดจากการ block ทันที; คืน Event ให้ caller .set() ตอนจบ stream เพื่อเลิกเฝ้า"""
    done = threading.Event()
    if intr:
        def run():
            while not done.wait(0.1):
                if intr.stopped():
                    try:
                        close_fn()
                    except Exception:
                        pass
                    return

        threading.Thread(target=run, daemon=True).start()
    return done
