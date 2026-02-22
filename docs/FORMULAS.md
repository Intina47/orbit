# Formulas

## Bootstrap Relevance Prior

Used only as a bounded cold-start prior blended with learned importance output.

```
relevance_prior = 0.4 * recency + 0.3 * frequency + 0.3 * entity_importance
```

Where:

```
recency = exp(-0.1 * days_since_event)
frequency = 1 - exp(-0.3 * similar_recent_count)
entity_importance = min(1.0, entity_reference_count / 10)
```

## Final Confidence

```
confidence = 0.85 * learned_importance + 0.15 * relevance_prior
```

## Decay

```
relevance(t) = initial_importance * exp(-decay_rate * age_days)
half_life_days = ln(2) / decay_rate
```

`decay_rate` is learned per semantic key via outcome feedback.
