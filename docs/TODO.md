# Orbit TODO Board

This log keeps key follow-up items that require deeper work beyond the current cleanup sprint.

## Memory compression gaps
- [ ] Preserve either the full raw content or a “decompression tail” when the summary is truncated, so follow-up queries can surface the missing reason (e.g., “Why do I want to reach 64 kg?”).
- [ ] Flag compressed memories that contain critical facts (weights, allergies, commitments) as non-truncatable or store provenance metadata that includes the trimmed suffix.
- [ ] Emit metrics/logs whenever a truncated memory is retrieved for a query that clearly asks for the missing section so we can measure regression impact.

## Ranking/feedback refinement
- [x] Ship diversity-aware reranking with assistant-length penalties (in progress/complete).
- [ ] Reconnect derived_from provenance to the reranker so that confirmed facts outrank verbose assistant clusters.
- [ ] Expand scorecard deltas for `top1_relevant_rate`, `precision@5`, and derived completeness.

## Documentation polish
- [x] Add multi-language README and docs entry points (English, 中文, Español, Deutsch, 日本語, Português-BR).
- [ ] Build AI-guided setup helper in the front-end (floating UI copy/paste flow).
- [ ] Document API key lifecycle, limits, and upgrade CTA in the dashboard docs.
