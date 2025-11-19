# LLM Guard Tutorial: Evaluating AI Models without API Keys

This tutorial demonstrates how to use **Metamorphic Guard** to evaluate LLM applications.
We use a **Mock Executor** to simulate LLM behavior, so you don't need OpenAI/Anthropic API keys to run this demo.

## 1. Project Setup

The demo project is self-contained in `llm_demo_project/`.
It contains:
- `src/mock_executor.py`: A plugin that simulates GPT-4 responses.
- `src/llm_task.py`: The evaluation task specification (inputs, properties, relations).
- `run_demo.py`: The runner script.

## 2. The Scenario

We are upgrading an AI assistant from a **Baseline** version to a **Candidate** version.

- **Baseline**: Configured to be "Verbose" (simulated).
- **Candidate**: Configured to be "Concise" (simulated).

**Goal**: We want to ensure the new model is concise (length < 200 chars) and doesn't leak PII, while maintaining robustness.

## 3. The Task Specification (`src/llm_task.py`)

We define a task `llm_demo` with:

### Properties (Quality Gates)
1. **Max Length**: Output must be under 200 characters.
   - *Baseline (Verbose)* should FAIL this.
   - *Candidate (Concise)* should PASS this.
2. **No PII**: Output must not contain phone numbers/emails.

### Metamorphic Relations (Robustness)
1. **Paraphrasing**: If we paraphrase the input, the output structure should remain consistent (equality check).

## 4. Running the Evaluation

Run the demo script:

```bash
python llm_demo_project/run_demo.py
```

## 5. Understanding the Results

The script will output:

```text
🚀 Starting LLM Demo with Mock Executor...

✅ Evaluation Complete!
Results:
  Pass Rate Delta: 0.2000
  Decision: Adopt (meets_gate)
```

### Why did it pass?
- The **Baseline** failed the "Max Length" property (0% pass rate).
- The **Candidate** passed the "Max Length" property (100% pass rate).
- The improvement (Delta) is +0.20 (or higher depending on weighting).
- Since Delta > 0.01 (default threshold), the candidate is **Adopted**.

## 6. Key Concepts Demonstrated

- **Custom Executors**: We injected `MockLLMExecutor` at runtime. You can do the same for local HuggingFace models or custom APIs.
- **LLM Judges**: We used `LengthJudge` and `NoPIIJudge` to grade text outputs.
- **Cost Monitoring**: The report includes simulated token usage and costs.
- **Adoption Gating**: The decision was automated based on statistical significance.

