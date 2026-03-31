def _clean(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    return value if value else None


def _join_scene(subject: str | None, action: str | None, obj: str | None, setting: str | None) -> str:
    parts = []

    if subject and action and obj:
        parts.append(f"{subject} {action} {obj}")
    elif subject and action:
        parts.append(f"{subject} {action}")
    elif obj:
        parts.append(f"{obj}")
    elif subject:
        parts.append(subject)
    elif action:
        parts.append(f"someone {action}")

    if setting:
        parts.append(f"in {setting}")

    return " ".join(parts).strip()


def build_image_prompt(item) -> str:
    subject = _clean(item.scene.subject if item.scene else None)
    action = _clean(item.scene.action if item.scene else None)
    obj = _clean(item.scene.object if item.scene else None)
    setting = _clean(item.scene.setting if item.scene else None)
    gloss = _clean(item.gloss_en)
    input_type = item.input_type or "phrase"
    lexical_type = item.lexical_type or "other"
    visual_type = item.visual_type or "literal_visual"

    scene_text = _join_scene(subject, action, obj, setting)

    base_rules = [
        "Child-friendly educational illustration",
        "clear and easy to understand",
        "simple background",
        "one main idea",
        "no text in the image",
        "no logos",
        "no watermarks",
        "no clutter",
    ]

    details = []

    if input_type == "word":
        details.append(f"Portuguese word: '{item.normalized}'")
        if gloss:
            details.append(f"English meaning: '{gloss}'")

        if lexical_type == "noun":
            details.extend([
                "Show the object clearly and centrally",
                "Make it easy for a learner to identify",
                "Do not add unnecessary extra objects",
            ])
            if scene_text:
                details.append(f"Scene: {scene_text}")

        elif lexical_type == "verb":
            details.extend([
                "Show the action clearly",
                "Use a simple scene with one person or animal performing the action",
                "Make the movement obvious at a glance",
            ])
            if scene_text:
                details.append(f"Scene: {scene_text}")

        elif lexical_type == "adjective":
            details.extend([
                "Show the meaning through expression, posture, or simple context",
                "Keep the visual interpretation clear and gentle",
            ])
            if scene_text:
                details.append(f"Scene: {scene_text}")

        else:
            details.extend([
                "Show the clearest and most common visual meaning",
                "Avoid less common interpretations",
            ])
            if scene_text:
                details.append(f"Scene: {scene_text}")

    else:
        if visual_type == "literal_visual":
            details = [
                f"Show the literal meaning of the Portuguese input: '{item.normalized}'",
                f"English meaning: '{gloss}'" if gloss else "",
                f"Scene: {scene_text}" if scene_text else "",
                "Make the main action very clear",
                "Make the subject easy to identify",
            ]

        elif visual_type == "literal_but_ambiguous":
            details = [
                f"Show the clearest literal interpretation of the Portuguese input: '{item.normalized}'",
                f"English meaning: '{gloss}'" if gloss else "",
                f"Scene: {scene_text}" if scene_text else "",
                "Choose the most common and teachable interpretation",
                "Avoid elements that suggest a different meaning",
            ]

        elif visual_type == "abstract":
            details = [
                f"Create a teachable visual interpretation of the Portuguese input: '{item.normalized}'",
                f"English meaning: '{gloss}'" if gloss else "",
                f"Scene: {scene_text}" if scene_text else "",
                "Use facial expression, posture, and context to show the meaning clearly",
                "Avoid surreal or metaphorical elements",
            ]

        elif visual_type == "idiomatic":
            details = [
                f"Show the intended meaning of the Portuguese input: '{item.normalized}'",
                f"English meaning: '{gloss}'" if gloss else "",
                f"Scene: {scene_text}" if scene_text else "",
                "Do not illustrate the words literally if that would be misleading",
                "Show the meaning in a simple everyday situation",
            ]

        else:
            details = [
                f"Show the meaning of the Portuguese input: '{item.normalized}'",
                f"English meaning: '{gloss}'" if gloss else "",
                f"Scene: {scene_text}" if scene_text else "",
                "Keep the meaning clear and simple",
            ]

    if item.teacher_review:
        details.append("Use the safest and most teachable interpretation")

    prompt_lines = [base_rules[0] + "."] + [rule + "." for rule in base_rules[1:]]
    prompt_lines += [detail + "." for detail in details if detail]

    return "\n".join(prompt_lines)