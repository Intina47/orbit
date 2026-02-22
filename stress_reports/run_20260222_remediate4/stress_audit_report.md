# Orbit Stress Audit Report

- Started: `2026-02-22T18:12:16.340117+00:00`
- Finished: `2026-02-22T18:12:35.512347+00:00`
- Duration: `19.172s`

## Scenario Results

### throughput_and_scaling
- Status: **PASS**
- Metrics:
  - `checkpoints`: `[{'memory_count': 1000, 'checkpoint_ingest_sec': 0.949, 'checkpoint_ingest_eps': 683.49, 'retrieve_p50_ms': 9.804, 'retrieve_p95_ms': 12.473, 'retrieve_max_ms': 20.482}, {'memory_count': 5000, 'checkpoint_ingest_sec': 3.9979, 'checkpoint_ingest_eps': 832.67, 'retrieve_p50_ms': 10.149, 'retrieve_p95_ms': 14.048, 'retrieve_max_ms': 25.697}, {'memory_count': 10000, 'checkpoint_ingest_sec': 5.2516, 'checkpoint_ingest_eps': 840.93, 'retrieve_p50_ms': 12.084, 'retrieve_p95_ms': 13.957, 'retrieve_max_ms': 38.56}]`
  - `final_memory_count`: `10000`
  - `scenario_elapsed_sec`: `13.998`
- Findings:
  - Throughput and latency remained within benchmark targets in this run.

### storage_bloat_long_assistant_responses
- Status: **PASS**
- Metrics:
  - `memory_count`: `250`
  - `db_size_mb`: `0.988`
  - `avg_content_chars`: `901.9`
  - `avg_summary_chars`: `219.9`
  - `bytes_per_memory`: `4145.2`
  - `p95_content_chars`: `902.0`
  - `scenario_elapsed_sec`: `0.558`
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
  - `scenario_elapsed_sec`: `0.415`
- Findings:
  - Personalization memory stayed dominant under mixed chatbot noise load.

### entity_isolation_filtering
- Status: **PASS**
- Metrics:
  - `alice_result_count`: `20`
  - `bob_result_count`: `20`
  - `alice_leak_count`: `0`
  - `bob_leak_count`: `0`
  - `scenario_elapsed_sec`: `0.158`
- Findings:
  - Entity filtering stayed isolated for sampled retrievals.

### feedback_learning_adaptation
- Status: **PASS**
- Metrics:
  - `baseline_top_memory`: `e08c049f-be86-4cf2-8504-b1e286fd4217`
  - `final_top_memory`: `e08c049f-be86-4cf2-8504-b1e286fd4217`
  - `preferred_memory_id`: `e08c049f-be86-4cf2-8504-b1e286fd4217`
  - `scenario_elapsed_sec`: `0.212`
- Findings:
  - Feedback loop converged: preferred memory promoted to top.

### concurrent_ingest_pressure
- Status: **PASS**
- Metrics:
  - `workers`: `12`
  - `events_per_worker`: `220`
  - `target_events`: `2640`
  - `stored_events`: `2640`
  - `elapsed_sec`: `3.559`
  - `events_per_sec`: `741.79`
  - `failed_events`: `0`
  - `scenario_elapsed_sec`: `3.586`
- Findings:
  - Concurrent ingest completed with no observed write failures.

### compression_behavior
- Status: **PASS**
- Metrics:
  - `input_events`: `120`
  - `stored_events`: `24`
  - `compression_ratio`: `0.8`
  - `compressed_records`: `24`
  - `scenario_elapsed_sec`: `0.244`
- Findings:
  - Compression ratio reached 0.80 on repetitive traffic.
  - Largest compressed summary length: 469 chars.
