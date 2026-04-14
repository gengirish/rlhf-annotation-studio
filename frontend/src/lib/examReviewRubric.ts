/** Mirrors backend `app/exam_rubric.EXAM_REVIEW_RUBRIC_CRITERIA`. */
export const EXAM_REVIEW_RUBRIC_CRITERIA = [
  {
    id: "root_cause_identification",
    title: "Root Cause Identification",
    description:
      "Does it correctly identify reference vs value comparison as the root cause?"
  },
  {
    id: "explanation_depth",
    title: "Explanation Depth",
    description:
      "Does it explain String interning, heap allocation, and why == works with literals?"
  },
  {
    id: "fix_correctness",
    title: "Fix Correctness",
    description:
      "Is the fix correct, robust, and does it solve the general problem (not just this test case)?"
  },
  {
    id: "null_safety",
    title: "Null Safety",
    description:
      "Does it address potential NullPointerException when calling .equals() on a possibly null reference?"
  },
  {
    id: "educational_value",
    title: "Educational Value",
    description: "Would this help a developer avoid == for objects in all future code?"
  }
] as const;

export type RubricCriterionId = (typeof EXAM_REVIEW_RUBRIC_CRITERIA)[number]["id"];
