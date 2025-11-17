# Text Normalizer Guard

A real-world consumer project that uses [Metamorphic Guard](https://github.com/metamorphic-guard/metamorphic-guard) to evaluate and compare text normalization implementations.

## Overview

This project demonstrates how to use Metamorphic Guard to evaluate two text normalizer implementations:
- **Baseline**: Simple normalizer (strip, collapse whitespace, lowercase)
- **Candidate**: Enhanced normalizer with Unicode normalization and non-breaking space handling

Metamorphic Guard compares these implementations by:
- Generating synthetic user text inputs
- Checking properties of each output
- Applying metamorphic relations (input transformations that shouldn't change normalized output)
- Running statistical gates to decide if the candidate is safe to adopt

## Installation

```bash
pip install metamorphic-guard
```

## Usage

Run the evaluation:

```bash
python run_guard.py
```

This will:
1. Generate 500 synthetic text inputs
2. Evaluate both implementations against properties and metamorphic relations
3. Compare results statistically
4. Output an adoption decision and generate a JSON report

## Properties

The normalizers are evaluated against these properties:

1. **Output is a string**: Ensures the function returns a string type
2. **No leading/trailing whitespace**: Normalized output should be trimmed
3. **No internal whitespace runs**: No sequences of multiple spaces

## Metamorphic Relations

The following metamorphic relations are tested:

1. **Whitespace Padding**: Adding leading/trailing whitespace should not change the normalized output
2. **Whitespace Bursting**: Expanding spaces into mixed whitespace characters should not change the normalized output
3. **Case Flip**: Changing the case of input text should not change the normalized output (both implementations lowercase)

## Project Structure

```
text_normalizer_guard_project/
├── implementations/
│   ├── __init__.py
│   ├── baseline_normalizer.py    # Simple normalizer
│   └── candidate_normalizer.py   # Enhanced normalizer
├── spec.py                        # TaskSpec with properties, relations, metrics
├── run_guard.py                   # Main evaluation script
└── README.md
```

## Implementation Details

Both implementations export a `solve(text: str) -> str` function that matches Metamorphic Guard's expected contract.

The baseline normalizer performs:
- Strip outer whitespace
- Collapse whitespace runs
- Convert to lowercase

The candidate normalizer additionally:
- Normalizes Unicode (NFKC)
- Converts non-breaking spaces to regular spaces
- Then applies the same steps as baseline

## Results

The evaluation produces:
- Adoption decision (boolean)
- Reason for decision
- Delta pass rate (difference in property/MR pass rates)
- Confidence interval
- Path to detailed JSON report

