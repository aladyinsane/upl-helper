# Development workflow

Every nontrivial change goes through this loop. No implementation starts before
an ADR is accepted.

## 1. ADR

Write `docs/adr/NNNN-short-title.md` from `docs/adr/ADR_TEMPLATE.md`.
Open a PR with the ADR alone. The PR is the review gate — nothing gets built
until the ADR is marked **Accepted** and the PR is merged.

An ADR covers a decision, not a task list. If there is no real choice being
made, it does not need an ADR.

## 2. Spec

Write `docs/specs/NNNN-short-title.md` from `docs/specs/SPEC_TEMPLATE.md`,
derived from the accepted ADR. The spec has to be detailed enough that an
implementer never has to guess what was meant. Anything genuinely undecided
goes in **Open Questions** to be flagged, not guessed at.

The spec can ride in the ADR PR for small decisions, or go in its own PR.

## 3. Implement

Work on a branch off `main`, one branch per spec. Keep the branch scoped to
what the spec covers.

## 4. Test

Tests are written against the spec's acceptance criteria, not against whatever
the code happens to do. Run the full suite before opening the PR.

## 5. PR

Open the PR. Review it against the ADR and the spec — does it do what was
decided, not just does it work. Merge when green.

## 6. Update the index

`docs/project/index.md` gets a short entry: what changed, what was decided,
what is next. Terse bullets, not prose.

## Branch naming

- `adr/NNNN-short-title` — ADR only
- `feat/NNNN-short-title` — implementation of spec NNNN
- `fix/short-title` — bug fix

Claude Code web sessions are assigned a `claude/<topic>` branch by the
harness and push to that instead. Same loop, different branch name.

## Commits

Present tense, say what the change does and why if it is not obvious.
