# Sample Reports

This directory contains validated sample reports generated from end-to-end testing of the Fairness Guard project.

## Reports

- `report_*.json`: Sample evaluation reports showing:
  - Successful candidate adoption (fair implementation)
  - Failed candidate rejection (biased implementation)

## Report Structure

Each report contains:

- **Core Metrics**: Baseline and candidate pass rates, delta, confidence intervals
- **Fairness Metrics**: Overall approval rates, group-level rates, fairness gaps
- **Decision**: Adoption decision with reason
- **Violations**: Property and metamorphic relation violations (if any)
- **Metadata**: Hashes, fingerprints, job metadata, environment info

## Usage

These reports can be used for:
- Testing report parsing and visualization tools
- Understanding report structure with fairness metrics
- Documentation examples
- CI/CD integration testing
- Regulatory compliance demonstrations

## Validation

All reports in this directory have been validated to ensure:
- Required fields are present
- Data types are correct
- Structure matches the report schema
- Fairness metrics are included and valid


