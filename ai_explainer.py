"""
Calls the Gemini API to generate a RAG-grounded schedule explanation.
Retrieved care facts are injected into the prompt so the AI's response
is shaped by the knowledge base, not just generic pet advice.
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, List

from google import genai
from dotenv import load_dotenv

if TYPE_CHECKING:
    from pawpal_system import DailyPlan, Owner

load_dotenv()

logger = logging.getLogger(__name__)

_MODEL = "gemini-2.5-flash-lite"
_client: genai.Client | None = None


def _get_client() -> genai.Client | None:
    global _client
    if _client is not None:
        return _client
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("GEMINI_API_KEY not set — AI explanation unavailable.")
        return None
    _client = genai.Client(api_key=api_key)
    return _client


def _build_prompt(
    plan: "DailyPlan",
    owner: "Owner",
    available_time: int,
    retrieved_facts: List[str],
) -> str:
    lines: List[str] = []

    lines.append("You are a knowledgeable and friendly pet care assistant.")
    lines.append(
        "Using ONLY the expert care guidelines provided below, write a warm 3–4 sentence "
        "explanation for the owner about why today's schedule is well-suited to their pets. "
        "Cite specific guidelines where they apply. Be specific to the pets and tasks shown — "
        "do not give generic advice that ignores the guidelines."
    )

    lines.append("")
    if retrieved_facts:
        lines.append("RELEVANT CARE GUIDELINES (retrieved from knowledge base):")
        for fact in retrieved_facts:
            lines.append(f"  - {fact}")
    else:
        lines.append("RELEVANT CARE GUIDELINES: (none found for these species/categories)")
    lines.append("")

    lines.append("TODAY'S SCHEDULED TASKS:")
    if plan.scheduled_slots:
        slot_map = {id(t): (p, s, e) for p, t, s, e in plan.scheduled_slots}
        for task in plan.selected_tasks:
            pet, start, end = slot_map[id(task)]
            lines.append(
                f"  - {pet.name} ({pet.species}): \"{task.description}\" | "
                f"{task.duration_mins} min | category: {task.category} | "
                f"priority: {task.priority}/9 | window: {start}–{end} min"
            )
    else:
        lines.append("  (no tasks were scheduled in this window)")
    lines.append("")

    pet_summary = ", ".join(f"{p.name} ({p.species})" for p in owner.pets)
    lines.append(f"Household pets: {pet_summary}")
    lines.append(
        f"Time budget: {plan.total_duration} min scheduled out of {available_time} min available."
    )
    lines.append("")
    lines.append(
        "Write the explanation now. 3–4 sentences. Address the owner directly using 'your'. "
        "No bullet points. No headings."
    )

    return "\n".join(lines)


def generate_explanation(
    plan: "DailyPlan",
    owner: "Owner",
    available_time: int,
    retrieved_facts: List[str],
) -> str:
    """Return a Gemini-generated explanation grounded in retrieved care facts.

    Falls back to plan.explanation if the API key is missing or the call fails,
    so the app always has something to display.
    """
    client = _get_client()
    if client is None:
        return plan.explanation

    prompt = _build_prompt(plan, owner, available_time, retrieved_facts)

    try:
        response = client.models.generate_content(model=_MODEL, contents=prompt)
        return response.text.strip()
    except Exception as exc:
        logger.error("Gemini call failed: %s", exc)
        return plan.explanation
