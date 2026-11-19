---
version: <positive integer>
run_id: <16 lowercase hexadecimal characters>
status: draft|active|complete|limit|aborted
base_commit: <full commit id at workflow start>
max_verifier_invocations: 2
---

# User Intent
| id | stakeholder | intention | observable goal |
| --- | --- | --- | --- |

# Scope
In scope: <behavior and product boundary>
Out of scope: <explicit exclusions>

# Paths
Implementation: <comma-separated repo paths>
Tests: <comma-separated repo paths>
Test command: <one shell command covering all automated functional and quality checks, including the project's lint gate when it has one; fails when a structure-based coverage target is missed>
Review evidence: <named procedure/output, or none — reason>
Fuzzing: <tool, harness, surface, oracle (crash / property / differential), seed, budget — or none — reason>
Mutation tool: <tool and command, sample cap and seed, survival threshold (default 40%) — or none>

# Signatures
<signature per line>

# Functional Requirements
| id | requirement | priority | source |
| --- | --- | --- | --- |

# Errors
<failure condition — observable signal, including non-exception failures — post-failure state>

# Cases
| id | level | input / state | expected result |
| --- | --- | --- | --- |

# Quality Applicability
| ISO/IEC 25010:2023 characteristic | applicable | rationale |
| --- | --- | --- |
| Functional suitability | yes / no | ... |
| Performance efficiency | yes / no | ... |
| Compatibility | yes / no | ... |
| Interaction capability | yes / no | ... |
| Reliability | yes / no | ... |
| Security | yes / no | ... |
| Maintainability | yes / no | ... |
| Flexibility | yes / no | ... |
| Safety | yes / no | ... |

# Quality Requirements
| id | characteristic / subcharacteristic | target and context | measure method / inputs / unit | threshold and direction | evidence: automated, review, mutation | source |
| --- | --- | --- | --- | --- | --- | --- |

# Verification Obligations
| id | parent requirement/Case ids | variant and target surface | test layer and selection policy | ISO/IEC/IEEE 29119-4 technique | coverage items | coverage target | observation and expected result | evidence procedure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

# Assumptions and Defaults
| id | decision | evidence and uncertainty | brief v<n> — approved / vetoed → <answer> / user answer / user decision (main: <own option>) / facts.md: <first words of the entry> |
| --- | --- | --- | --- |

# Alternatives
| decision id | option not taken | what it gains and what it costs | reversal condition: the state of the world in which it wins |
| --- | --- | --- | --- |

# Open Questions
| id | question | requirement, decision, or step it affects | what would settle it | open / settled v<n> — <answer> / deferred — <reason> |
| --- | --- | --- | --- | --- |

# Completion Questions
| id | question | expected answer | what it tests: trade-off / engineer call (decision id) / final shape | built by: step id, or `all` | asked: no / closing <YYYY-MM-DD> | valid / invalid v<n> — <reason> |
| --- | --- | --- | --- | --- | --- | --- |

# Traceability
| requirement id | Case ids | obligation ids | evidence procedure |
| --- | --- | --- | --- |

# Workflow Control
| item | value |
| --- | --- |
| correction batches used | 0 |
| verifier invocations | 0 |
| open finding ids | none |

Audit state (one entry per obligation; retain prior decisions in the execution ledger):
| obligation id | spec version | evidence references and revision | accepted / open / invalidated / pending | rationale and mutation outcome | dependencies and reopening evidence |
| --- | --- | --- | --- | --- | --- |

Execution ledger (append attempts; preserve failed approaches):
| attempt | finding / failure signature | cause hypothesis | changed approach / new evidence | result / disposition |
| --- | --- | --- | --- | --- |

# Version Log
## v<n>
- <what changed and the evidence or decision that forced it>

# Steps
| id | outcome the user can observe when it is done | requirement ids | obligation ids | depends on | held decisions | pending / active / done <YYYY-MM-DD> | verifier invocations |
| --- | --- | --- | --- | --- | --- | --- | --- |

# Session Memory
## Failed Attempts & Reasons
| step | recorded: <YYYY-MM-DD>, <HEAD> | attempt | failure evidence | cause — verified / hypothesis | how to re-check |
| --- | --- | --- | --- | --- | --- |

## Decisions & Reasons & Alternatives
| step | recorded: <YYYY-MM-DD>, <HEAD> | decision | reason and evidence | alternative not taken | what would reopen it |
| --- | --- | --- | --- | --- | --- |

## Unresolved Questions & Uncertainties
| step | recorded: <YYYY-MM-DD>, <HEAD> | question or uncertainty | what is known, with evidence | what would settle it |
| --- | --- | --- | --- | --- |
