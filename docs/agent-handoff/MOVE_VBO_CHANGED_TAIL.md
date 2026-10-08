# Assemble only the changed VBO tail

Base: draft PR #74 (`perf/move-qt-frame-benchmark`). Branch:
`perf/vbo-changed-tail` ([draft PR #75](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/75)).

`Viewport._upload_vbo` already kept an unchanged prefix in the GPU buffer,
but it joined **all** CPU byte parts before comparing the prefix and sending
only the changed tail. That whole-model copy scales with the complete buffer
even when a local edit changes a few bytes. The upload now totals the part
lengths, finds the equal prefix, and joins only the remaining parts. If the
buffer outgrows its capacity, it still reallocates and sends every part.
The returned byte count and GPU content are unchanged; one-pass iterables are
materialized once before either scan.

Reproduce the isolated comparison from the repository root:

```powershell
python scripts/bench_vbo_tail.py
```

On native Windows, 20 alternating trials with eight cached chunks totaling
64 MiB and a changed 32-byte tail took 21.368 ms median with the former
whole-buffer join and 0.009 ms with the changed-tail join. The benchmark has a
no-op VBO and excludes GPU transfer, paint and Qt composition. The bundled
group-rich Yanque example's largest real buffer was about 1.2 MB; measured
`_upload_vbo` work there was under 1 ms per Move paint, so this change does
**not** establish a whole-frame improvement on that example. A three-trial
visible Qt Move run remained roughly in the prior frame-time range. This
slice matters when much larger unchanged group buffers precede a small edit.

Focused native Windows group-edit and Move validation passed 74 tests. The
new cases verify a changed middle part followed by an unchanged part and a
one-pass iterator, while existing cases cover first upload, value-equal
prefixes, growth, shrink and correct written bytes. `compileall` and
`git diff --check` passed. The PR #75 Windows Qt smoke job passed. At this
handoff snapshot, the Ubuntu `pytest (not slow)` job is still running; PR
#74's later documentation-only CI run also stalled at 26% after its earlier
code run passed. Do not call #75 fully green until the Ubuntu job completes.
The installed `C:\Program Files\IngeTrazo` build remains at `3815ef8`.

Next: profile `_sync_edges` face bucketing and loose silhouettes in a
representative large loose mesh; the 7,633-face queued-Move measurement in
PR #74 spent 135.4 ms median in paint and only 3.9 ms after paint before
`frameSwapped`. Do not infer monitor scanout from that signal.
