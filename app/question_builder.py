from collections import defaultdict

from app.draft_models import LearnerProfile
from app.models import PhraseItem


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


def allowed_grammar_families(item: PhraseItem, learner_profile: LearnerProfile) -> list[str]:
    level = learner_profile.cefr_level

    if level == "A1":
        families = ["identify_verb", "reuse_verb", "complete_conjugation"]
    elif level == "A2":
        families = ["identify_verb", "reuse_verb", "complete_conjugation", "change_subject"]
    elif level in {"B1", "B2"}:
        families = ["identify_verb", "reuse_verb", "complete_conjugation", "change_subject", "rewrite_plural"]
    else:
        families = ["identify_verb"]

    valid = []

    for family in families:
        if family == "identify_verb" and item.main_verb_surface_pt:
            valid.append(family)
        elif family == "reuse_verb" and item.main_verb_infinitive_pt:
            valid.append(family)
        elif family == "complete_conjugation" and item.main_verb_infinitive_pt:
            valid.append(family)
        elif family == "change_subject" and item.subject_pt:
            valid.append(family)
        elif family == "rewrite_plural" and item.number_pt == "singular":
            valid.append(family)

    return valid or ["identify_verb"]


def learner_is_younger(learner_profile: LearnerProfile) -> bool:
    return learner_profile.age_max is not None and learner_profile.age_max <= 10


def simplify_instruction(text: str, learner_profile: LearnerProfile) -> str:
    if learner_is_younger(learner_profile):
        replacements = {
            "utilizar": "usar",
            "reescreve": "escreve de novo",
            "adapta o verbo": "muda o verbo",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
    return text


def _build_grammar_question(
    item: PhraseItem,
    family: str,
    learner_profile: LearnerProfile,
) -> tuple[str, str | None]:
    infinitive = item.main_verb_infinitive_pt or item.verb_pt
    surface = item.main_verb_surface_pt or item.verb_pt

    if family == "identify_verb":
        templates = [
            "Identifica o verbo nesta frase.",
            f'Qual é o verbo na frase "{item.normalized}"?',
            "Assinala o verbo da frase.",
        ]
        question = templates[abs(hash(item.id)) % len(templates)]
        return simplify_instruction(question, learner_profile), surface

    if family == "reuse_verb" and infinitive:
        templates = [
            f'Escreve outra frase a utilizar o verbo "{infinitive}".',
            f'Escreve uma nova frase com o verbo "{infinitive}".',
            f'Usa o verbo "{infinitive}" numa frase diferente.',
        ]
        question = templates[abs(hash(item.id)) % len(templates)]
        return simplify_instruction(question, learner_profile), infinitive

    if family == "complete_conjugation" and infinitive:
        templates = [
            "Completa a frase: Eu _____ no parque. Usa o verbo da frase acima e tem atenção à conjugação.",
            "Completa a frase com o verbo da frase acima: Nós _____ no parque.",
            f'Completa a frase usando o verbo "{infinitive}": Eles _____ todos os dias.',
        ]
        question = templates[abs(hash(item.id)) % len(templates)]
        return simplify_instruction(question, learner_profile), infinitive

    if family == "change_subject":
        templates = [
            'Substitui o sujeito por "eles" e reescreve a frase.',
            'Troca o sujeito por "nós" e adapta o verbo.',
            "Muda o sujeito da frase e ajusta o verbo corretamente.",
        ]
        question = templates[abs(hash(item.id)) % len(templates)]
        return simplify_instruction(question, learner_profile), None

    if family == "rewrite_plural":
        templates = [
            "Reescreve a frase no plural.",
            "Passa a frase para o plural.",
            "Transforma a frase para que o sujeito fique no plural.",
        ]
        question = templates[abs(hash(item.id)) % len(templates)]
        return simplify_instruction(question, learner_profile), None

    return simplify_instruction("Identifica o verbo na frase.", learner_profile), surface


def _build_vocabulary_question(item: PhraseItem) -> tuple[str, str | None, str]:
    keyword = _pick_keyword(item)
    focus = _pick_focus_phrase(item)

    families = [
        "meaning",
        "use_in_sentence",
        "find_word",
    ]
    family = families[abs(hash(item.id)) % len(families)]

    if family == "meaning":
        return f'O que significa a palavra "{keyword}"?', item.gloss_en, family

    if family == "use_in_sentence":
        return f'Escreve uma frase com a palavra "{keyword}".', None, family

    return f'Encontra na frase a palavra ou expressão "{focus}".', focus, family


def _build_comprehension_question(item: PhraseItem) -> tuple[str, str | None, str]:
    families = [
        "what_happens",
        "who_is_there",
        "what_do_you_see",
    ]
    family = families[abs(hash(item.id)) % len(families)]

    if family == "what_happens":
        return "O que está a acontecer na imagem?", item.scene.action if item.scene else None, family

    if family == "who_is_there":
        return "Quem aparece na imagem?", item.scene.subject if item.scene else None, family

    return "O que vês nesta imagem?", None, family


def _build_production_question(item: PhraseItem) -> tuple[str, str | None, str]:
    families = [
        "describe_two_sentences",
        "write_one_sentence",
        "describe_freely",
    ]
    family = families[abs(hash(item.id)) % len(families)]

    if family == "describe_two_sentences":
        return "Descreve a imagem em duas frases.", None, family

    if family == "write_one_sentence":
        return "Escreve uma frase sobre esta imagem.", None, family

    return "Observa a imagem e escreve o que está a acontecer.", None, family


def build_question_for_item(
    item: PhraseItem,
    question_mode: str,
    learner_profile: LearnerProfile,
    batch_context: QuestionBatchContext | None = None,
) -> tuple[str, str | None, str]:
    """
    Returns:
        (question_pt, answer_pt, exercise_family)
    """

    if question_mode == "grammar":
        candidates = allowed_grammar_families(item, learner_profile)

        if batch_context:
            family = batch_context.choose_least_used(candidates)
        else:
            family = candidates[0]

        question, answer = _build_grammar_question(item, family, learner_profile)
        return question, answer, family

    if question_mode == "vocabulary":
        question, answer, family = _build_vocabulary_question(item)
        if batch_context:
            batch_context.family_counts[family] += 1
        return question, answer, family

    if question_mode == "comprehension":
        question, answer, family = _build_comprehension_question(item)
        if batch_context:
            batch_context.family_counts[family] += 1
        return question, answer, family

    if question_mode == "production":
        question, answer, family = _build_production_question(item)
        if batch_context:
            batch_context.family_counts[family] += 1
        return question, answer, family

    return "", None, ""


def build_question_from_family(
    item: PhraseItem,
    exercise_family: str,
    learner_profile: LearnerProfile,
) -> tuple[str, str | None]:
    if exercise_family == "meaning":
        keyword = _pick_keyword(item)
        return f'O que significa a palavra "{keyword}"?', item.gloss_en

    if exercise_family == "use_in_sentence":
        keyword = _pick_keyword(item)
        return f'Escreve uma frase com a palavra "{keyword}".', None

    if exercise_family == "find_word":
        focus = _pick_focus_phrase(item)
        return f'Encontra na frase a palavra ou expressão "{focus}".', focus

    if exercise_family in {
        "identify_verb",
        "reuse_verb",
        "complete_conjugation",
        "change_subject",
        "rewrite_plural",
    }:
        return _build_grammar_question(item, exercise_family, learner_profile)

    if exercise_family == "what_happens":
        return "O que está a acontecer na imagem?", item.scene.action if item.scene else None

    if exercise_family == "who_is_there":
        return "Quem aparece na imagem?", item.scene.subject if item.scene else None

    if exercise_family == "what_do_you_see":
        return "O que vês nesta imagem?", None

    if exercise_family == "describe_two_sentences":
        return "Descreve a imagem em duas frases.", None

    if exercise_family == "write_one_sentence":
        return "Escreve uma frase sobre esta imagem.", None

    if exercise_family == "describe_freely":
        return "Observa a imagem e escreve o que está a acontecer.", None

    if exercise_family == "sem_pergunta":
        return "", None

    return "", None