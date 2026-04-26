# Model Card — PawPal+

This model card documents the AI component of PawPal+, an AI-powered pet care scheduling assistant. It answers reflection prompts on AI collaboration, system biases, and testing results for portfolio and academic review purposes.

---

## 1. Model Details

| Field | Value |
|---|---|
| Model used | Google Gemini 2.5 Flash Lite (`gemini-2.5-flash-lite`) |
| Access method | Google Generative AI Python SDK (`google-genai`) |
| Role in system | Generates a natural-language explanation of the AI-produced daily care plan |
| Retrieval layer | Custom RAG over `pet_care_kb.json` — up to 15 expert guidelines injected per prompt |
| Fallback | Rule-based explanation from `Scheduler._build_explanation()` if API is unavailable |

---

## 2. Intended Use

**Primary use case:** Help busy pet owners understand *why* their daily care schedule is structured the way it is — grounded in expert pet care guidelines, not generic AI output.

**Intended users:** Individual pet owners managing multiple animals with competing care demands.

**Out-of-scope uses:**
- Diagnosing illness or symptoms
- Recommending medication dosages
- Replacing professional veterinary advice
- Managing care for animals with complex or active medical conditions

---

## 3. AI Collaboration During Development

### How AI tools were used

AI assistants (including Claude) were used at multiple stages:

- **Design brainstorming** — sketching the class structure and discussing where the AI layer should live relative to the scheduling engine
- **Algorithm design** — working through the conflict detection and walk/groom exclusivity logic
- **Debugging** — tracing edge cases in the recurrence logic (Daily vs. Weekly vs. None frequencies)
- **Prompt refinement** — iterating on the Gemini prompt to produce more grounded, task-specific output

The most effective prompts were specific and included context: *"I have a greedy scheduler that packs tasks by priority density. How should I handle the constraint that walk/groom tasks for different pets can't overlap when there's only one owner?"* produced a useful answer. Broad questions like *"how do I write a scheduler?"* did not.

### One helpful AI suggestion

When designing conflict detection, an AI assistant suggested modeling task time windows as half-open intervals `[start, end)` and using the condition `max(start_a, start_b) < min(end_a, end_b)` to detect overlap. This was cleaner and more mathematically sound than the boundary comparison I had started writing. I adopted it directly — it is now the core of `Scheduler.check_for_conflicts()` and made the test cases easy to reason about.

### One flawed AI suggestion (and how I caught it)

When designing walk/groom exclusivity, the AI suggested adding a boolean flag to each `Task` — something like `requires_exclusive_owner = True` — and filtering on that flag during scheduling. This sounded clean but was wrong for the domain.

The constraint isn't about a task being exclusive in isolation. It's about whether two tasks for *different pets* overlap in the same owner time slot. A walk for one dog doesn't conflict with another walk for the same dog scheduled sequentially — but it does conflict with a simultaneous walk for a second dog, because there is one owner. The flag approach cannot express that distinction at all.

I caught this by tracing through a concrete example: one owner, two dogs, two walks at the same time. The flag approach would have allowed the plan, which is physically impossible. I pushed back, explained the owner-as-shared-resource model, and the AI revised its suggestion to tracking committed owner time ranges across all pets. That is what `_find_earliest_safe_start()` now implements.

**Lesson:** AI suggestions require domain validation, not just syntactic review. A suggestion can be logically coherent and still be wrong for the specific real-world constraints of your problem.

---

## 4. Training Data and Knowledge Base

The Gemini model itself was trained by Google on a broad corpus; its training data is not inspectable or auditable by this project.

The `pet_care_kb.json` knowledge base — which grounds every AI explanation — was authored by the project developer drawing on general pet care resources. It is the primary controllable data layer. Its properties:

- **Coverage:** Detailed entries for dogs and cats across exercise, feeding, grooming, medication, and enrichment categories. Thinner coverage for rabbits, guinea pigs, and other small animals.
- **Author perspective:** Single author; guidelines reflect general healthy-adult-animal recommendations.
- **No versioning or sourcing:** Guidelines are not attributed to specific veterinary sources or review dates.

---

## 5. Limitations and Biases

### Knowledge base gaps
Species with thin or absent knowledge base coverage receive more generic AI explanations. This is a data gap, not a model bias, but it is invisible to users who don't already know their species is underrepresented.

### Guidelines assume a healthy adult animal
The knowledge base does not account for age, breed, weight, or medical history. A guideline appropriate for a healthy adult Labrador may be wrong for a senior dog with heart disease. The system has no mechanism to detect this mismatch.

### Priority scores are user-controlled
The scheduler trusts the priority numbers the owner enters. A user who undervalues medication tasks gets a plan that reflects their inputs, not what is medically optimal. The system cannot override or question user judgments.

### No longitudinal awareness
The app holds all state in Streamlit session storage, which resets on browser refresh. There is no history, no trend detection, and no way to surface patterns like "this pet has missed its medication three days in a row."

### Silent degradation
When a scheduled task's category or species has no matching entry in the knowledge base, the AI produces fluent but generic output without flagging the gap. The degradation is only visible in the server logs (`(none found)` entry), not to the user.

---

## 6. Misuse Risks and Mitigations

**Primary risk: over-reliance**
A user may treat the AI's explanation as veterinary advice rather than a scheduling aid. The model generates confident-sounding paragraphs; users may not distinguish between "this task is scheduled first because of priority score" and "this is the medically correct approach for your animal."

**Mitigations already in place:**
- Prompt instructs Gemini to explain scheduling decisions, not prescribe treatment
- Fallback explanation (rule-based) avoids medical-sounding language
- `logger.warning` and `logger.error` capture every API failure before the safe fallback is returned

**Recommended additions before wider deployment:**
- Visible disclaimer on every AI explanation: *"This is a scheduling suggestion, not veterinary advice. Consult your vet for medical decisions."*
- Prompt guardrails that explicitly prevent the model from recommending dosages or contradicting a vet's instructions
- Special prompt tone for `medication` category tasks that emphasizes professional consultation
- Input validation to flag suspiciously high medication doses or frequencies entered by users

---

## 7. Testing Results

**Automated test suite: 27 of 27 tests passed** (run time: 0.06s)

```
$ python -m pytest tests/ -v
27 passed in 0.06s
```

### Behaviors verified

| Behavior | Result |
|---|---|
| Chronological sort by `HH:MM` string | PASS |
| Daily recurrence advances `due_date` by 1 day | PASS |
| Weekly recurrence advances `due_date` by 7 days | PASS |
| One-off task returns `None` on completion | PASS |
| Completing a foreign task raises `ValueError` | PASS |
| Overlapping time windows generate a conflict warning | PASS |
| Tasks on different days are not flagged as conflicts | PASS |
| Walk/groom exclusivity enforced across pets | PASS |
| Priority-density packing: high-value short tasks scheduled first | PASS |
| Completed recurring tasks remain eligible for scheduling | PASS |
| Completed non-recurring tasks excluded from plan | PASS |
| Filtering by pet name, category, and completion status | PASS |

### AI-specific reliability observations

The automated tests cover the scheduling engine only, not the AI explanation layer (which requires a live API key and is non-deterministic). AI reliability was assessed through manual review of outputs across several scenarios:

- **With full RAG facts:** Explanations were specific, cited relevant guidelines, and accurately reflected the scheduled tasks.
- **With partial RAG facts:** Explanations remained coherent but became less task-specific as fewer retrieved guidelines were available.
- **With no RAG facts (unknown species/category):** Explanations became noticeably generic. The model did not signal uncertainty — it produced confident-sounding output that was less accurate. This was the most significant reliability finding.
- **With API unavailable:** The fallback explanation appeared correctly; no crash or user-visible error.

**Confidence level:** High for the scheduling engine (27/27 tests, deterministic logic). Moderate for AI explanation quality (non-deterministic, dependent on retrieval coverage and prompt stability).

---

## 8. What Surprised Me

Two things during testing were unexpected:

1. **Silent AI degradation.** When retrieval returned nothing, the model didn't hedge or flag uncertainty — it just became less accurate while staying just as confident in tone. A user with an unusual pet species would have no way to know their explanation was less grounded than a dog owner's.

2. **Prompt sensitivity.** Small wording changes in the Gemini prompt produced meaningfully different output quality. Changing "explain the schedule" to "explain *why* the schedule is well-suited to their pets, citing specific guidelines" produced dramatically more grounded output. This reinforced that prompt wording is a reliability concern, not just a style preference — it should be versioned and tested like code.

---

## 9. What I Would Do Differently

- **Expand the knowledge base** to cover more species with the same depth as dogs and cats
- **Version and test the prompt** as a formal artifact, with documented expected outputs for key scenarios
- **Add a disclaimer layer** in the UI that makes the system's limitations visible to users
- **Persist state** across sessions so the system could detect care gaps over time
- **Source and date the guidelines** in `pet_care_kb.json` so they can be audited and updated as veterinary guidance evolves
