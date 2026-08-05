---
name: data-engineering-data-pipeline
description: End-to-end data pipeline verification, preproduction testing, X.com content curation, and log auditing.
triggers:
  - pipeline
  - curator
  - live_persistent_curator
  - PostExporter
  - LinkedInRewriter
  - X.com
---

# Data Engineering & Pipeline Protocol

## 1. Pipeline Verification Workflow
- **AST Parse Gate**: Run `python -c "import ast; ..."` across all 11 pipeline modules before launching full browser cycles.
- **Import Check**: Run python subprocess import checks to verify zero dependency regressions.

## 2. Dry-Run & Preproduction Gate
- Preproduction mode (`--mode all --max-feed N`) generates and logs AI responses without triggering actual DOM clicks on like/comment/send buttons.
- `--live` mode must be explicitly provided for real LinkedIn post publishing and messaging.

## 3. Log Audit Standard
- Audit task logs for ⚠️ warning symbols (`file input not reachable`, `Node is not an HTMLElement`, `TargetClosedError`). Every ⚠️ must be traced to root cause and resolved.
