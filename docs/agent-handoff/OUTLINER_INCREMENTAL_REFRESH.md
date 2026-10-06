# Incremental Outliner refresh

Base: draft PR #57 (`perf/outliner-selection-sync`).
Branch: `perf/outliner-incremental-refresh`.

The Outliner checks group identity and sibling order against the existing
rows. When structure is unchanged, it updates changed name, visibility,
lock and kind properties in place, retaining Qt row objects and expansion.
When groups are added, removed or reordered, it rebuilds the tree and its
object index. Search and viewport selection are refreshed in either path.

On a synthetic offscreen Windows scene of 2,000 top-level groups, five
refreshes took 0.7808 s on the parent branch and 0.3090 s with this
change. Filter traversal of 20 calls took 0.0827 s on the parent branch;
this change does not target filtering. This measures these isolated methods,
not full GUI frame time. Benchmark script:
`C:\Users\Lenovo\Desktop\IngeTrazoTest\bench-outliner-refresh.py`.

Eleven Outliner tests passed with native Windows Qt and eleven offscreen.
The new test verifies row reuse, property updates, selection, expansion,
filtering and rebuild after a structural change. Representative real-model
benchmarks and deeper nested-tree stress cases remain open.
