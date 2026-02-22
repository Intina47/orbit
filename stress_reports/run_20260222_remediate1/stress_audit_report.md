# Orbit Stress Audit Report

- Started: `2026-02-22T17:58:17.709098+00:00`
- Finished: `2026-02-22T17:58:37.107046+00:00`
- Duration: `19.398s`

## Scenario Results

### throughput_and_scaling
- Status: **PASS**
- Metrics:
  - `checkpoints`: `[{'memory_count': 1000, 'checkpoint_ingest_sec': 1.0087, 'checkpoint_ingest_eps': 654.66, 'retrieve_p50_ms': 9.956, 'retrieve_p95_ms': 11.626, 'retrieve_max_ms': 20.753}, {'memory_count': 5000, 'checkpoint_ingest_sec': 3.9898, 'checkpoint_ingest_eps': 805.75, 'retrieve_p50_ms': 13.689, 'retrieve_p95_ms': 17.529, 'retrieve_max_ms': 17.832}, {'memory_count': 10000, 'checkpoint_ingest_sec': 5.1325, 'checkpoint_ingest_eps': 835.36, 'retrieve_p50_ms': 11.855, 'retrieve_p95_ms': 15.267, 'retrieve_max_ms': 28.507}]`
  - `final_memory_count`: `10000`
  - `scenario_elapsed_sec`: `14.074`
- Findings:
  - Throughput and latency remained within benchmark targets in this run.

### storage_bloat_long_assistant_responses
- Status: **WARN**
- Metrics:
  - `memory_count`: `250`
  - `db_size_mb`: `1.312`
  - `avg_content_chars`: `1401.9`
  - `avg_summary_chars`: `219.9`
  - `bytes_per_memory`: `5505.0`
  - `p95_content_chars`: `1402.0`
  - `scenario_elapsed_sec`: `0.619`
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
  - `scenario_elapsed_sec`: `0.409`
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
  - `scenario_elapsed_sec`: `0.159`
- Findings:
  - Entity filtering stayed isolated for sampled retrievals.

### feedback_learning_adaptation
- Status: **PASS**
- Metrics:
  - `baseline_top_memory`: `2e543318-708d-42a8-8279-ba22b9c171c9`
  - `final_top_memory`: `2e543318-708d-42a8-8279-ba22b9c171c9`
  - `preferred_memory_id`: `2e543318-708d-42a8-8279-ba22b9c171c9`
  - `scenario_elapsed_sec`: `0.198`
- Findings:
  - Feedback loop converged: preferred memory promoted to top.

### concurrent_ingest_pressure
- Status: **PASS**
- Metrics:
  - `workers`: `12`
  - `events_per_worker`: `220`
  - `target_events`: `2640`
  - `stored_events`: `2640`
  - `elapsed_sec`: `3.648`
  - `events_per_sec`: `723.73`
  - `failed_events`: `0`
  - `scenario_elapsed_sec`: `3.675`
- Findings:
  - Concurrent ingest completed with no observed write failures.

### compression_behavior
- Status: **PASS**
- Metrics:
  - `input_events`: `120`
  - `stored_events`: `24`
  - `compression_ratio`: `0.8`
  - `compressed_records`: `24`
  - `scenario_elapsed_sec`: `0.263`
- Findings:
  - Compression ratio reached 0.80 on repetitive traffic.
  - Largest compressed summary length: 469 chars.
