# RLHF Annotation Studio - Beta Testing Guide

This document is for beta testers validating the production exam workflow, RBAC behavior, and reviewer release flow.

## Environment

- Frontend: `https://rlhf-studio.intelliforge.tech`
- Exams page: `https://rlhf-studio.intelliforge.tech/exams`

## Test Accounts (Production)

Use the following seeded users:

- Admin (owner): `gen.girish@gmail.com` / `Demo@12345`
- Demo Admin: `exam.admin.demo@rlhf.dev` / `Demo@12345`
- Demo Reviewer: `exam.reviewer.demo@rlhf.dev` / `Demo@12345`
- Demo Annotator: `exam.annotator.demo@rlhf.dev` / `Demo@12345`

## Seeded Demo Data

Published exams:

- Enterprise Certification - Python Debugging
- Enterprise Certification - Code Review

Review queue contains seeded attempts including:

- `submitted` attempts (unreleased)
- `timed_out` attempts (unreleased)
- one `released` attempt for result-page demo

## Beta Test Checklist

### 1) Authentication + Navigation

- Open `/auth`, login with each role account.
- Verify `/exams` loads and shows published exams.
- Verify unauthenticated access to `/exams` redirects to `/auth`.

### 2) Annotator Flow

Login as `exam.annotator.demo@rlhf.dev`:

- Open `/exams`.
- Start or resume an attempt.
- Save at least one answer.
- Submit exam.
- Confirm result page behavior:
  - released result shows score + notes
  - unreleased result shows pending release message

### 3) Reviewer/Admin Queue Flow

Login as `exam.reviewer.demo@rlhf.dev` (or admin):

- Open `/exams/review`.
- Confirm submitted/timed_out attempts are visible.
- Add reviewer notes and release one attempt.
- Re-open result page for that attempt and confirm released data is visible.

### 4) RBAC Expectations

- Annotator account:
  - can see `/exams`
  - cannot access review queue actions (`/exams/review` restricted)
- Reviewer/Admin accounts:
  - can access and act on `/exams/review`
- Admin account:
  - should have full reviewer capabilities for exam release workflow

## Expected Results

- No blank page on `/exams`.
- Route guards redirect correctly for unauthenticated users.
- Review queue is populated for reviewer/admin users.
- Release action makes result visible to candidate.

## Bug Report Template

When reporting a beta issue, include:

- Role used (annotator/reviewer/admin)
- URL where issue occurred
- Exact action performed
- Expected result vs actual result
- Timestamp (with timezone)
- Screenshot or short screen recording

## Notes for Demo Leads

- If a tester reports stale behavior, ask for:
  - logout/login
  - hard refresh (Ctrl+F5)
- Rotate or remove demo credentials after beta ends.
