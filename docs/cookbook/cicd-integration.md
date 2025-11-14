# CI/CD Integration

This guide shows how to integrate Metamorphic Guard into your CI/CD pipelines.

## GitHub Actions

### Basic Template

Copy `.github/workflows/templates/metamorphic-guard.yml` to your repository:

```yaml
name: Metamorphic Guard Evaluation

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install metamorphic-guard
      - run: |
          metamorphic-guard evaluate \
            --task top_k \
            --baseline baseline.py \
            --candidate candidate.py \
            --n 400 \
            --junit-report reports/junit.xml
      - uses: actions/upload-artifact@v4
        with:
          name: reports
          path: reports/
```

### Using Repository Variables

Set variables in GitHub repository settings:

- `MG_TASK_NAME`: Task name (default: `top_k`)
- `MG_BASELINE_PATH`: Baseline path (default: `baseline.py`)
- `MG_CANDIDATE_PATH`: Candidate path (default: `candidate.py`)
- `MG_N`: Number of test cases (default: `400`)

### LLM Evaluation

For LLM evaluations, add API keys as secrets:

```yaml
- name: Run evaluation
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  run: |
    metamorphic-guard evaluate \
      --task llm_task \
      --executor openai \
      --executor-config '{"model": "gpt-3.5-turbo"}' \
      --estimate-cost
```

## GitLab CI

### Include Template

Add to your `.gitlab-ci.yml`:

```yaml
include:
  - local: '.gitlab-ci/templates/metamorphic-guard.yml'

variables:
  MG_TASK_NAME: "top_k"
  MG_BASELINE_PATH: "baseline.py"
  MG_CANDIDATE_PATH: "candidate.py"
```

### Custom Job

```yaml
metamorphic_guard:
  stage: test
  image: python:3.11
  script:
    - pip install metamorphic-guard
    - metamorphic-guard evaluate --task top_k --baseline baseline.py --candidate candidate.py
  artifacts:
    paths:
      - reports/
    reports:
      junit: reports/junit.xml
```

## Jenkins

### Pipeline Script

Use the template from `jenkins/templates/metamorphic-guard.groovy`:

1. Create a new Pipeline job
2. Copy the Groovy script
3. Configure environment variables
4. Run the pipeline

### Declarative Pipeline

```groovy
pipeline {
    agent any
    stages {
        stage('Evaluate') {
            steps {
                sh '''
                    pip install metamorphic-guard
                    metamorphic-guard evaluate \
                        --task top_k \
                        --baseline baseline.py \
                        --candidate candidate.py
                '''
            }
        }
    }
}
```

## Best Practices

1. **Fail on Rejection**: Set `--min-delta` and `--min-pass-rate` appropriately
2. **Upload Reports**: Always archive reports as artifacts
3. **JUnit Integration**: Use `--junit-report` for test result visualization
4. **Cost Estimation**: Use `--estimate-cost` for LLM evaluations
5. **Parallel Execution**: Use `--parallel` for faster execution

## Examples

See the templates directory for complete examples:
- `.github/workflows/templates/` - GitHub Actions
- `.gitlab-ci/templates/` - GitLab CI
- `jenkins/templates/` - Jenkins

## Notifications

Use webhook alerts to push failures to ChatOps:

```bash
metamorphic-guard evaluate \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --alert-webhook https://hooks.slack.com/services/... \
  --html-report reports/latest.html
```

For richer messages use the Slack helper in `metamorphic_guard.notifications.send_slack_message`.

## Kubernetes / Helm

The Helm chart under `deploy/helm/metamorphic-guard` deploys queue workers:

```
helm install guard deploy/helm/metamorphic-guard \
  --set image.tag=2.2.0 \
  --set queue.backend=redis
```

## Policy Snapshots

Version policies before deployment:

```
metamorphic-guard policy snapshot policies/policy-v1.toml --label release-2025-11
metamorphic-guard policy rollback policies/history/policy-v1-release-2025-11-20251113-120000.toml policies/policy-v1.toml
```

