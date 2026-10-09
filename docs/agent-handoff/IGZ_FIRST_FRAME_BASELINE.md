# Native IGZ first-frame baseline

Draft PR #93 on `perf/igz-first-frame-baseline` follows draft PR #92. The preceding
`load_scene` corpus measured decode/hydration only. This slice uses the same
three SHA-256-pinned example documents and exercises the real
`MainWindow.open_path` path in a visible native Qt window. Every sample gets a
fresh process and temporary application profile, then records the first
`QOpenGLWidget.frameSwapped` after `sceneVersionChanged` reports the opened
document. Source files are verified before and after sampling and never saved.

Run from a visible Windows desktop session:

```powershell
python scripts/bench_igz_first_frame.py --repeats 3 --output igz-first-frame-local.json
```

The timer starts immediately before `open_path`, after the application window
and initial blank OpenGL viewport exist. `open_to_ready` ends at the document's
scene-version signal. `paint_ms` times the matching model `paintGL`; `open_to_swap`
ends when Qt submits that frame. A 50 ms timer provides a coarse event-loop
stall proxy. The load gap ends at document-ready; the full gap ends at frame
submission. It is not a physical pointer, monitor scanout, or visible-pixel
measurement. OS cache was not flushed, and the model set is small with no
nested groups.

Windows 10 build 19045, Python 3.12.15, 8 logical CPUs, 3 fresh processes per
model. Medians are milliseconds; the raw samples are in
`benchmarks/results/igz-windows-first-frame-2026-10-09.json`.

| Model | Open to ready | Paint | Open to Qt frame | Max load event gap | Max open-to-frame event gap |
| --- | ---: | ---: | ---: | ---: | ---: |
| banca-pergola | 228.991 | 106.170 | 370.944 | 121.577 | 179.092 |
| pileta-fuente | 1,336.310 | 1,338.631 | 2,766.572 | 450.586 | 1,471.726 |
| arco | 709.973 | 737.753 | 1,521.936 | 189.259 | 858.562 |

On these models, first model paint is a large portion of time to Qt frame;
pileta spends roughly as long painting as opening the document. This points to
renderer rebuild/upload work as a more useful next profiling target than Qt
composition. The event-gap figures are a timer proxy and include any scheduling
delay; they are not direct input-latency figures.

Next: profile the first paint's face, edge, texture, chunk-cache and GPU-upload
phases on pileta and a genuinely large nested model. Implement one bounded
progressive-paint or render-chunk change, then compare the same corpus and
first-frame measurements on the same machine. The performance workstream stays
at 70% until a real large-project and correctness gate is met. The installed
application remains unchanged.

The follow-up opt-in phase profile is in `IGZ_FIRST_PAINT_PHASES.md`; it
identifies cold render-chunk preparation as the dominant measured paint cost
on pileta and arco. It does not establish a performance improvement yet.
