---
name: explain-diff
description: >-
  Produce a self-contained HTML teaching page that explains a code change,
  diff, branch, or pull request in terms of both software behavior and
  scientific meaning (entity identity, identifiers and coordinates,
  missingness, joins, downstream interpretation). Use when the user asks
  for an HTML explanation, teaching walkthrough, or scientific explanation
  of a diff, PR, or branch. Do not use for a short verbal summary or a
  normal code review.
---

# Explain a code change

## Goal

One HTML page that builds this mental model:

question → source data → representation → algorithm → output → downstream interpretation

Scientific meaning is part of the software contract. Do not only list changed functions.

## Load project domain

Before exploring the diff, read project scientific context if it exists:

1. `{workspace}/.agents/skills/explain-diff/domain.md`
2. `domain.md` next to this `SKILL.md` (when installed as a project skill)

If both exist and differ, prefer the workspace copy. If neither exists, infer from README, tests, examples, and the diff. Do not assume sequence, structure, imaging, or any other modality.

## Principles

1. For each important change, answer **what the code does** and **what scientific operation or assumption that behavior represents**. Do not stop at “this function left-joins on an ID column”: say what those keys represent, whether both sides use the same scheme, why the join is appropriate, what unmatched rows mean, and how a wrong join would affect downstream results.
2. Implementation correctness ≠ scientific correctness. Tests, types, and green CI do not establish that identifiers, coordinates, units, or filters are scientifically right.
3. Separate **evidence** (code, tests, schemas, config, docs, fixtures) from **interpretation**. Never invent a scientific rationale. If an assumption cannot be verified locally, say so.
4. Trace scientifically meaningful fields from source through transforms to downstream use — only for fields the change actually touches.
5. Ask: could this change which observations are included, how they are represented, the numbers computed, or the conclusion drawn downstream? Watch for non-random dropping (selection effects).

### Question types (only when implicated)

Not a checklist to fill:

- What experimental or biological entity does each object represent? Does the change treat two entities as equivalent?
- Which identifier or coordinate systems are in play, and are they being mixed?
- What is the unit of observation, and can a join, filter, group-by, or reshape drop, duplicate, merge, reorder, or reassign it?
- What do missing, zero, NaN, None, and empty mean here? They are not equivalent unless the code says so.
- Which units, scales, or transforms apply?
- Does the result depend on a pinned reference, database, or tool version?

If identifiers, coordinates, or indices are transformed, diagram that mapping explicitly. Do not let the reader infer equivalence from variable names.

## Workflow

1. **Resolve the target.** Current checkout, uncommitted diff, `main...HEAD` / `origin/main...HEAD`, a PR, or a user-specified range. If ambiguous, infer and state the assumption in the page.
2. **Read the surrounding system**, not the hunk list: domain file, callers/callees, schemas, tests, examples, config. Prefer those over speculation. Do not run the full pipeline unless needed to explain a numerical change.
3. **Build the model, then write HTML:** scientific problem; old behavior; why it changed; new behavior; data in; transforms; assumptions; how correctness is checked; downstream effect.

Only discuss assumptions the change implicates.

## Page structure

Always include: title, one-paragraph summary, linked TOC, then:

1. **What changed and why** — scientific and software
2. **How it works** — algorithm and data flow with a toy or fixture example (label invented values as toy)
3. **Scientific impact** — before/after; which of observations / representation / numbers / conclusions actually moved; selection effects if rows drop
4. **Code walkthrough** — grouped by conceptual operation, not file order; tiny excerpts with `path:line`; distinguish infrastructure-only edits from scientifically consequential ones

Include only when relevant:

- Identifier/coordinate mapping diagram
- Assumptions vs invariants (where enforced or tested, if known)
- Validation, plus the most dangerous *silent* scientific failure (plausible-looking output, wrong interpretation)
- Realistic edge cases
- Quiz: 3–5 conceptual multiple-choice questions with plausible distractors and an explanation after selection. Skip for purely infrastructural diffs. Do not test filenames.

## Where to save

Default directory: `/tmp`. Filename: `YYYY-MM-DD-explanation-<slug>.html` (today’s date, short kebab-case slug).

Example: `/tmp/2026-08-14-explanation-residue-mapping.html`

If the user names a different directory or full path, use that instead. Create the directory if needed. Do not write inside the repository unless they explicitly ask to.

## HTML artifact

- One self-contained file: inline CSS and JS, no CDN, no network, no external fonts or images
- `pre, code { white-space: pre-wrap; }` so newlines survive
- Escape repository-derived text before inserting into HTML or JS
- Semantic HTML/CSS diagrams; no ASCII art
- Do **not** modify repository files (except when the user asked to save the HTML there)
- Do **not** use a Cursor canvas

Before handoff, confirm the file exists, opens offline, TOC links work, code blocks keep whitespace, and quiz clicks work if a quiz is present.

## Handoff

Return a `file://` link to the HTML. Then 3–4 sentences: what change was inspected, what surrounding pipeline was inspected, unverified assumptions, validation limits. The page holds the full explanation.

## Anti-patterns

- File-by-file diff narration or dumping the full diff
- Filling scientific categories that the change does not implicate
- Claiming scientific correctness because tests pass
- Inventing biology or experimental rationale
- Assuming a modality (sequence, structure, imaging, …) when `domain.md` is absent
