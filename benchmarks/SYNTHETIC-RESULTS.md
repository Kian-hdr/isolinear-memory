# Candidate v0.5 retrieval comparison, 29-Sep-2026

The disposable synthetic fixture in `recall_pair.py` exercises rare facts,
changed/competing facts, a heading with the answer on the next line, reordered
query words, Raw/Output opt-in, absence, edit freshness and deletion freshness.
The tested package was a **dirty-tree candidate**, SHA-256
`88fc93b68c5924d90a09333ec5a3906ebf4859275a0029eca0cd6ef3ecc26fd0`.
Run again on the exact clean release artifact before using these numbers as
release evidence.

| Route | Correct source and answer | Agent tool calls | Returned bytes | `o200k_base` reference tokens | Median CLI time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Targeted `rg` plus necessary bounded reads | 13/13 | 15 | 732 | 197 | 7.5 ms |
| v0.5 `recall` plus necessary `show` | 13/13 | 14 | 1,998 | 629 | 159.8 ms |

The private derived SQLite index occupied 32,768 bytes at the end of the
fixture run. Both routes returned current evidence after an edit and omitted
the deleted source. The reference tokenizer is `tiktoken 0.14.0`; its counts
are **not GLM tokens, provider billing or complete-task usage**. Short exact
queries favor `rg` because the source hash and structured hit metadata cost
context. The saved results do not pass a retrieval-only token-efficiency gate.

Startup-instruction compaction and lower read/decision retries may still save
complete-task tokens. Test that with actual paired sessions and the private
`paired_task_cost.py` ledger before any vault cutover. This synthetic result
does not establish a per-vault total-token improvement.
