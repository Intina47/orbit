# Orbit Stress Audit Report

- Started: `2026-02-22T18:10:27.252930+00:00`
- Finished: `2026-02-22T18:10:44.593170+00:00`
- Duration: `17.34s`

## Scenario Results

### throughput_and_scaling
- Status: **PASS**
- Metrics:
  - `checkpoints`: `[{'memory_count': 1000, 'checkpoint_ingest_sec': 0.8585, 'checkpoint_ingest_eps': 752.96, 'retrieve_p50_ms': 9.139, 'retrieve_p95_ms': 11.085, 'retrieve_max_ms': 16.851}, {'memory_count': 5000, 'checkpoint_ingest_sec': 3.4098, 'checkpoint_ingest_eps': 954.04, 'retrieve_p50_ms': 9.618, 'retrieve_p95_ms': 11.482, 'retrieve_max_ms': 25.183}, {'memory_count': 10000, 'checkpoint_ingest_sec': 4.396, 'checkpoint_ingest_eps': 980.22, 'retrieve_p50_ms': 10.732, 'retrieve_p95_ms': 13.167, 'retrieve_max_ms': 31.304}]`
  - `final_memory_count`: `10000`
  - `scenario_elapsed_sec`: `12.296`
- Findings:
  - Throughput and latency remained within benchmark targets in this run.

### storage_bloat_long_assistant_responses
- Status: **PASS**
- Metrics:
  - `memory_count`: `250`
  - `db_size_mb`: `0.992`
  - `avg_content_chars`: `901.9`
  - `avg_summary_chars`: `219.9`
  - `bytes_per_memory`: `4161.5`
  - `p95_content_chars`: `902.0`
  - `scenario_elapsed_sec`: `0.516`
- Findings:
  - Assistant payload truncation and compact vector encoding kept storage footprint controlled.

### relevance_vs_noise_multibot
- Status: **WARN**
- Metrics:
  - `queries_tested`: `4`
  - `avg_precision_at_5`: `0.5`
  - `top1_relevant_rate`: `1.0`
  - `assistant_slots_in_top5_total`: `10`
  - `candidate_memory_count`: `276`
  - `scenario_elapsed_sec`: `0.379`
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
  - `scenario_elapsed_sec`: `0.129`
- Findings:
  - Entity filtering stayed isolated for sampled retrievals.

### feedback_learning_adaptation
- Status: **PASS**
- Metrics:
  - `baseline_top_memory`: `44d5a577-e491-40ea-95a3-1cdf05c81571`
  - `final_top_memory`: `44d5a577-e491-40ea-95a3-1cdf05c81571`
  - `preferred_memory_id`: `44d5a577-e491-40ea-95a3-1cdf05c81571`
  - `scenario_elapsed_sec`: `0.194`
- Findings:
  - Feedback loop converged: preferred memory promoted to top.

### concurrent_ingest_pressure
- Status: **PASS**
- Metrics:
  - `workers`: `12`
  - `events_per_worker`: `220`
  - `target_events`: `2640`
  - `stored_events`: `2640`
  - `elapsed_sec`: `3.185`
  - `events_per_sec`: `828.94`
  - `failed_events`: `0`
  - `scenario_elapsed_sec`: `3.345`
- Findings:
  - Concurrent ingest completed with no observed write failures.

### compression_behavior
- Status: **PASS**
- Metrics:
  - `input_events`: `120`
  - `stored_events`: `24`
  - `compression_ratio`: `0.8`
  - `compressed_records`: `24`
  - `scenario_elapsed_sec`: `0.48`
- Findings:
  - Compression ratio reached 0.80 on repetitive traffic.
  - Largest compressed summary length: 469 chars.
