# AGENTS.md

Rules for every coding agent working in this repository. Terse, scientific, minimal. If a rule here conflicts with a direct user instruction, the user wins; say so in one line.

## 0. Required: Ponytail

Ponytail is mandatory. It enforces the smallest complete change while never cutting validation, error handling, security, or tests for risky logic.

Install from the official sources only: `DietrichGebert/ponytail` on GitHub or `@dietrichgebert/ponytail` on npm. Reject any copy that ships `.exe` or `.dll` files.

| Agent | Install |
|---|---|
| Claude Code | Preconfigured in `.claude/settings.json`; accept the prompt when you trust the folder. Manual: `/plugin marketplace add DietrichGebert/ponytail` then `/plugin install ponytail@ponytail` |
| Claude cloud sessions (web, mobile app, `--cloud`) | Plugins don't load there. Upload upstream `skills/{ponytail,ponytail-review,ponytail-audit,ponytail-debt}` as claude.ai skills (Settings → Capabilities → Skills); cloud sessions load enabled skills automatically. No hooks, so no `/ponytail <level>` switching; the `ponytail` workflow still reviews every PR |
| Codex | `codex plugin marketplace add DietrichGebert/ponytail` then `codex plugin add ponytail@ponytail`; trust both hooks in `/hooks`; start a new thread |
| Anything else | Load `skills/ponytail/SKILL.md` as a skill, or vendor upstream `AGENTS.md` as `.agents/ponytail.md` and read it before this file. Per-agent steps: upstream `INSTALL.md` |

Use:
- Default mode `full`. Set via `PONYTAIL_DEFAULT_MODE=full` or `~/.config/ponytail/config.json`.
- Run `/ponytail-review` on every diff before declaring done. Fix all "must fix" findings.
- Run `/ponytail-audit` before a release or after any large refactor.
- Run `/ponytail-debt` before each release; every `shortcut:` comment gets an owner or is resolved.
- Shortcut format: `shortcut: <the limit>, <when to upgrade>`.

If Ponytail cannot be installed in the current environment, state that at the top of your reply and apply section 2 manually.

## 1. Precedence

1. Correctness and scientific validity.
2. Safety: trust-boundary validation, data-loss prevention, security, privacy.
3. Ponytail's ladder: least new code that fully solves the task.
4. Everything else in this file.

## 2. Before writing code

- Read the task and every file the change touches. List callers, tests, fixtures, configs, exports.
- State assumptions in one line each. If an assumption changes the result, ask; otherwise proceed.
- Climb the ladder, stop at the first rung that holds: needed at all? → already in repo? → stdlib/platform? → installed dependency? → one clear line? → minimum code that works.
- New dependency requires a one-line justification in the PR. Never add one for a few lines.

## 3. Scientific rigor

- **Reproducibility.** Every run is reproducible from commit hash + lockfile + config + seed. Seed all RNGs (Python, NumPy, framework, CUDA) from one config value. Record nondeterministic kernels when enabled.
- **Provenance.** Raw data is immutable and never edited in place. Each derived artifact records inputs (with hashes), code version, and parameters.
- **Leakage.** Split before any fitting, normalization, imputation, feature selection, or tuning. Split by the independent unit (patient, subject, site, batch, time), never by row when rows are correlated. Test sets are touched once.
- **Statistics.** Report effect size with uncertainty (CI or posterior interval), n, and the unit of n. No bare p-values. Correct for multiple comparisons. Pre-declare primary metric and threshold. For imbalanced classes report calibration and threshold-specific metrics (sensitivity at fixed specificity, PPV at stated prevalence), not accuracy alone.
- **Baselines.** Every model result is compared to a trivial baseline and the current best method, on identical splits.
- **Ablations.** A claimed component contribution needs an ablation. Variance across ≥3 seeds or bootstrap.
- **Numerics.** Use log-space for probabilities and likelihoods. Use `logsumexp`, stable softmax, and `np.isclose`/`math.isclose` with explicit tolerances. Never compare floats with `==`. Assert shapes and dtypes at function boundaries where silent broadcasting is possible.
- **Units.** Physical quantities carry units in names (`conc_ng_ml`, `dt_s`) or types. No unit-less magic numbers; named constants with a source citation.
- **Negative results** are recorded, not deleted.

## 4. Code style

- Python ≥ 3.12. Type hints on all public functions. Prefer plain functions and dataclasses over class hierarchies.
- Names are precise and domain-correct. Math variables may mirror the paper's notation if the docstring cites the equation.
- Docstrings: one-line summary, then Args/Returns/Raises only when non-obvious. Shapes as `(n_samples, n_features)`.
- Comments explain *why*, one line. Never restate the code.
- No dead code, commented-out blocks, speculative options, or "for later" abstractions.
- Pure functions for transforms; side effects (I/O, logging, plotting) at the edges.
- Fail loudly: raise specific exceptions with the offending value. No bare `except`. No silent fallbacks that change results.
- Vectorize before you loop; profile before you optimize.

## 5. Tooling

| Concern | Tool |
|---|---|
| Env + lockfile | `uv` (`uv.lock` committed) |
| Lint + format | `ruff check --fix` and `ruff format` |
| Types | `pyright` (strict on `src/`) or `mypy --strict` |
| Tests | `pytest`; `hypothesis` for parsers, transforms, and numerical invariants |
| Notebooks | Exploration only. Logic used twice moves to `src/`. Strip outputs before commit (`nbstripout`) |
| Config | One typed config object per run; no scattered globals or env lookups inside logic |
| Experiments | Log params, metrics, artifacts, and git SHA to the project's tracker |
| Hooks | `pre-commit` running ruff, type check, and fast tests |

## 6. Tests

- Logic with a branch, loop, parser, statistic, or security relevance ships with at least one small test.
- Numerical code: test against a known analytic result or a reference implementation, plus one invariant (symmetry, conservation, normalization, monotonicity).
- Data code: test schema, empty input, NaN handling, and one malformed record.
- Bug fixes start with a failing test that reproduces the bug.
- Tests are deterministic and fast; anything slow gets `@pytest.mark.slow`.

## 7. Data, security, privacy

- No credentials, tokens, or patient-identifiable data in code, logs, fixtures, or commits. Use synthetic or de-identified fixtures.
- Validate all external input at the boundary (schema, ranges, encodings).
- Never log raw sensitive records; log counts, hashes, or IDs.
- Destructive operations (delete, overwrite, migrate) require an explicit flag and a dry-run path.

## 8. Commits and PRs

- Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`). Imperative mood, ≤ 72-char subject.
- One logical change per commit. Diff stays as small as the task allows.
- PR description: what changed, why, how it was verified, what was not checked.

## 9. Agent output style

- Terse. Lead with the result. No preamble, no recap of the request, no praise.
- Report numbers with units and uncertainty.
- Distinguish verified (ran it), reasoned (did not run), and assumed.
- End every reply with one or two lines: what was skipped or not checked, and any risk the user must know.
- Ask at most one question, and only when the answer changes the work.

## 10. Development journal

- `JOURNAL.md` holds a ≤ 25-line summary (state, standing decisions, current best results, open questions) and an index of entries. `journal/YYYY-MM-DD-<slug>.md` holds one append-only entry per working day.
- End every work session by running the `historian` agent (Claude Code: `.claude/agents/historian.md`). Other agents follow that file's procedure directly.
- Entries record evidence only: commits, verified results with uncertainty, negative results, open risks. Unverified claims are marked.
- Merges to `main` that touch the journal publish it to GitHub Pages (`.github/workflows/journal.yml`). Only the journal is published.

## 11. Definition of done

- [ ] Ponytail installed and active; `/ponytail-review` clean of "must fix"
- [ ] `ruff`, type check, and tests pass locally
- [ ] Results reproducible from SHA + lockfile + config + seed
- [ ] No leakage across splits; metrics reported with uncertainty and baseline
- [ ] Every `shortcut:` has a stated upgrade condition
- [ ] Journal entry written and summary refreshed
- [ ] Reply ends with skipped/unchecked items and risks
