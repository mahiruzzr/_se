"""Progress meter rendering, similar to curl's default progress bar."""

from __future__ import annotations

import sys
import time

SPINNER = "|/-\\"


class ProgressMeter:
    def __init__(
        self,
        enabled: bool,
        total: int | None = None,
        stream=None,
        bar: bool = False,
    ):
        self.enabled = enabled
        self.total = total
        self.stream = stream if stream is not None else sys.stderr
        self.bar = bar
        self.done = 0
        self.start = time.perf_counter()
        self._last_render = 0.0
        self._ticks = 0
        self._cleared = False

    def update(self, chunk: int) -> None:
        self.done += chunk
        if not self.enabled:
            return
        now = time.perf_counter()
        if now - self._last_render < 0.1:
            return
        self._last_render = now
        self._render()

    def _render(self) -> None:
        elapsed = max(time.perf_counter() - self.start, 1e-6)
        speed = self.done / elapsed
        self._ticks += 1

        if self.bar:
            width = 30
            if self.total:
                frac = min(self.done / self.total, 1.0)
            else:
                frac = 0.0
            filled = int(width * frac)
            bar = "#" * filled + "-" * (width - filled)
            pct = f"{frac * 100:5.1f}%" if self.total else "  ?  "
            line = f"\r {bar} {pct}  {_hsize(self.done)}"
            if self.total:
                line += f"  {_hsize(int(speed))}/s  ETA {_eta(self.total, self.done, elapsed)}"
        else:
            pct = f"{self.done * 100 / self.total:6.1f}%" if self.total else "100.0%"
            if self.total:
                average = self.done / elapsed
                remaining = (self.total - self.done) / average if average else 0
                line = (
                    f"\r {self._spin()} {pct}  {_hsize(self.done)}/{_hsize(self.total)} "
                    f"({elapsed:0.3f}s) ({average:0.1f} kB/s, {remaining:0.1f}s ETA)"
                )
            else:
                line = (
                    f"\r {self._spin()} {_hsize(self.done)} ({elapsed:0.3}s) "
                    f"({speed / 1024:0.1f} kB/s)"
                )

        print(line, end="", file=self.stream, flush=True)
        self._cleared = True

    def _spin(self) -> str:
        return SPINNER[self._ticks % len(SPINNER)]

    def finish(self) -> None:
        if not self.enabled or not self._cleared:
            return
        print("\r" + " " * 79 + "\r", end="", file=self.stream, flush=True)
        self._cleared = False


def _hsize(size: float) -> str:
    units = ["B", "K", "M", "G", "T"]
    index = 0
    value = float(size)
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    if index == 0:
        return f"{int(value)}{units[index]}"
    return f"{value:.1f}{units[index]}"


def _eta(total: int, done: int, elapsed: float) -> str:
    if done <= 0:
        return "--:--"
    rate = done / elapsed
    if rate <= 0:
        return "--:--"
    seconds = max((total - done) / rate, 0)
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
