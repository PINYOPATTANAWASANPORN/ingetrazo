# IGZ real-model load corpus (candidate)

Draft PR #92 on `perf/igz-real-model-corpus` follows draft PR #91. This slice adds a
hash-pinned, reproducible baseline for `formats.igz.load_scene` before changing
the renderer. It does **not** demonstrate progressive paint or large-project
performance.

Run from the repository root with the project Python environment:

```powershell
python scripts/bench_igz_corpus.py --repeats 5 --output igz-corpus-local.json
python -m pytest -q tests/test_igz_corpus_benchmark.py
```

`benchmarks/models/corpus-v1.json` pins three existing example documents by
SHA-256. The runner verifies their hashes before and after measurement, starts
a new Python process for each sample, and records scene structure. The reported
`load_ms` measures only the call to `load_scene`; `process_wall_ms` separately
includes interpreter and import startup, statistics, and process teardown.
Neither metric measures GUI creation, viewport first paint, picking, or user
interaction. The OS file cache is not flushed, so these are fresh-process
samples, not guaranteed cold-disk reads.

Local baseline on 2026-10-09: Windows 10 build 19045, Python 3.12.15,
8 logical CPUs, 5 fresh processes per model. Medians are in milliseconds.

| Model | File MiB | Top groups | Instances | Unique faces | Soft edges | `load_scene` median | Process wall median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| banca-pergola | 0.45 | 9 | 3 | 227 | 0 | 261.219 | 769.393 |
| pileta-fuente | 1.68 | 39 | 22 | 27,025 | 50,024 | 1,339.921 | 1,875.826 |
| arco | 3.44 | 30 | 28 | 10,370 | 203 | 691.402 | 1,023.988 |

The compressed file size does not predict load time here: the smaller pileta
file has substantially more faces and soft edges than arco. All three files
have zero nested groups, so the corpus does not exercise nested hierarchy
scale. The examples are only a small bundled sample, not representative of a
large professional project. Raw samples and environment metadata are in
`benchmarks/results/igz-windows-baseline-2026-10-09.json`.

Next: add a licensed or generated large nested/instanced model with pinned
structure and no sensitive project data. Instrument time to first useful
viewport paint in a frozen or native GUI, plus UI responsiveness during load.
Use those results to choose one renderer or progressive-paint change, then
re-run this corpus and the GUI measurements on the same machine and commit.
