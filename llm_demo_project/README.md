# LLM Guard Demo Project

This project demonstrates how to use **Metamorphic Guard** to evaluate LLM applications without needing live API keys, using a **Mock Executor**.

## Features Demonstrated
- **Custom Executors**: Plug in your own LLM backend (or a mock one).
- **LLM Task Specs**: Define properties (Length, PII) and Metamorphic Relations (Paraphrasing).
- **Cost Monitoring**: Track simulated token usage and costs.
- **Adoption Gating**: Automated pass/fail decisions.

## How to Run

```bash
python llm_demo_project/run_demo.py
```

## Output
The script will:
1. Register a `MockLLMExecutor` that simulates GPT-4 responses.
2. Run 20 test cases comparing a "Verbose" baseline vs a "Concise" candidate.
3. Check properties (e.g. max length).
4. Generate a JSON report in `llm_demo_project/reports/`.

