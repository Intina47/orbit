# Orbit Stress Audit Report

- Started: `2026-02-22T18:51:23.938178+00:00`
- Finished: `2026-02-22T18:51:48.332686+00:00`
- Duration: `24.395s`

## Scenario Results

### throughput_and_scaling
- Status: **PASS**
- Metrics:
  - `checkpoints`: `[{'memory_count': 1000, 'checkpoint_ingest_sec': 1.3918, 'checkpoint_ingest_eps': 456.57, 'retrieve_p50_ms': 13.176, 'retrieve_p95_ms': 18.7, 'retrieve_max_ms': 112.548}, {'memory_count': 5000, 'checkpoint_ingest_sec': 5.0908, 'checkpoint_ingest_eps': 629.65, 'retrieve_p50_ms': 12.119, 'retrieve_p95_ms': 14.783, 'retrieve_max_ms': 60.47}, {'memory_count': 10000, 'checkpoint_ingest_sec': 6.3218, 'checkpoint_ingest_eps': 667.81, 'retrieve_p50_ms': 12.455, 'retrieve_p95_ms': 16.26, 'retrieve_max_ms': 86.975}]`
  - `final_memory_count`: `10000`
  - `scenario_elapsed_sec`: `17.729`
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
  - `scenario_elapsed_sec`: `0.838`
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
  - `scenario_elapsed_sec`: `0.534`
- Findings:
  - Personalization memory stayed dominant under mixed chatbot noise load.

### entity_isolation_filtering
- Status: **PASS**
- Metrics:
  - `alice_result_count`: `20`
  - `bob_result_count`: `20`
  - `alice_leak_count`: `0`
  - `bob_leak_count`: `0`
  - `scenario_elapsed_sec`: `0.555`
- Findings:
  - Entity filtering stayed isolated for sampled retrievals.

### feedback_learning_adaptation
- Status: **PASS**
- Metrics:
  - `baseline_top_memory`: `a7dc6053-5ca1-4d81-88ec-a70c80b687e4`
  - `final_top_memory`: `a7dc6053-5ca1-4d81-88ec-a70c80b687e4`
  - `preferred_memory_id`: `a7dc6053-5ca1-4d81-88ec-a70c80b687e4`
  - `scenario_elapsed_sec`: `0.32`
- Findings:
  - Feedback loop converged: preferred memory promoted to top.

### concurrent_ingest_pressure
- Status: **PASS**
- Metrics:
  - `workers`: `12`
  - `events_per_worker`: `220`
  - `target_events`: `2640`
  - `stored_events`: `2640`
  - `elapsed_sec`: `3.948`
  - `events_per_sec`: `668.73`
  - `failed_events`: `0`
  - `scenario_elapsed_sec`: `4.094`
- Findings:
  - Concurrent ingest completed with no observed write failures.

### compression_behavior
- Status: **PASS**
- Metrics:
  - `input_events`: `120`
  - `stored_events`: `24`
  - `compression_ratio`: `0.8`
  - `compressed_records`: `24`
  - `scenario_elapsed_sec`: `0.324`
- Findings:
  - Compression ratio reached 0.80 on repetitive traffic.
  - Largest compressed summary length: 469 chars.
