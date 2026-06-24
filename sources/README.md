# Benchmark source registry

Generate `benchmark_sources.csv` with `esai-validate prepare-source-registry`. Supplying the
systematic collection candidate catalog prefills exact normalized-title matches but leaves them
pending. For each benchmark, record the canonical paper or benchmark URL and the source abstract.
Set `source_status=verified` only after checking that the source describes the benchmark named by
the tracker row. Use
`rejected` for a proposed source that was checked and found not to match; leave unresolved rows as
`pending`.

Verified registries are version-controlled. Do not store credentials, private documents, or
copyrighted full text in this directory.
