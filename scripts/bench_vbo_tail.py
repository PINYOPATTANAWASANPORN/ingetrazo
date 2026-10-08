"""Compare old whole-buffer join with changed-tail VBO assembly.

Run ``python scripts/bench_vbo_tail.py`` from the repository root. This is an
isolated CPU comparison with a no-op VBO; it is not a viewport frame benchmark.
The default models a 64 MiB unchanged cached prefix and a 32-byte edit.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from views.viewport import Viewport


class _State:
    def __init__(self, parts):
        self._vbo_parts = {"sample": (list(parts), sum(map(len, parts)) + 4096)}


class _NoopVBO:
    def bind(self):
        pass

    def release(self):
        pass

    def allocate(self, _size):
        raise AssertionError("benchmark unexpectedly reallocated the VBO")

    def write(self, _offset, data, count):
        assert len(data) == count


def _previous_upload(state, vbo, slot, parts):
    """The pre-change `_upload_vbo` algorithm, only for this comparison."""
    raw = b"".join(parts)
    total = len(raw)
    prev = state._vbo_parts.get(slot)
    keep = 0
    cap = prev[1] if prev is not None else 0
    if prev is not None and total <= cap:
        for a, b in zip(parts, prev[0]):
            if a is b or a == b:
                keep += len(a)
            else:
                break
        keep = min(keep, total)
    vbo.bind()
    if total > cap:
        raise AssertionError("benchmark unexpectedly grew the VBO")
    if total > keep:
        vbo.write(keep, raw[keep:], total - keep)
    vbo.release()
    state._vbo_parts[slot] = (list(parts), cap)
    return total


def measure(repeats: int = 20, prefix_mib: int = 64) -> dict:
    if repeats < 1 or prefix_mib < 1:
        raise ValueError("repeats and prefix_mib must be positive")
    # Separate cached objects model stable group chunks. The changed tail is
    # much smaller than the prefix, as with a local edit in a large document.
    chunk_size = prefix_mib * 1024 * 1024 // 8
    parts = [b"x" * chunk_size for _ in range(8)] + [b"a" * 32]
    old_state, new_state = _State(parts), _State(parts)
    vbo = _NoopVBO()
    timings = {"whole_join_ms": [], "tail_join_ms": []}
    total = sum(map(len, parts))
    for i in range(repeats):
        changed = parts[:-1] + [bytes([65 + i % 26]) * 32]
        modes = (("whole_join_ms", _previous_upload, old_state),
                 ("tail_join_ms", Viewport._upload_vbo, new_state))
        if i % 2:
            modes = modes[::-1]
        for name, upload, state in modes:
            start = time.perf_counter()
            assert upload(state, vbo, "sample", changed) == total
            timings[name].append((time.perf_counter() - start) * 1000)
    return {
        "prefix_mib": prefix_mib,
        "changed_tail_bytes": 32,
        "repeats": repeats,
        "boundary": "CPU VBO assembly and no-op upload; excludes real GPU and paint",
        "median_ms": {name: round(statistics.median(values), 3)
                      for name, values in timings.items()},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--prefix-mib", type=int, default=64)
    args = parser.parse_args()
    try:
        print(json.dumps(measure(args.repeats, args.prefix_mib), indent=2))
    except ValueError as exc:
        parser.error(str(exc))
