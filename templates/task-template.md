# Task Authoring Template

Use this template to create new annotation tasks. Save your tasks as a `.json` file in the `tasks/` folder, then load them into the Annotation Studio.

---

## JSON Schema

Each task file is a JSON array of task objects:

```json
[
  {
    "id": "unique-task-id",
    "type": "comparison | rating | ranking",
    "title": "Short descriptive title",
    "prompt": "The user prompt / question that was asked",
    "guidelines": [
      "Guideline 1 for annotators",
      "Guideline 2 for annotators"
    ],
    "responses": [
      {
        "label": "Response A",
        "model": "Model name (optional)",
        "text": "The full response text (supports Markdown)"
      }
    ],
    "dimensions": [
      {
        "name": "Dimension Name",
        "description": "What this dimension measures",
        "scale": 5
      }
    ]
  }
]
```

---

## Live Hugging Face completions (optional)

When the UI is pointed at a FastAPI server with `HF_API_TOKEN` (or `HF_TOKEN`) set, you can load responses at annotation time instead of embedding `text` in the JSON.

- Add top-level `"inference": { "provider": "hf", "system": "Optional system prompt for the model." }`.
- For each slot in `responses`, use `"text": ""` (or omit). Optional per-slot: `"hf_model": "org/model-id"`, `"temperature"`, `"seed"`.
- If `hf_model` is omitted, the server uses `HF_DEFAULT_MODEL` from `.env`.
- After the first successful run, filled `text` is kept in memory (and may sync to the server with your workspace) so revisiting the task replays the same wording.

See `tasks/hf-live-demo.json` for a minimal example.

---

## Task Types

### Comparison (2 responses, pick the better one)
```json
{
  "id": "my-comparison-1",
  "type": "comparison",
  "title": "My Comparison Task",
  "prompt": "What the user asked...",
  "guidelines": ["Evaluation criteria..."],
  "responses": [
    { "label": "Response A", "model": "GPT-4", "text": "..." },
    { "label": "Response B", "model": "Claude", "text": "..." }
  ],
  "dimensions": [
    { "name": "Accuracy", "description": "Is the information correct?", "scale": 5 },
    { "name": "Clarity", "description": "Is it easy to understand?", "scale": 5 }
  ]
}
```

### Rating (1 response, rate on multiple dimensions)
```json
{
  "id": "my-rating-1",
  "type": "rating",
  "title": "My Rating Task",
  "prompt": "What the user asked...",
  "guidelines": ["Evaluation criteria..."],
  "responses": [
    { "label": "Response", "model": "GPT-4", "text": "..." }
  ],
  "dimensions": [
    { "name": "Overall Quality", "description": "How good is this response?", "scale": 5 }
  ]
}
```

### Ranking (3+ responses, order from best to worst)
```json
{
  "id": "my-ranking-1",
  "type": "ranking",
  "title": "My Ranking Task",
  "prompt": "What the user asked...",
  "guidelines": ["Ranking criteria..."],
  "responses": [
    { "label": "Response A", "model": "Model 1", "text": "..." },
    { "label": "Response B", "model": "Model 2", "text": "..." },
    { "label": "Response C", "model": "Model 3", "text": "..." }
  ],
  "dimensions": [
    { "name": "Quality", "description": "Overall response quality", "scale": 5 }
  ]
}
```

---

## Tips for Writing Good Tasks

1. **Use real-world prompts** — Pull from actual user queries when possible
2. **Include a clear quality gap** — For training, have at least one clearly better and one clearly worse response
3. **Vary the difficulty** — Mix obvious and subtle differences
4. **Write specific guidelines** — Generic guidelines lead to inconsistent annotations
5. **Choose relevant dimensions** — Only include dimensions that matter for this task type
6. **Include code and formatting** — Use Markdown in response text for realistic content
7. **Test your tasks** — Load them in the tool and annotate them yourself before assigning to students

---

## Recommended Dimensions by Domain

### Code Tasks
- Correctness, Security, Readability, Performance, Best Practices

### Writing Tasks
- Prose Quality, Tone, Originality, Grammar, Engagement

### Factual/Knowledge Tasks
- Accuracy, Completeness, Source Quality, Recency, Nuance

### Safety Tasks
- Harm Avoidance, Helpfulness, Honesty, Bias-Free, Appropriate Caveats

### Instruction Following
- Adherence, Format Compliance, Completeness, Relevance
