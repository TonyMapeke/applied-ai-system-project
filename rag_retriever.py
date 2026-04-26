"""
Retrieves relevant pet care facts from pet_care_kb.json given a list of
(Pet, Task) pairs from a generated schedule.
"""
from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Dict, List, Set, Tuple

if TYPE_CHECKING:
    from pawpal_system import Pet, Task

_KB_PATH = os.path.join(os.path.dirname(__file__), "pet_care_kb.json")
_CACHED_KB: Dict | None = None

# Map free-text species entries to KB keys.
_SPECIES_ALIASES: Dict[str, str] = {
    "guinea pig": "guinea_pig",
    "guineapig": "guinea_pig",
    "guinea-pig": "guinea_pig",
}

# Hard cap so the downstream Gemini prompt stays focused.
MAX_FACTS = 15


def _load_kb() -> Dict:
    global _CACHED_KB
    if _CACHED_KB is None:
        with open(_KB_PATH, "r", encoding="utf-8") as fh:
            _CACHED_KB = json.load(fh)
    return _CACHED_KB


def _species_key(species: str) -> str:
    s = species.strip().lower()
    return _SPECIES_ALIASES.get(s, s)


def _category_key(category: str) -> str:
    return category.strip().lower()


def retrieve_facts(pet_task_pairs: List[Tuple["Pet", "Task"]]) -> List[str]:
    """Return deduplicated care facts relevant to the given (Pet, Task) pairs.

    Lookup order per pair:
      1. kb[species][category]  — most specific, added first
      2. kb[species]["general"] — appended once per new species seen

    Returns at most MAX_FACTS entries so the AI prompt stays concise.
    Unknown species or categories produce no facts rather than an error.
    """
    kb = _load_kb()
    seen_facts: Set[str] = set()
    seen_species: Set[str] = set()
    facts: List[str] = []

    def _add(candidates: List[str]) -> None:
        for fact in candidates:
            if fact not in seen_facts and len(facts) < MAX_FACTS:
                seen_facts.add(fact)
                facts.append(fact)

    for pet, task in pet_task_pairs:
        sp = _species_key(pet.species)
        cat = _category_key(task.category)
        species_data = kb.get(sp, {})

        # Category-specific facts are most relevant — add these first.
        _add(species_data.get(cat, []))

        # General species facts, but only once per species to avoid repetition.
        if sp not in seen_species:
            seen_species.add(sp)
            _add(species_data.get("general", []))

    return facts


def supported_species() -> List[str]:
    """Return the list of species keys present in the knowledge base."""
    return list(_load_kb().keys())


def supported_categories(species: str) -> List[str]:
    """Return the category keys available for a given species."""
    kb = _load_kb()
    return list(kb.get(_species_key(species), {}).keys())
