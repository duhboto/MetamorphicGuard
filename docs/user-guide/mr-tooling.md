# Metamorphic Relation Tooling

## Built-in MR Library
- Inspect with `metamorphic-guard mr library`
- Provides stability/robustness relations such as `permute_input`, `add_noise_below_min`, `scale_scores`, `drop_low_confidence`, and `duplicate_top_k`
- Metadata now includes risk level and estimated implementation effort so you can triage quickly.

## Discovery Helper
- Suggest relations from existing property descriptions
- Usage: `metamorphic-guard mr discover ranking_guard`

## Validation
- Lints relation definitions for missing metadata and incorrect signatures
- Usage: `metamorphic-guard mr validate fairness_guard`

## Coverage & Prioritization
- Run `metamorphic-guard mr prioritize fairness_guard --format table` to view category coverage (robustness, stability, monotonicity, fairness, etc.) plus prioritized suggestions.
- Use `--format json` for automation pipelines; the report includes density, missing categories, and scored library recommendations.

## Composition
- Use `metamorphic_guard.specs.chain_relations()` to combine multiple relations into a single composite check.

