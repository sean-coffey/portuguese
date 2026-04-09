from collections import defaultdict
import json
from pathlib import Path

from openai import OpenAI

from app.draft_models import LearnerProfile
from app.models import PhraseItem, QuestionOutput

client = OpenAI()

BASE_DIR = Path(__file__).resolve().parent

with open(BASE_DIR / "question_rules.json", "r", encoding="utf-8") as f:
    QUESTION_RULES = json.load(f)

with open(BASE_DIR / "question_templates.json", "r", encoding="utf-8") as f:
    QUESTION_TEMPLATES = json.load(f)

with open(BASE_DIR / "question_families.json", "r", encoding="utf-8") as f:
    QUESTION_FAMILIES = json.load(f)

QUESTION_MODE_FALLBACKS = {
    "grammar": ["grammar", "vocabulary", "production"],
    "vocabulary": ["vocabulary", "production"],
    "comprehension": ["comprehension", "production", "vocabulary"],
    "production": ["production"],
}

FAMILIES_BY_MODE = {}

for family_key, meta in QUESTION_FAMILIES.items():
    mode = meta.get("question_mode")
    if not mode:
        continue

    if isinstance(mode, list):
        for mode_name in mode:
            FAMILIES_BY_MODE.setdefault(mode_name, set()).add(family_key)
    else:
        FAMILIES_BY_MODE.setdefault(mode, set()).add(family_key)


def _get_families_for_mode(question_mode: str) -> set[str]:
    return FAMILIES_BY_MODE.get(question_mode, set())

def _get_family_meta(exercise_family: str) -> dict:
    return QUESTION_FAMILIES.get(exercise_family, {})


def _family_is_llm_backed(exercise_family: str) -> bool:
    return bool(_get_family_meta(exercise_family).get("llm_backed", False))


def _get_llm_strategy(exercise_family: str) -> str | None:
    return _get_family_meta(exercise_family).get("llm_strategy")


class QuestionBatchContext:
    def __init__(self):
        self.family_counts = defaultdict(int)

    def choose_least_used(self, families: list[str]) -> str:
        families = sorted(families, key=lambda f: (self.family_counts[f], f))
        chosen = families[0]
        self.family_counts[chosen] += 1
        return chosen


def _pick_keyword(item: PhraseItem) -> str:
    if item.keyword_pt:
        return item.keyword_pt

    words = item.normalized.replace(".", "").replace("!", "").replace("?", "").split()
    return words[-1] if words else item.normalized


def _pick_focus_phrase(item: PhraseItem) -> str:
    return item.focus_phrase_pt or item.normalized


def _main_verb_infinitive(item: PhraseItem) -> str | None:
    return item.main_verb_infinitive_pt or item.verb_pt


def _main_verb_surface(item: PhraseItem) -> str | None:
    return item.main_verb_surface_pt or item.verb_pt


def _subject(item: PhraseItem) -> str | None:
    return item.subject_pt


def _learner_descriptor(learner_profile: LearnerProfile) -> str:
    level = learner_profile.cefr_level
    age_min = learner_profile.age_min
    age_max = learner_profile.age_max

    if age_min and age_max:
        return f"{level}, {age_min}-{age_max} years old"
    if age_min:
        return f"{level}, {age_min}+ years old"
    return level


def learner_is_younger(learner_profile: LearnerProfile) -> bool:
    return learner_profile.age_max is not None and learner_profile.age_max <= 10


def simplify_instruction(text: str, learner_profile: LearnerProfile) -> str:
    if learner_is_younger(learner_profile):
        replacements = {
            "utilizar": "usar",
            "reescreve": "escreve de novo",
            "adapta o verbo": "muda o verbo"
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
    return text


def _classify_item(item: PhraseItem) -> str:
    if item.input_type == "word":
        lexical = (item.lexical_type or "other").lower()
        if lexical in {"noun", "adjective", "verb"}:
            return lexical
        return "other"

    visual = item.visual_type or "literal_visual"

    if visual in {"literal_visual", "literal_but_ambiguous"}:
        return "literal"
    if visual == "idiomatic":
        return "idiom"
    return "non_visual"


def _get_rule_entry(category: str) -> dict:
    return QUESTION_RULES.get(category, {})


def _family_is_structurally_valid(item: PhraseItem, family: str) -> bool:
    if family == "sem_pergunta":
        return True

    if family == "identify_verb":
        return bool(_main_verb_surface(item)) or (
            item.input_type == "word" and item.lexical_type == "verb"
        )

    if family in {"reuse_verb", "complete_conjugation"}:
        return bool(_main_verb_infinitive(item))

    if family == "change_subject":
        return bool(_subject(item)) and item.input_type in {"phrase", "sentence"}

    if family == "rewrite_plural":
        return bool(_subject(item)) and item.number_pt == "singular" and item.input_type in {"phrase", "sentence"}

    if family in {"meaning", "use_in_sentence", "write_one_sentence", "describe_freely"}:
        return True

    if family in {"find_word", "what_happens", "who_is_there", "what_do_you_see", "describe_two_sentences"}:
        return item.input_type in {"phrase", "sentence"}

    return True


def _filter_families_by_structure(item: PhraseItem, families: list[str]) -> list[str]:
    return [family for family in families if _family_is_structurally_valid(item, family)]

def _get_families_for_mode(question_mode: str) -> set[str]:
    return FAMILIES_BY_MODE.get(question_mode, set())

def _get_candidate_families(
    item: PhraseItem,
    learner_profile: LearnerProfile,
    question_mode: str,
) -> tuple[list[str], list[str]]:
    category = _classify_item(item)
    rule = _get_rule_entry(category)

    allowed = rule.get("allowed_families", [])
    preferred = rule.get("cefr_preferred_families", {}).get(
        learner_profile.cefr_level,
        rule.get("preferred_families", [])
    )

    allowed_for_mode = _get_families_for_mode(question_mode)

    allowed = [f for f in allowed if f in allowed_for_mode]
    preferred = [f for f in preferred if f in allowed_for_mode]

    allowed = _filter_families_by_structure(item, allowed)
    preferred = _filter_families_by_structure(item, preferred)

    return preferred, allowed

def _get_mode_families_for_item(
    item: PhraseItem,
    learner_profile: LearnerProfile,
    question_mode: str,
) -> tuple[list[str], list[str]]:
    preferred, allowed = _get_candidate_families(
        item=item,
        learner_profile=learner_profile,
        question_mode=question_mode
    )
    return preferred, allowed


def _choose_exercise_family(
    item: PhraseItem,
    question_mode: str,
    learner_profile: LearnerProfile,
    batch_context: QuestionBatchContext | None = None
) -> str:
    modes_to_try = QUESTION_MODE_FALLBACKS.get(question_mode, [question_mode])

    for mode in modes_to_try:
        preferred, allowed = _get_mode_families_for_item(
            item=item,
            learner_profile=learner_profile,
            question_mode=mode,
        )

        candidates = preferred or allowed

        if candidates:
            if batch_context:
                return batch_context.choose_least_used(candidates)
            return candidates[0]

    return ""

def _build_template_question_for_family(
    item: PhraseItem,
    exercise_family: str,
    learner_profile: LearnerProfile,
) -> tuple[str, str | None]:
    if exercise_family == "identify_verb":
        if item.input_type == "word" and item.lexical_type == "verb":
            template = _pick_template("identify_verb", "word_verb", item.id)
        else:
            template = _pick_template("identify_verb", "default", item.id)

        question = _render_template(template, item)
        return simplify_instruction(question, learner_profile), _main_verb_surface(item)

    if exercise_family in QUESTION_TEMPLATES:
        template = _pick_template(exercise_family, "default", item.id)
        question = _render_template(template, item)

        answer = None
        if exercise_family == "meaning":
            answer = item.gloss_en
        elif exercise_family == "find_word":
            answer = _pick_focus_phrase(item)
        elif exercise_family == "what_happens":
            answer = item.scene.action if item.scene else None
        elif exercise_family == "who_is_there":
            answer = item.scene.subject if item.scene else None

        return simplify_instruction(question, learner_profile), answer

    return "", None

def _build_llm_question_for_family(
    item: PhraseItem,
    exercise_family: str,
    learner_profile: LearnerProfile,
) -> tuple[str, str | None]:
    strategy = _get_llm_strategy(exercise_family)

    if strategy == "reuse_verb":
        return _build_reuse_verb_question_llm(item, learner_profile)

    if strategy == "complete_conjugation":
        return _build_complete_conjugation_question_llm(item, learner_profile)

    return "", None


def _pick_template(family: str, template_key: str, item_id: str) -> str:
    templates = QUESTION_TEMPLATES.get(family, {}).get(template_key, [])
    if not templates:
        return ""
    return templates[abs(hash(item_id)) % len(templates)]


def _render_template(template: str, item: PhraseItem) -> str:
    return template.format(
        normalized=item.normalized,
        keyword=_pick_keyword(item),
        focus=_pick_focus_phrase(item)
    )


def _build_complete_conjugation_question_llm(
    item: PhraseItem,
    learner_profile: LearnerProfile
) -> tuple[str, str | None]:
    infinitive = _main_verb_infinitive(item)

    if not infinitive:
        return "Identifica o verbo na frase.", _main_verb_surface(item)

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You create short European Portuguese worksheet exercises for young learners. "
                        "Generate one fill-in-the-blank sentence that uses the SAME target verb as the source phrase, "
                        "but in a NEW context that makes natural semantic sense. "
                        "If the source input is a single verb in the infinitive, create a natural fill-in-the-blank sentence "
                        "that uses that verb in a suitable context. "
                        "Do not refer to the source as if it were a full sentence. "
                        "Requirements: "
                        "Use European Portuguese. "
                        "Keep the sentence simple and age-appropriate. "
                        "The sentence must be natural and plausible. "
                        "Include exactly one blank written as _____. "
                        "Do not repeat the original phrase too closely unless necessary. "
                        "Do not produce a context that clashes with the meaning of the verb. "
                        "Return a worksheet-style instruction sentence in Portuguese and the expected conjugated answer."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f'Source input: "{item.normalized}"\n'
                        f'Input type: "{item.input_type or ""}"\n'
                        f'Lexical type: "{item.lexical_type or ""}"\n'
                        f'Target verb infinitive: "{infinitive}"\n'
                        f'English gloss: "{item.gloss_en or ""}"\n'
                        f'Learner profile: {_learner_descriptor(learner_profile)}\n\n'
                        "Return:\n"
                        '- question_pt: start with "Completa a frase com o verbo da frase acima:" followed by a natural sentence with one blank\n'
                        "- answer_pt: the expected conjugated answer for the blank\n"
                    )
                }
            ],
            response_format=QuestionOutput
        )

        parsed = completion.choices[0].message.parsed
        question_pt = (parsed.question_pt or "").strip()
        answer_pt = (parsed.answer_pt or "").strip() or None

        if not question_pt or "_____" not in question_pt:
            return f'Escreve uma nova frase com o verbo "{infinitive}".', infinitive

        return question_pt, answer_pt

    except Exception as e:
        print(f"[QUESTION LLM ERROR] complete_conjugation item={item.normalized!r} error={e}")
        return f'Escreve uma nova frase com o verbo "{infinitive}".', infinitive


def _build_reuse_verb_question_llm(
    item: PhraseItem,
    learner_profile: LearnerProfile
) -> tuple[str, str | None]:
    infinitive = _main_verb_infinitive(item)

    if not infinitive:
        return "Identifica o verbo nesta frase.", _main_verb_surface(item)

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You create short European Portuguese worksheet exercises for young learners. "
                        "Write one natural worksheet instruction asking the learner to create a NEW sentence "
                        "using the same target verb as the source phrase. "
                        "Requirements: "
                        "Use European Portuguese. "
                        "Keep it short, clear, and age-appropriate. "
                        "Do not add multiple tasks. "
                        "Do not use unnatural wording."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f'Source phrase: "{item.normalized}"\n'
                        f'Target verb infinitive: "{infinitive}"\n'
                        f'Learner profile: {_learner_descriptor(learner_profile)}\n\n'
                        "Return:\n"
                        "- question_pt: one instruction in Portuguese\n"
                        "- answer_pt: null\n"
                    )
                }
            ],
            response_format=QuestionOutput
        )

        parsed = completion.choices[0].message.parsed
        question_pt = (parsed.question_pt or "").strip()

        if not question_pt:
            return f'Escreve uma nova frase com o verbo "{infinitive}".', None

        return question_pt, None

    except Exception as e:
        print(f"[QUESTION LLM ERROR] reuse_verb item={item.normalized!r} error={e}")
        return f'Escreve uma nova frase com o verbo "{infinitive}".', None


def _build_question_for_family(
    item: PhraseItem,
    exercise_family: str,
    learner_profile: LearnerProfile
) -> tuple[str, str | None]:
    if not exercise_family or exercise_family == "sem_pergunta":
        return "", None

    if _family_is_llm_backed(exercise_family):
        return _build_llm_question_for_family(
            item=item,
            exercise_family=exercise_family,
            learner_profile=learner_profile
        )

    return _build_template_question_for_family(
        item=item,
        exercise_family=exercise_family,
        learner_profile=learner_profile
    )


def build_question_for_item(
    item: PhraseItem,
    question_mode: str,
    learner_profile: LearnerProfile,
    batch_context: QuestionBatchContext | None = None
) -> tuple[str, str | None, str]:
    family = _choose_exercise_family(
        item=item,
        question_mode=question_mode,
        learner_profile=learner_profile,
        batch_context=batch_context
    )

    if not family:
        return "", None, ""

    question, answer = _build_question_for_family(
        item=item,
        exercise_family=family,
        learner_profile=learner_profile
    )

    return question, answer, family

def get_allowed_families_for_item(
    item: PhraseItem,
    learner_profile: LearnerProfile,
) -> list[str]:
    category = _classify_item(item)
    rule = _get_rule_entry(category)

    allowed = rule.get("allowed_families", [])
    allowed = _filter_families_by_structure(item, allowed)

    return allowed


def build_question_from_family(
    item: PhraseItem,
    exercise_family: str,
    learner_profile: LearnerProfile
) -> tuple[str, str | None]:
    return _build_question_for_family(
        item=item,
        exercise_family=exercise_family,
        learner_profile=learner_profile
    )