# Project Instructions

## Purpose

This project is a replication of the core functionality of LiteChat for the ITENT 45 midterm.

The goal is to demonstrate effective management of an agentically-coded software project. Do not treat the project as a request to blindly implement features. First understand the requirements, document decisions, create a plan, then implement the plan.

---

# Development Workflow

All substantial work should follow this workflow:

1. Study
2. Plan
3. Execute plan
4. Rendezvous
5. Sync docs

## 1. Study

When asked to study a request:

- Analyze the request before modifying application code.
- Inspect the existing codebase and relevant documentation.
- Identify requirements, constraints, feasibility, tradeoffs, risks, and open questions.
- Do not implement the requested changes yet.
- Write the study as a Markdown file in `doc/study/`.
- Use a descriptive filename.
- The study should contain enough detail to support the later planning step.

## 2. Plan

When asked to create a plan:

- Base the plan on the relevant study document.
- Convert the study into concrete implementation steps.
- Write the plan as a Markdown checklist in `doc/plan/`.
- Include testing and verification steps.
- Do not begin implementation unless explicitly asked to execute the plan.

## 3. Execute Plan

When asked to execute a plan:

- Find and read the relevant plan document.
- Follow the plan rather than inventing an unrelated implementation.
- Work on a separate Git branch from `main`.
- Make changes in small, understandable steps.
- Test changes as appropriate.
- Update the plan checklist as work is completed.
- Use conventional commits.

Examples:

- `feat: add chat sessions`
- `fix: handle failed llm requests`
- `test: add session tests`
- `docs: update architecture documentation`
- `chore: configure development environment`
- `build: add project dependencies`

Do not make unrelated changes while executing a plan.

## 4. Rendezvous

When a plan has been successfully executed:

- Verify that the implementation works.
- Run relevant tests and checks.
- Review the resulting code for obvious issues.
- Confirm that the branch is in a workable state.
- Merge the implementation branch back into `main` when appropriate.
- Do not merge incomplete or knowingly broken work.

## 5. Sync Docs

After the codebase changes:

- Check the living documentation in `doc/wiki/`.
- Update documentation that no longer accurately describes the codebase.
- Documentation should describe the actual current implementation, not an intended or outdated implementation.
- Keep documentation changes separate and clear when practical.

---

# Documentation Structure

Use these directories for project documentation:

- `doc/study/` — analysis, feasibility, tradeoffs, requirements, and research
- `doc/plan/` — concrete implementation checklists
- `doc/wiki/` — living documentation of the current codebase

Do not place study documents in `doc/plan/` or implementation plans in `doc/study/`.

---

# Git Rules

- `main` is the stable branch.
- Feature or implementation work should normally happen on a separate branch.
- Use conventional commits.
- Keep commits focused and understandable.
- Do not rewrite Git history unless explicitly requested.
- Do not commit secrets, API keys, passwords, or other credentials.

---

# Agent Behavior

Before making substantial changes:

1. Understand the request.
2. Inspect relevant files and existing documentation.
3. Identify what is known and what is uncertain.
4. Follow the study/plan/execute workflow when appropriate.

Do not assume that every feature of the reference application must be replicated.

Prioritize the documented core functionality required by the project.

If an important requirement is ambiguous, investigate the available evidence or document the uncertainty rather than silently inventing a requirement.

Avoid unrelated refactoring or scope expansion.

---

# LiteChat Context

The reference application is LiteChat.

The project should replicate its core functionality rather than necessarily reproduce every feature or every visual detail of the original application.

The provided LiteChat proxy/API access should be investigated during the study phase before implementation decisions are finalized.

Do not expose API keys or other credentials in source code, documentation, Git history, or client-side code.

---

# Definition of Done

A task is not considered complete merely because code was written.

Completion should include, as appropriate:

- implementation
- relevant tests/checks
- verification that the feature works
- updated plan checklist
- updated living documentation when affected
- appropriate conventional commit(s)
- a workable Git branch ready for rendezvous