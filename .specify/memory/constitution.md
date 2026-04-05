<!--
SYNC IMPACT REPORT
==================
Version change: N/A (initial) → 1.0.0
Modified principles: N/A (initial ratification)
Added sections:
  - Core Principles (5 principles)
  - Testing Strategy
  - Development Workflow
  - Governance
Removed sections: N/A
Templates reviewed:
  ✅ .specify/templates/plan-template.md — Constitution Check gate aligns with principles
  ✅ .specify/templates/spec-template.md — User Scenarios & Testing section aligns with test-first principle
  ✅ .specify/templates/tasks-template.md — Test tasks marked OPTIONAL; FamilyVault overrides this:
     tests are MANDATORY per Principle II. Tasks template note retained for spec-kit compatibility.
Follow-up TODOs: None. All fields resolved.
-->

# FamilyVault Constitution

## Core Principles

### I. Test-First (NON-NEGOTIABLE)

TDD is mandatory — no implementation code is written before a failing test exists.
The cycle is strictly: write test → confirm it fails → implement → confirm it passes → refactor.

Tests MUST be written upfront to validate requirements and provide clarity on how
each feature will be tested before any implementation begins. This is not optional
and is a hard gate before planning is considered complete.

**Rationale**: Tests written after the fact verify implementation, not behavior.
Tests written first define intent and serve as living documentation. For a solo
developer with AI assistance, pre-existing tests are the primary guardrail against
AI-generated regressions.

### II. Three-Layer Testing Pyramid

All features MUST have coverage across three test layers. Small tests are the
primary investment; medium and big tests exist to validate integration contracts
and end-user flows respectively.

**Small (unit) tests — the workhorse:**
- MUST test behavior, not implementation details
- MUST cover wide code paths including edge cases and error conditions
- MUST run fast (entire suite under 60 seconds)
- MUST use minimal mocking — prefer real objects and in-memory fakes over mocks
- "End-to-endish" unit tests that exercise a full vertical slice with no external
  dependencies are the ideal: hard to break, high confidence, AI-safe guardrails
- Quantity target: the majority of test coverage lives here

**Medium tests — API and persistence layer:**
- Operate at the service/API boundary with a real database (no mocks for persistence)
- Validate contracts between components and data integrity
- Slower than small tests but faster than big tests
- Cover happy paths and critical failure scenarios at the integration boundary

**Big tests — UI and end-to-end:**
- Include the UI and full system stack
- Fewer in number; focus on critical user journeys only
- Acceptable to be slow; MUST be stable (no flaky tests tolerated)

**Rationale**: This pyramid maximizes confidence-per-second-of-test-run. Small tests
catch regressions instantly; medium tests catch contract violations; big tests catch
user-facing regressions. AI code generation makes a strong small-test suite
especially critical as the primary regression shield.

### III. AI-Interaction First

The system MUST be operable through AI conversation. Complex UI navigation is a
secondary concern; AI-driven workflows are the primary interface.

Features that require a GUI MUST also expose an AI-accessible interface (API,
CLI, or MCP tool) that provides equivalent capability. New capabilities SHOULD be
designed as AI-accessible first, with UI as an optional layer on top.

**Rationale**: The project owner prefers AI interaction over complex UI navigation.
This also ensures features remain accessible without a browser and are easily
automatable.

### IV. Simplicity and YAGNI

Every design decision MUST justify its complexity. Abstractions are introduced only
when the same logic is needed in three or more places. Features are built for
current requirements, not hypothetical future ones.

As a solo project, every layer of indirection has a carrying cost with no team to
share it. Complexity MUST be explicitly justified in the plan's Complexity Tracking
section. When in doubt, the simpler approach wins.

**Rationale**: Solo development context means complexity compounds faster. YAGNI
prevents premature generalization that slows delivery and increases maintenance burden.

### V. Privacy and Local-First

All data processing MUST default to local execution. Photos, videos, and personal
metadata MUST NOT leave the home network unless the user explicitly opts in.

External AI API calls (e.g., Claude API for story generation) are permitted only
for non-sensitive metadata (captions, event names, descriptions) — never raw
photo/video bytes. Any feature that would send personal data to an external
service MUST have explicit user consent and MUST be opt-in.

**Rationale**: FamilyVault exists specifically to reclaim ownership of family
memories from cloud services. Violating that principle in the implementation
would undermine the project's core reason for existence.

## Testing Strategy

Tests are written before implementation in all cases. The following workflow is
mandatory for every feature:

1. Read the spec's acceptance scenarios
2. Write failing small tests that directly exercise those scenarios
3. Write failing medium tests for any persistence or API contracts
4. Get explicit confirmation tests fail for the right reasons
5. Implement until all tests pass
6. Refactor with tests as the safety net

**Test file naming convention** (to be established per language/framework chosen
for each component):
- Small tests: `tests/unit/` or `*_test.go` / `test_*.py` etc.
- Medium tests: `tests/integration/` or tagged `//go:build integration`
- Big tests: `tests/e2e/`

**Mocking policy**: Prefer real in-memory implementations over mocks. Use mocks
only for external network calls (iCloud API, Google Drive, Claude API). Database
and filesystem interactions in small tests MUST use in-memory or temp-dir fakes,
not mocks.

## Development Workflow

1. **Spec first**: Every feature starts with a spec (`/speckit-specify`)
2. **Clarify if ambiguous**: Run `/speckit-clarify` before planning when requirements
   are unclear
3. **Plan with constitution check**: Run `/speckit-plan` — the Constitution Check
   gate MUST pass before implementation begins
4. **Tests before tasks**: Test scenarios are defined in the spec and translated to
   test tasks before implementation tasks in `/speckit-tasks`
5. **Implement incrementally**: Each task delivers a testable increment; commit after
   each passing test group
6. **AI as pair programmer**: Treat AI suggestions as pull requests — review for
   correctness, test coverage, and constitution compliance before accepting

## Governance

This constitution supersedes all other practices and preferences on this project.
Any deviation MUST be documented in the relevant plan's Complexity Tracking section
with explicit justification.

**Amendment procedure**: Update this file, increment the version following semantic
versioning rules (see report header for rules), update `Last Amended` date, and
propagate changes to affected templates.

**Compliance review**: Each plan's Constitution Check section serves as the
compliance gate. No feature moves to implementation without passing it.

**AI guardrails**: The small test suite is the primary mechanism for keeping AI
assistance safe. A feature is not "done" until its small tests serve as a
regression shield — i.e., breaking the feature MUST cause at least one small test
to fail.

**Version**: 1.0.0 | **Ratified**: 2026-04-04 | **Last Amended**: 2026-04-04
