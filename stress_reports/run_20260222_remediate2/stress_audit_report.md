# Orbit Stress Audit Report

- Started: `2026-02-22T18:05:42.334994+00:00`
- Finished: `2026-02-22T18:06:00.232559+00:00`
- Duration: `17.898s`

## Scenario Results

### throughput_and_scaling
- Status: **PASS**
- Metrics:
  - `checkpoints`: `[{'memory_count': 1000, 'checkpoint_ingest_sec': 0.8903, 'checkpoint_ingest_eps': 709.89, 'retrieve_p50_ms': 9.837, 'retrieve_p95_ms': 12.385, 'retrieve_max_ms': 22.175}, {'memory_count': 5000, 'checkpoint_ingest_sec': 3.7241, 'checkpoint_ingest_eps': 880.84, 'retrieve_p50_ms': 10.64, 'retrieve_p95_ms': 13.185, 'retrieve_max_ms': 13.538}, {'memory_count': 10000, 'checkpoint_ingest_sec': 4.6674, 'checkpoint_ingest_eps': 915.82, 'retrieve_p50_ms': 11.264, 'retrieve_p95_ms': 13.79, 'retrieve_max_ms': 15.239}]`
  - `final_memory_count`: `10000`
  - `scenario_elapsed_sec`: `12.926`
- Findings:
  - Throughput and latency remained within benchmark targets in this run.

### storage_bloat_long_assistant_responses
- Status: **WARN**
- Metrics:
  - `memory_count`: `250`
  - `db_size_mb`: `1.164`
  - `avg_content_chars`: `901.9`
  - `avg_summary_chars`: `219.9`
  - `bytes_per_memory`: `4882.4`
  - `p95_content_chars`: `902.0`
  - `scenario_elapsed_sec`: `0.597`
- Findings:
  - Summaries are compact, but raw stored `content` remains large; no payload truncation.

### relevance_vs_noise_multibot
- Status: **WARN**
- Metrics:
  - `queries_tested`: `4`
  - `avg_precision_at_5`: `0.5`
  - `top1_relevant_rate`: `1.0`
  - `assistant_slots_in_top5_total`: `10`
  - `candidate_memory_count`: `276`
  - `scenario_elapsed_sec`: `0.381`
- Findings:
  - Average precision@5 was 0.50; noisy assistant memories still dilute top results.
  - Assistant-response memories still occupy many top-5 slots under heavy noise.

### entity_isolation_filtering
- Status: **PASS**
- Metrics:
  - `alice_result_count`: `20`
  - `bob_result_count`: `20`
  - `alice_leak_count`: `0`
  - `bob_leak_count`: `0`
  - `scenario_elapsed_sec`: `0.202`
- Findings:
  - Entity filtering stayed isolated for sampled retrievals.

### feedback_learning_adaptation
- Status: **PASS**
- Metrics:
  - `baseline_top_memory`: `a501cf17-c67e-4214-8fa5-0b9f58f9ee7c`
  - `final_top_memory`: `a501cf17-c67e-4214-8fa5-0b9f58f9ee7c`
  - `preferred_memory_id`: `a501cf17-c67e-4214-8fa5-0b9f58f9ee7c`
  - `scenario_elapsed_sec`: `0.199`
- Findings:
  - Feedback loop converged: preferred memory promoted to top.

### concurrent_ingest_pressure
- Status: **PASS**
- Metrics:
  - `workers`: `12`
  - `events_per_worker`: `220`
  - `target_events`: `2640`
  - `stored_events`: `2640`
  - `elapsed_sec`: `3.337`
  - `events_per_sec`: `791.19`
  - `failed_events`: `0`
  - `scenario_elapsed_sec`: `3.361`
- Findings:
  - Concurrent ingest completed with no observed write failures.

### compression_behavior
- Status: **PASS**
- Metrics:
  - `input_events`: `120`
  - `stored_events`: `24`
  - `compression_ratio`: `0.8`
  - `compressed_records`: `24`
  - `scenario_elapsed_sec`: `0.23`
- Findings:
  - Compression ratio reached 0.80 on repetitive traffic.
  - Largest compressed summary length: 469 chars.
