# Concepts Overview

Metamorphic Guard is built on several key concepts:

## Task Specifications

A **task specification** defines:
- How to generate test inputs
- What properties outputs must satisfy
- What metamorphic relations should hold

See [Task Specifications](task-specifications.md) for details.

## Properties

**Properties** are assertions that outputs must satisfy. For example:
- "Output must be sorted"
- "Output length must be <= k"
- "Output must contain no PII"

## Metamorphic Relations

**Metamorphic relations** (MRs) are invariants that should hold across input transformations:
- If input is sorted, output should be sorted
- If input is negated, output should be negated
- If input is paraphrased, output should be semantically equivalent

## Statistical Analysis

Metamorphic Guard uses:
- **Bootstrap confidence intervals** for pass-rate differences
- **Power analysis** to determine sample sizes
- **Sequential testing** for iterative workflows

See [Statistical Analysis](statistical-analysis.md) for details.

## Adoption Gating

The **adoption gate** decides whether to adopt a candidate based on:
- Minimum improvement threshold (min_delta)
- Minimum pass rate
- Statistical significance (alpha)
- Power requirements

