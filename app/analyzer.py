import uuid
from openai import OpenAI
from app.models import PhraseItem, AnalyzerOutput

client = OpenAI()


def analyze_phrase(text: str) -> PhraseItem:
    normalized = text.strip()
    if not normalized:
        raise RuntimeError("Empty input is not allowed.")

    # Keep punctuation for full phrases/sentences, but don't force it for single words
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
                        "Prefer literal, pedagogically useful interpretations."
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
                        "- image_prompt\n\n"
                        "Rules:\n"
                        "- input_type must be one of: word, phrase, sentence\n"
                        "- lexical_type is mainly for single-word inputs\n"
                        "- For nouns, prefer showing the object clearly\n"
                        "- For verbs, prefer showing the action clearly\n"
                        "- For adjectives or feelings, prefer expression, posture, or simple context\n"
                        "- If the word is ambiguous, set teacher_review=true\n"
                        "- gloss_en must be short and natural\n"
                        "- scene should include subject, action, object, and setting when possible\n"
                        "- image_prompt can be a draft prompt for debugging\n"
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
        )

    except Exception as e:
        print(f"[ANALYZER ERROR] input={text!r} normalized={normalized!r} error={e}")
        raise RuntimeError(
            f"Analyzer failed for input '{text}'."
        ) from e