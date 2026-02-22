# Orbit Stress Audit Report

- Started: `2026-02-22T18:49:43.041175+00:00`
- Finished: `2026-02-22T18:50:05.951782+00:00`
- Duration: `22.911s`

## Scenario Results

### throughput_and_scaling
- Status: **PASS**
- Metrics:
  - `checkpoints`: `[{'memory_count': 1000, 'checkpoint_ingest_sec': 1.2893, 'checkpoint_ingest_eps': 523.1, 'retrieve_p50_ms': 12.108, 'retrieve_p95_ms': 14.29, 'retrieve_max_ms': 19.084}, {'memory_count': 5000, 'checkpoint_ingest_sec': 4.7225, 'checkpoint_ingest_eps': 686.11, 'retrieve_p50_ms': 12.477, 'retrieve_p95_ms': 14.867, 'retrieve_max_ms': 30.683}, {'memory_count': 10000, 'checkpoint_ingest_sec': 6.0148, 'checkpoint_ingest_eps': 714.03, 'retrieve_p50_ms': 13.539, 'retrieve_p95_ms': 15.412, 'retrieve_max_ms': 43.057}]`
  - `final_memory_count`: `10000`
  - `scenario_elapsed_sec`: `16.531`
- Findings:
  - Throughput and latency remained within benchmark targets in this run.

### storage_bloat_long_assistant_responses
- Status: **PASS**
- Metrics:
  - `memory_count`: `250`
  - `db_size_mb`: `0.984`
  - `avg_content_chars`: `901.9`
  - `avg_summary_chars`: `219.9`
  - `bytes_per_memory`: `4128.8`
  - `p95_content_chars`: `902.0`
  - `scenario_elapsed_sec`: `0.616`
- Findings:
  - Assistant payload truncation and compact vector encoding kept storage footprint controlled.

### relevance_vs_noise_multibot
- Status: **PASS**
- Metrics:
  - `queries_tested`: `4`
  - `avg_precision_at_5`: `0.85`
  - `top1_relevant_rate`: `1.0`
  - `assistant_slots_in_top5_total`: `3`
  - `candidate_memory_count`: `276`
  - `scenario_elapsed_sec`: `0.509`
- Findings:
  - Personalization memory stayed dominant under mixed chatbot noise load.

### entity_isolation_filtering
- Status: **PASS**
- Metrics:
  - `alice_result_count`: `20`
  - `bob_result_count`: `20`
  - `alice_leak_count`: `0`
  - `bob_leak_count`: `0`
  - `scenario_elapsed_sec`: `0.552`
- Findings:
  - Entity filtering stayed isolated for sampled retrievals.

### feedback_learning_adaptation
- Status: **WARN**
- Metrics:
  - `baseline_top_memory`: `b5beeaa4-6e4d-4e98-b454-72a858694435`
  - `final_top_memory`: `49d9e45d-5264-4d02-83a7-7014c4da0d87`
  - `preferred_memory_id`: `b5beeaa4-6e4d-4e98-b454-72a858694435`
  - `scenario_elapsed_sec`: `0.238`
- Findings:
  - Feedback loop did not converge to preferred memory as top result.

### concurrent_ingest_pressure
- Status: **PASS**
- Metrics:
  - `workers`: `12`
  - `events_per_worker`: `220`
  - `target_events`: `2640`
  - `stored_events`: `2640`
  - `elapsed_sec`: `4.08`
  - `events_per_sec`: `647.12`
  - `failed_events`: `0`
  - `scenario_elapsed_sec`: `4.109`
- Findings:
  - Concurrent ingest completed with no observed write failures.

### compression_behavior
- Status: **PASS**
- Metrics:
  - `input_events`: `120`
  - `stored_events`: `24`
  - `compression_ratio`: `0.8`
  - `compressed_records`: `24`
  - `scenario_elapsed_sec`: `0.356`
- Findings:
  - Compression ratio reached 0.80 on repetitive traffic.
  - Largest compressed summary length: 469 chars.
