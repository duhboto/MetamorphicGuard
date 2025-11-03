# Demo Project Using Metamorphic Guard

This miniature client project shows how downstream users can consume the
`metamorphic-guard` library programmatically.

## Prerequisites

```bash
python -m pip install metamorphic-guard==1.0.1
```

## Run the demo

```bash
python src/run_demo.py
```

The script compares the bundled baseline and improved `top_k` implementations,
prints the adoption decision, and saves a JSON report under `../reports/`.
