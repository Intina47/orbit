# Orbit Stress Audit Report

- Started: `2026-02-22T17:20:22.958421+00:00`
- Finished: `2026-02-22T17:21:54.124773+00:00`
- Duration: `91.166s`

## Scenario Results

### throughput_and_scaling
- Status: **PASS**
- Metrics:
  - `checkpoints`: `[{'memory_count': 1000, 'checkpoint_ingest_sec': 6.4481, 'checkpoint_ingest_eps': 107.79, 'retrieve_p50_ms': 55.255, 'retrieve_p95_ms': 68.178, 'retrieve_max_ms': 80.314}, {'memory_count': 5000, 'checkpoint_ingest_sec': 26.0199, 'checkpoint_ingest_eps': 131.37, 'retrieve_p50_ms': 52.503, 'retrieve_p95_ms': 70.568, 'retrieve_max_ms': 83.15}, {'memory_count': 10000, 'checkpoint_ingest_sec': 33.4156, 'checkpoint_ingest_eps': 134.76, 'retrieve_p50_ms': 52.677, 'retrieve_p95_ms': 66.037, 'retrieve_max_ms': 73.779}]`
  - `final_memory_count`: `10000`
  - `scenario_elapsed_sec`: `76.424`
- Findings:
  - Throughput and latency remained within benchmark targets in this run.

### storage_bloat_long_assistant_responses
- Status: **WARN**
- Metrics:
  - `memory_count`: `250`
  - `db_size_mb`: `5.883`
  - `avg_content_chars`: `6831.6`
  - `avg_summary_chars`: `219.9`
  - `bytes_per_memory`: `24674.3`
  - `p95_content_chars`: `6883.0`
  - `scenario_elapsed_sec`: `2.147`
- Findings:
  - Full assistant responses are persisted in `content`, causing storage growth.
  - Summaries are compact, but raw stored `content` remains large; no payload truncation.

### relevance_vs_noise_multibot
- Status: **WARN**
- Metrics:
  - `queries_tested`: `4`
  - `avg_precision_at_5`: `0.1`
  - `top1_relevant_rate`: `0.5`
  - `assistant_slots_in_top5_total`: `18`
  - `candidate_memory_count`: `276`
  - `scenario_elapsed_sec`: `1.927`
- Findings:
  - Average precision@5 was 0.10; noisy assistant memories still dilute top results.
  - Assistant-response memories still occupy many top-5 slots under heavy noise.

### entity_isolation_filtering
- Status: **PASS**
- Metrics:
  - `alice_result_count`: `20`
  - `bob_result_count`: `20`
  - `alice_leak_count`: `0`
  - `bob_leak_count`: `0`
  - `scenario_elapsed_sec`: `1.052`
- Findings:
  - Entity filtering stayed isolated for sampled retrievals.

### feedback_learning_adaptation
- Status: **PASS**
- Metrics:
  - `baseline_top_memory`: `068d71bd-4ef2-43af-8fd6-781d7bc79a96`
  - `final_top_memory`: `068d71bd-4ef2-43af-8fd6-781d7bc79a96`
  - `preferred_memory_id`: `068d71bd-4ef2-43af-8fd6-781d7bc79a96`
  - `scenario_elapsed_sec`: `0.862`
- Findings:
  - Feedback loop converged: preferred memory promoted to top.

### concurrent_ingest_pressure
- Status: **FAIL**
- Metrics:
  - `workers`: `12`
  - `events_per_worker`: `220`
  - `target_events`: `2640`
  - `stored_events`: `2085`
  - `elapsed_sec`: `7.497`
  - `events_per_sec`: `352.15`
  - `failed_events`: `258`
  - `scenario_elapsed_sec`: `7.512`
- Findings:
  - Concurrent ingest saw 258 failed writes out of 2640 attempts.
  - worker_failed_events=17
  - worker_failed_events=21
  - worker_failed_events=24
  - worker_failed_events=30
  - worker_failed_events=17
  - worker_failed_events=27
  - worker_failed_events=17
  - worker_failed_events=23
  - worker_failed_events=17
  - worker_failed_events=23

### compression_behavior
- Status: **PASS**
- Metrics:
  - `input_events`: `120`
  - `stored_events`: `24`
  - `compression_ratio`: `0.8`
  - `compressed_records`: `24`
  - `scenario_elapsed_sec`: `1.243`
- Findings:
  - Compression ratio reached 0.80 on repetitive traffic.
  - Largest compressed summary length: 469 chars.
