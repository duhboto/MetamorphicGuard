# Metamorphic Relation Tooling

## Built-in MR Library
- Inspect with `metamorphic-guard mr library`
- Provides stability/robustness relations such as `permute_input` and `add_noise_below_min`

## Discovery Helper
- Suggest relations from existing property descriptions
- Usage: `metamorphic-guard mr discover ranking_guard`

## Validation
- Lints relation definitions for missing metadata and incorrect signatures
- Usage: `metamorphic-guard mr validate fairness_guard`

## Composition
- Use `metamorphic_guard.specs.chain_relations()` to combine multiple relations into a single composite check.

