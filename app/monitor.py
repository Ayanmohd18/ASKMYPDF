import psutil
import time
from dataclasses import dataclass

@dataclass
class SystemStats:
    cpu_percent: float
    ram_used_mb: float
    ram_total_mb: float
    ram_percent: float
    last_query_latency_s: float

class LatencyTracker:
    def __init__(self):
        self._start: float = 0.0
        self._last_latency: float = 0.0

    def start(self):
        self._start = time.perf_counter()

    def stop(self) -> float:
        self._last_latency = time.perf_counter() - self._start
        return self._last_latency

    def last(self) -> float:
        return self._last_latency

_tracker = LatencyTracker()

def get_tracker() -> LatencyTracker:
    return _tracker

def get_stats() -> SystemStats:
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    
    return SystemStats(
        cpu_percent=cpu,
        ram_used_mb=mem.used / (1024 ** 2),
        ram_total_mb=mem.total / (1024 ** 2),
        ram_percent=mem.percent,
        last_query_latency_s=_tracker.last()
    )
