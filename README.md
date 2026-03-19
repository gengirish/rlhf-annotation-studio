# RLHF Annotation Studio

A lightweight, Markdown-based annotation kit for practicing Reinforcement Learning from Human Feedback (RLHF) workflows. Designed to give students hands-on experience with the same annotation patterns used at Scale AI, Surge AI, and similar data labeling platforms.

**Zero dependencies. No server. Just open the HTML file.**

---

## Quick Start

1. Open `annotation-tool.html` in any modern browser
2. Click **"Try Demo Tasks"** to load 5 built-in practice tasks
3. Annotate each task: read the prompt, evaluate responses, rate dimensions, write justifications
4. Click **Export** to download your annotations as Markdown

---

## What's Included

```
RLHF/
├── annotation-tool.html              ← Main annotation interface (open in browser)
├── tasks/
│   ├── code-review-comparisons.json  ← Code review annotation tasks
│   └── safety-alignment.json         ← Safety & alignment evaluation tasks
├── guidelines/
│   ├── comparison-rubric.md          ← How to annotate comparison tasks
│   ├── rating-rubric.md              ← How to annotate rating tasks
│   ├── ranking-rubric.md             ← How to annotate ranking tasks
│   └── safety-guidelines.md          ← Safety & bias evaluation criteria
├── templates/
│   ├── task-template.md              ← JSON schema for creating new tasks
│   └── annotation-export-example.md  ← Example of what exported annotations look like
├── exports/                          ← Save your exported annotations here
└── README.md
```

---

## Task Types

The tool supports three annotation task types that mirror real RLHF workflows:

### Comparison (A/B Testing)
- View two AI responses side-by-side
- Select which response is better (or mark as a tie)
- Rate both on multiple quality dimensions
- Most common task type in RLHF pipelines

### Rating (Absolute Scoring)
- Evaluate a single AI response
- Score it on defined quality dimensions (1–5 Likert scale)
- Used for reward model training data

### Ranking (Ordered Preference)
- View three or more responses
- Drag/reorder them from best to worst
- Used for preference-based training (DPO, RLHF)

---

## Creating Your Own Tasks

1. Read `templates/task-template.md` for the JSON schema
2. Create a new `.json` file in the `tasks/` folder
3. Load it into the annotation tool via the **"Upload JSON"** button in the sidebar

Minimal example:

```json
[
  {
    "id": "my-task-1",
    "type": "comparison",
    "title": "My First Task",
    "prompt": "What is the capital of France?",
    "responses": [
      { "label": "Response A", "model": "Model 1", "text": "Paris is the capital of France." },
      { "label": "Response B", "model": "Model 2", "text": "The capital is Lyon, a major city in France." }
    ],
    "dimensions": [
      { "name": "Accuracy", "description": "Is the answer correct?", "scale": 5 }
    ]
  }
]
```

---

## Features

- **Side-by-side response comparison** with click-to-select preference
- **Multi-dimensional Likert ratings** (1–5 scale per dimension)
- **Drag-to-rank interface** for ordering multiple responses
- **Task queue sidebar** with progress tracking and session stats
- **Built-in annotation guidelines** toggle per task
- **Session timer** and per-task time tracking
- **Markdown rendering** in prompts and responses (code blocks, bold, italic, headers)
- **Keyboard shortcuts**: arrow keys to navigate, number keys for quick preference selection
- **Export to Markdown** — copy to clipboard or download as `.md` file
- **Validation** — prevents submission without complete ratings and justification
- **100% client-side** — no data leaves your browser

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `←` / `p` | Previous task |
| `→` / `n` | Next task |
| `1` | Select Response A (comparison tasks) |
| `2` | Select Response B (comparison tasks) |
| `3` | Select Tie (comparison tasks) |

---

## Reading the Guidelines

Before annotating, read the relevant rubric in the `guidelines/` folder:

- **comparison-rubric.md** — How to evaluate A vs B tasks, rating scale definitions, writing good justifications
- **rating-rubric.md** — How to score individual responses, calibration tips
- **ranking-rubric.md** — How to order multiple responses, handling close calls
- **safety-guidelines.md** — The Three H's framework (Helpful, Harmless, Honest), bias checklist, red flags

---

## For Instructors

### Setting Up a Class Exercise

1. Create task files targeting your learning objectives
2. Distribute this folder to students (zip, git, or LMS upload)
3. Students open `annotation-tool.html`, load the task file, and annotate
4. Students export their annotations as Markdown and submit
5. Review submissions — the structured Markdown format makes comparison easy

### Assessment Ideas

- Compare student annotations to a "gold standard" annotation set
- Measure inter-annotator agreement across the class
- Have students create their own task sets and swap with peers
- Discuss disagreements as a class to build calibration

### Suggested Exercises

| Exercise | Task File | Focus |
|----------|-----------|-------|
| Code Review Quality | `code-review-comparisons.json` | Evaluating technical accuracy and completeness |
| Safety & Alignment | `safety-alignment.json` | Detecting bias, evaluating refusals, harm avoidance |
| Built-in Demo | (click "Try Demo Tasks") | General RLHF annotation practice |

---

## How This Relates to Real RLHF

This annotation kit simulates the human feedback collection phase of the RLHF pipeline:

```
Prompt → LLM generates responses → Humans annotate preferences → Train reward model → RL fine-tuning
                                    ^^^^^^^^^^^^^^^^^^^^^^^^
                                    (this is what you're practicing)
```

In production RLHF systems (like those at OpenAI, Anthropic, and Google), human annotators perform thousands of these comparisons and ratings. The quality of this human feedback directly determines the quality of the resulting model. Practicing annotation helps you understand:

- Why annotation guidelines and calibration matter
- How subtle differences in evaluation criteria change outcomes
- The difficulty of maintaining consistency across many tasks
- How bias in annotation can propagate to model behavior

---

## Browser Support

Works in any modern browser: Chrome, Firefox, Edge, Safari. No installation or build step required.
