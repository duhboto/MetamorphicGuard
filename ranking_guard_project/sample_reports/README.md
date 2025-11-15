# Sample Reports

This directory contains validated sample reports generated from end-to-end testing of the Ranking Guard project.

## Reports

- `report_*.json`: Sample evaluation reports showing:
  - Successful candidate adoption (heap implementation)
  - Failed candidate rejection (buggy implementation)

## Report Structure

Each report contains:

- **Core Metrics**: Baseline and candidate pass rates, delta, confidence intervals
- **Decision**: Adoption decision with reason
- **Violations**: Property and metamorphic relation violations (if any)
- **Metadata**: Hashes, fingerprints, job metadata, environment info

## Usage

These reports can be used for:
- Testing report parsing and visualization tools
- Understanding report structure
- Documentation examples
- CI/CD integration testing

## Validation

All reports in this directory have been validated to ensure:
- Required fields are present
- Data types are correct
- Structure matches the report schema

