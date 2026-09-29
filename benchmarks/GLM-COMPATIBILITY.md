# OpenCode GLM 5.3 synthetic compatibility, 29-Sep-2026

Client: OpenCode 1.18.30 with `--pure --auto`. Model: GLM 5.3.
Product candidate: dirty-tree v0.5.0 package SHA-256
`7d29069fb36646fe810513a5dd116cc7af2fa625dc38e3c2812063e59a67d6f3`.
The test folder contained only synthetic Markdown and used a private temporary
state directory. No real vault text was sent to GLM.

The first fresh session read AGENTS/INDEX, used `recall` and hash-checked
`show` to retrieve the synthetic checksum, used `append-row` to add one row to
an existing Wiki table, and ran `sync --brief`. Independent local inspection
found the row exactly once; `folder-status --brief` reported two history events
and three tracked files. The second independent session found the saved row
with `recall` and checked history. This tests real CLI tool execution and
persistence across sessions in this client/model/provider combination.

| Session | Tool calls | Uncached input | Cached input | Output |
| --- | ---: | ---: | ---: | ---: |
| Write/capture | 12 | 10,902 | 73,920 | 751 |
| Fresh recall | 7 | 3,449 | 56,064 | 451 |

The first session made four CLI help calls before using the commands. The
second first tried an unsupported `--private-state` flag, then recovered via
help and used `--state-dir`. These are material token and latency costs in
fresh sessions. The run does not prove
that v0.5 reduces complete-task tokens against the existing native-file flow.
It also does not test Kimi or Qwen, or prove other
OpenCode configurations and operating systems.

Full JSON event logs remain in private local temporary state, outside this
public repository. Repeat the same workflow with the exact clean release
package before claiming final-package compatibility.

## Paired complete-task token result

Follow-up paired synthetic runs used the same OpenCode client, GLM 5.3 route,
prompt and frozen Wiki evidence within each pair. The baseline used installed
v0.4.0 and native Markdown tools. Candidate runs used a dirty-tree v0.5.0
package. Every reported pair below passed the factual answer, exactly-one-row,
and local capture checks. Totals are the client's `tokens.total`, including
uncached input, cached input, output and separately reported reasoning. No real Vault content entered
these model sessions.

| Synthetic task and candidate route | Baseline total tokens | v0.5 total tokens | Difference | Accepted |
| --- | ---: | ---: | ---: | --- |
| Small exact fact, forced recall/show/append; write plus fresh recall | 182,134 | 215,083 | **18.1% more** | Both |
| Unknown-location fact, 51,036-word register, recall/append; write and capture | 146,754 | 273,662 | **86.5% more** | Both |
| Same large task, compact startup and native search/edit; write and capture | 146,754 | 231,145 | **57.5% more** | Both |
| Same large task, compact native rules with a hard 80-line read limit; write and capture | 543,026 | 100,448 | **81.5% fewer** | Both |

The large-task baseline initially inserted the row but failed capture because
its synthetic AGENTS lacked the explicit private `--state-dir`. That attempt
was excluded; the accepted baseline was rerun from frozen source with the
state route supplied. Candidate recall required multiple invalid location
attempts before a valid command. In the compact-native arm, the model read
53,279 bytes from the long register in one tool call despite guidance to use
bounded reads; its two private-event inspection calls returned 1,097 bytes.
The accepted baseline read 5,412 bytes across two bounded register calls.

In a final fresh pair, the compact candidate explicitly forbade whole-note
reads and private-event inspection during routine work. It read two bounded
register segments totaling 3,676 bytes and inspected no private events. The
paired baseline read 53,280 bytes in one register call. Its 543,026-token
total was also much higher than the earlier accepted 146,754-token baseline,
showing considerable run-to-run variation. The candidate's 100,448 tokens
were lower than both observed baselines. One final repeat used byte-identical
synthetic AGENTS, INDEX and Wiki files and the same task prompt/model. It
accepted the same answer, single row and local capture with **94,186 total
tokens**, 11 tool calls, bounded register reads and no private-event
inspection. The two hard-rule candidate runs (100,448 and 94,186) were below
both accepted baselines (146,754 and 543,026), including a 31.6% to 35.8%
reduction against the lower baseline. This supports a repeatable gain within
the tested synthetic task and GLM route, while baseline variance remains high.

**Forced use of recall/show/append increased GLM tokens; hard bounded native
reads produced a repeatable synthetic gain.** These synthetic results do not
establish a general token-savings claim across models, tasks or providers.
