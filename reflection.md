# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
The initial UML design for PawPal+ follows a composition-based structure. The system centers on a Pet object that can be assigned Task objects. A dedicated Scheduler class acts as the engine.
- What classes did you include, and what responsibilities did you assign to each?
Pet: The pet identity that maintains the required care activities
Task: Defines a care activity including priority, descriptipon, time limit, etc
Scheduler: Filters and sorts the tasks 
DailyPlanner: Formats the final list of tasks and explains reasoning


**b. Design changes**

- Did your design change during implementation?
No
- If yes, describe at least one change and why you made it.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?

- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
The system uses a budget-based packer to fit tasks into a time window based on priority, while a separate interval-based checker flags overlaps using actual clock times. Because these two logic paths are independent, a task might fit within your total time budget but still trigger a conflict warning if the specific start times you entered overlap.
- Why is that tradeoff reasonable for this scenario?
It balances a lightweight greedy algorithm with essential data validation

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?

I used AI tools at several stages: brainstorming the class structure during initial design, getting a second opinion on the conflict detection algorithm, debugging edge cases in the recurrence logic, and refining the RAG prompt to produce more grounded explanations. The most useful prompts were specific and gave context — for example, "I have a scheduler that packs tasks greedily by priority density. How should I handle the constraint that walk/groom tasks across different pets can't overlap if there's only one owner?" yielded a much more useful answer than asking broadly about scheduling algorithms.

- What kinds of prompts or questions were most helpful?

Specific, constrained questions worked best. Asking "what's wrong with this function" with the code pasted produced better results than asking "how do I write a scheduler." Asking the AI to explain its reasoning — not just give an answer — also helped me decide whether to trust the suggestion.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.

When designing the walk/groom exclusivity constraint, the AI suggested adding a boolean flag to each `Task` called something like `requires_exclusive_owner`. This sounded tidy, but it was wrong for the domain. The constraint isn't about a task being exclusive in isolation — it's about whether *two tasks for different pets* overlap in the same owner time slot. A walk for one dog doesn't conflict with another walk for the same dog (if scheduled sequentially), but it does conflict with a walk for a second dog at the same time. The flag approach couldn't express that distinction at all.

- How did you evaluate or verify what the AI suggested?

I traced through the logic manually using a concrete example: one owner, two dogs, two simultaneous walks. The flag approach would have allowed that, which is physically impossible. Once I explained the owner-as-shared-resource model, the AI revised its suggestion to track committed owner time ranges across all pets — which is the approach now implemented in `_find_earliest_safe_start()`.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?

The test suite covers: chronological task sorting, daily and weekly recurrence (correct `due_date` advancement via `timedelta`), one-off task completion returning `None`, `ValueError` when completing a task that belongs to a different pet, time-window conflict detection, no false positives for tasks on different calendar days, walk/groom exclusivity enforcement in `generate_plan()`, priority-density packing order, filtering by pet name / category / completion status, and conflict warnings surfacing in the final plan output.

- Why were these tests important?

The scheduling logic is the core value of the system. If recurrence is off by a day, or conflict detection has a false negative, or the packer ignores priority, the app produces plans that look valid but aren't. Because this logic lives in pure Python classes with no UI or network dependencies, every behavior can be verified in isolation — so bugs are caught immediately rather than discovered by a frustrated user.

**b. Confidence**

- How confident are you that your scheduler works correctly?

27 of 27 tests pass. The behaviors I'm most confident in are the ones with the most direct real-world consequence: recurrence (tested for Daily, Weekly, and None frequencies), conflict detection (tested for overlap and non-overlap across days), and walk/groom exclusivity (tested for both the constraint enforcement and the conflict reporter). I'm moderately confident in the priority packing, since the greedy algorithm has deterministic behavior but could produce surprising results when many tasks tie on priority density.

- What edge cases would you test next if you had more time?

A pet with zero tasks (empty list through the full pipeline), all tasks tied on priority (deterministic but arbitrary tie-breaking), a time budget of zero, the RAG retriever receiving a species not in the knowledge base, and AI explanation behavior when the retrieved facts list is empty.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

The separation between the scheduling engine and the UI. `pawpal_system.py` has zero Streamlit imports, which meant I could write all 27 unit tests against pure Python, and adding the RAG and AI layers later required no changes to the scheduling logic. The architecture paid off exactly when it was supposed to.

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

I'd add persistent storage so plans survive a browser refresh, and I'd expand the knowledge base to cover more species — the JSON structure makes that extension straightforward but I ran out of time. I'd also version the Gemini prompt and treat it as a testable artifact rather than an internal string, since small wording changes produce meaningfully different output quality.

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

The hardest part of building an AI-assisted product isn't calling the API — it's everything around it. Structuring clean domain logic, deciding what belongs in a retrieval layer versus a model, building graceful fallbacks, and logging failures so they're visible: these are what separate a reliable system from one that only works in a demo. I also learned that AI output quality is a function of prompt design, and prompts should be treated with the same rigor as code — reviewed, iterated on, and tested against concrete examples.

---

## 6. Responsible AI

**a. Limitations and biases**

The knowledge base has uneven coverage: dogs and cats have detailed entries across multiple care categories, while rabbits, guinea pigs, and other small animals have thinner data. A rabbit owner gets a less specific — and potentially less accurate — AI explanation than a dog owner. This isn't a model bias; it's a data gap that's invisible to users who don't already know their species is underrepresented.

The guidelines in `pet_care_kb.json` reflect one author's reading of general pet care resources. Veterinary recommendations vary by region, breed, age, and health status, and the system has no way to detect that a guideline appropriate for a healthy adult dog is wrong for a senior dog with joint problems. Priority scores are also fully user-driven — the scheduler trusts whatever numbers the owner enters, so a user who undervalues medication tasks will get a plan that reflects their inputs, not what's medically correct.

**b. Could this system be misused?**

The most realistic risk is over-reliance: a user treating the AI's explanation as veterinary advice rather than a scheduling aid. The model generates confident-sounding paragraphs, and users may not distinguish between "this task is scheduled first because of its priority score" and "this is medically the right approach for your animal."

Mitigations already in place: the prompt instructs Gemini to explain scheduling decisions, not prescribe treatment; the fallback explanation avoids medical-sounding language; and `logger.error` captures every API failure before returning the safe fallback.

What I'd add before wider deployment: a visible disclaimer on every AI explanation ("This is a scheduling suggestion, not veterinary advice"), prompt guardrails that prevent the model from recommending dosages or contradicting a vet's instructions, and a special prompt tone for `medication` category tasks that emphasizes consulting a professional.

**c. What surprised me while testing reliability**

The most surprising finding was how silently the AI's output degraded when a task's category didn't match any key in the knowledge base. The model didn't refuse or signal uncertainty — it produced fluent, confident-sounding text that was noticeably more generic and occasionally less accurate. Without the `(none found)` log entry, this failure mode would be completely invisible to a user.

The second surprise was how much small prompt wording changes affected output quality. Changing "explain the schedule" to "explain *why* the schedule is well-suited to their pets, citing specific guidelines" produced dramatically more grounded and task-specific output. Prompt wording is a reliability concern, not just a stylistic one.
