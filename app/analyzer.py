import uuid
from openai import OpenAI
from app.models import PhraseItem, AnalyzerOutput

client = OpenAI()


def analyze_phrase(text: str) -> PhraseItem:
    normalized = text.strip()
    if not normalized:
        raise RuntimeError("Empty input is not allowed.")

    looks_like_single_word = len(normalized.split()) == 1
    if not looks_like_single_word and normalized[-1] not in ".!?":
        normalized += "."

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You create structured metadata for Portuguese language-learning worksheets "
                        "for intermediate young learners. "
                        "Handle both single words and full phrases. "
                        "Prefer literal, pedagogically useful interpretations. "
                        "Use European Portuguese. "
                        "All *_pt fields must stay in Portuguese, not English."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f'Portuguese input: "{normalized}"\n\n'
                        "Return structured output with these fields:\n"
                        "- gloss_en\n"
                        "- input_type\n"
                        "- lexical_type\n"
                        "- visual_type\n"
                        "- teacher_review\n"
                        "- scene\n"
                        "- image_prompt\n"
                        "- keyword_pt\n"
                        "- verb_pt\n"
                        "- focus_phrase_pt\n"
                        "- pedagogical_target\n"
                        "- main_verb_infinitive_pt\n"
                        "- main_verb_surface_pt\n"
                        "- subject_pt\n"
                        "- number_pt\n"
                        "- tense_pt\n\n"
                        "Rules:\n"
                        "- input_type must be one of: word, phrase, sentence\n"
                        "- lexical_type is mainly for single-word inputs\n"
                        "- gloss_en must be short and natural\n"
                        "- keyword_pt should be the most teachable Portuguese word in the input\n"
                        "- verb_pt should be the main Portuguese verb if clear, otherwise null\n"
                        "- focus_phrase_pt should be a short Portuguese chunk useful for classroom focus\n"
                        "- pedagogical_target should be the best worksheet focus: "
                        "vocabulary, verb, noun, meaning, description, grammar, or other\n"
                        "- main_verb_infinitive_pt should be the infinitive form of the main verb if clear\n"
                        "- main_verb_surface_pt should be the actual verb form used in the input if clear\n"
                        "- subject_pt should be the Portuguese subject if clear\n"
                        "- number_pt should be singular or plural if clear\n"
                        "- tense_pt should be a simple Portuguese tense label, e.g. presente, if clear\n"
                        "- If the phrase is ambiguous or idiomatic, set teacher_review=true when needed\n"
                    ),
                },
            ],
            response_format=AnalyzerOutput,
        )

        parsed = completion.choices[0].message.parsed

        return PhraseItem(
            id=str(uuid.uuid4()),
            original=text,
            normalized=normalized,
            gloss_en=parsed.gloss_en,
            input_type=parsed.input_type,
            lexical_type=parsed.lexical_type,
            visual_type=parsed.visual_type,
            teacher_review=parsed.teacher_review,
            scene=parsed.scene,
            image_prompt=parsed.image_prompt,
            keyword_pt=parsed.keyword_pt,
            verb_pt=parsed.verb_pt,
            focus_phrase_pt=parsed.focus_phrase_pt,
            pedagogical_target=parsed.pedagogical_target,
            main_verb_infinitive_pt=parsed.main_verb_infinitive_pt,
            main_verb_surface_pt=parsed.main_verb_surface_pt,
            subject_pt=parsed.subject_pt,
            number_pt=parsed.number_pt,
            tense_pt=parsed.tense_pt,
        )

    except Exception as e:
        print(f"[ANALYZER ERROR] input={text!r} normalized={normalized!r} error={e}")
        raise RuntimeError(f"Analyzer failed for input '{text}'.") from e