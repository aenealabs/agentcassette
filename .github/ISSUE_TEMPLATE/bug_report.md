---
name: Bug report
about: Something isn't working correctly
labels: bug
---

## Description

A clear description of the bug.

## Reproduction

```python
import agentcassette
from agentcassette import record, replay

call_model = agentcassette.intercept(call_model, kind="llm")

# What you did:
with record("cassette.json"):
    ...

# What you expected:

# What you got:
```

## Environment

- agentcassette version:
- Python version:
- OS:

## Traceback

```
Paste the full traceback here, if any.
```
