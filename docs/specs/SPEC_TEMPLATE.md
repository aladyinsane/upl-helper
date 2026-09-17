# SPEC-NNNN: <title>

Implements ADR-NNNN.

## Goal

One or two sentences. What exists at the end that does not exist now.

## Context & constraints

Environment, allowed dependencies (be specific: "pandas and openpyxl only,
stdlib otherwise"), performance limits, compliance limits, anything that
rules out an otherwise obvious approach.

## Pipeline / stages

Per stage: input -> transformation -> output. Name the module or function
that owns each stage.

## Data contracts

Concrete schemas between stages. Column names, dtypes, nullability, keys,
units. A reader should be able to build stage 3 without reading stage 2's code.

## Validation / acceptance criteria

Numbered, each one testable. "Check X flags a provider whose CCR is outside
[0.05, 1.5]" — not "CCR is validated".

## Out of scope

What this explicitly does not do, so nobody builds it by accident.

## Open questions

Things the implementer should flag rather than guess. If this list is long,
the spec is not done.
