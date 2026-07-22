PROMPTS = {
    1: """
You will receive a machine translation evaluation submission, with the following fields:
- `source_text`: Text to be translated.
- `source_lang`: Language of the source text.
- `target_lang`: Language of the target text.
- `verification_rules`: Rules testing particular aspects of the translation.
- `translations`: The human translation only.
- `source_instructions`: Additional instructions for the translation.

Your job is to transplant this submission into a new language, either on the source side or the target side.

You will receive:
1. `transplant_side`, either "source" or "target";
2. `transplant_lang`, the language to transplant into;


Adapt the submission to the new language pair.
Return only these transplant-relevant fields. Do not add metadata fields or ids.

If `transplant_side` is "target":
- Keep input `source_text` unchanged.
- Keep input `source_lang` unchanged.
- Set `target_lang` to `transplant_lang`.
- Translate the `human` model translation into `transplant_lang` (taking into account the original `source_text` if needed) as the new `human` model translation.
- Make minimal changes to each verification rule but ensure that it is applicable to the new language pair and testing the same aspect as the original verification rule.

If `transplant_side` is "source":
- Set `source_lang` to `transplant_lang`.
- Rewrite `source_text` naturally in `transplant_lang`.
- Keep output `target_lang` unchanged.
- Maintain the original human translation.
- Make minimal changes to each verification rule but ensure that it is applicable to the new language pair and testing the same aspect as the original verification rule.
"""
}
