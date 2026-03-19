# Comparison Task Rubric

## Overview

In **comparison tasks**, you are shown a user prompt and two (or more) AI-generated responses. Your job is to determine which response is better and rate each on multiple quality dimensions.

---

## Step-by-Step Process

1. **Read the prompt carefully** — Understand exactly what the user is asking for.
2. **Read both responses fully** — Don't stop at the first difference. Read each response completely before judging.
3. **Check for correctness** — Are there factual errors, bugs in code, or logical mistakes?
4. **Compare on each dimension** — Rate each dimension independently. A response can be great on clarity but poor on completeness.
5. **Select your preference** — Choose the response that is better *overall*, considering all dimensions.
6. **Write your justification** — Explain *why* you chose one over the other with specific references.

---

## Rating Scale (1–5)

| Score | Label       | Meaning |
|-------|-------------|---------|
| 1     | Very Poor   | Fundamentally wrong, harmful, or completely misses the point |
| 2     | Poor        | Major issues that significantly hurt quality |
| 3     | Acceptable  | Adequate but with notable room for improvement |
| 4     | Good        | Minor issues only; solid overall quality |
| 5     | Excellent   | No meaningful issues; exemplary response |

---

## Common Dimensions

### Accuracy
- Are facts, code, and claims correct?
- Are there subtle errors (off-by-one, wrong API usage, outdated information)?
- Is the response misleading even if technically correct?

### Clarity
- Can the target audience understand this on first read?
- Is it well-organized with logical flow?
- Does it use appropriate formatting (headers, lists, code blocks)?

### Completeness
- Does it address all parts of the question?
- Are important caveats or edge cases mentioned?
- Is it thorough without being unnecessarily verbose?

### Helpfulness
- Would this response actually help the user accomplish their goal?
- Does it anticipate follow-up questions?
- Is it actionable rather than just theoretical?

---

## Common Pitfalls to Avoid

- **Length bias** — Longer is not always better. A concise, correct response can beat a verbose, rambling one.
- **Style bias** — Don't favor responses just because they use markdown formatting or emoji. Focus on substance.
- **Anchoring** — Don't let your first impression dominate. Re-evaluate after reading both fully.
- **Halo effect** — A response with one excellent quality isn't automatically good in all dimensions.

---

## Writing Good Justifications

### Good justification example:
> "Response A is preferred because it correctly identifies the SQL injection vulnerability (which Response B misses entirely) and provides a parameterized query fix. While Response B has cleaner formatting, its suggested fix uses a bare except clause, which masks errors — a practice that would fail code review."

### Poor justification example:
> "A is better because it's more detailed."

A good justification:
- References **specific content** from the responses
- Explains the **reasoning** behind your preference
- Notes **trade-offs** (where the other response was better)
- Is at least 2–3 sentences
