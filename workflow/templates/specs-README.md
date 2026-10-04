# Specs

Every feature goes spec → tests → freeze → implement. The IDs are `RNNN-MM`: spec number,
then requirement number. Each spec depends only on lower numbers.

| ID | Spec | Depends on |
|---|---|---|
| 000 | [vision](000-vision/spec.md): constitution, scope, glossary, roadmap | none |

Suggested order: the specs that others depend on first.

## Resume point

Run `{{python}} .agentkit/bin/agentkit status` for the active spec and its next step.
