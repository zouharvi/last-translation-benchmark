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
""",
2: """
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
2. `transplant_lang`, the language to transplant into.

Adapt the submission to the new language pair.
Return only the transplant-relevant fields. Do not add metadata fields or ids.

Treat the provided human translation as a MEANING REFERENCE ONLY — it tells you what the text means, in the old target language.
Translate source_text afresh into transplant_lang; do not carry over the old translation's phrasing or structure by default.
Where a natural rendering in transplant_lang happens to line up closely with the old translation, that is fine — but let that come from what reads naturally in transplant_lang, not from following the old translation.

If `transplant_side` is "target":
- Keep input `source_text` and `source_lang` unchanged.
- Set `target_lang` to `transplant_lang`.
- Produce a NEW human translation by translating `source_text` directly into
  `transplant_lang`, as a fluent native speaker would naturally write it. Use the
  original human translation ONLY to resolve ambiguous meaning, never as a model
  for phrasing, word order, or structure.

  Before writing, resolve the intended SENSE of each ambiguous word or referent
  (e.g. which meaning of a polysemous noun, singular vs. plural, literal vs.
  figurative). Translate that resolved meaning, not the surface form.

  Actively avoid these literal-translation failures:
    - WORD ORDER: use the natural word order of `transplant_lang`, even when it
      differs from the source. Do not preserve source order when the target
      language would place elements differently.
    - CALQUED IDIOMS: render idioms, set phrases, and wordplay as the nearest
      NATURAL equivalent in `transplant_lang`. Never translate an idiom
      word-for-word if `transplant_lang` expresses the concept differently.
    - WRONG SENSE: never carry over a literal reading when context makes another
      sense correct (e.g. a "drinking glass" must not become a generic/plural
      "glass").
    - CONCEPT GAPS: if a concept, idiom, or referent has no natural analogue in
      `transplant_lang`, use what a native writer would ACTUALLY say. Prefer the
      real-world localized referent (e.g. the actual local name of a species or
      object) over both a literal calque and an invented literal construction.
    - UNITS, NAMES, TITLES: render honorifics, name order, and units in the form
      native to `transplant_lang` (e.g. correct honorific placement for names).

  Preserve deliberate features of the source: numeric wordplay, puns, register,
  and tone should be recreated with `transplant_lang` equivalents, not dropped
  and not calqued. Match the register of the source — do not make a neutral
  source casual, or a casual source neutral.

  When wordplay and localization conflict, prefer preserving the wordplay if the
  joke or meaning depends on it; otherwise prefer the natural localized referent.

  The result must read as if originally written in `transplant_lang`.

  Before returning, re-read your `human` translation on its own (ignore the
  source) and check: does any phrase read as translated rather than native? Is
  the word order natural? Are idioms native? Is each ambiguous referent the
  correct sense? Is the register faithful to the source? Does it satisfy every
  verification rule? Fix anything that fails.

- Adapt each verification rule minimally so it applies to the new language pair
  and tests the same aspect. If a rule requires a specific feature (e.g. "uses a
  target-language idiom"), your new human translation MUST actually satisfy that
  rule.

If `transplant_side` is "source":
- Set `source_lang` to `transplant_lang`.
- Rewrite `source_text` naturally in `transplant_lang`, as a native speaker would
  write it — natural word order, idioms, and register, not a calque of the
  original source.
- Keep output `target_lang` unchanged.
- Maintain the original human translation.
- Make minimal changes to each verification rule but ensure that it is applicable
  to the new language pair and testing the same aspect as the original
  verification rule.
""",
3: """
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
2. `transplant_lang`, the language to transplant into.

Adapt the submission to the new language pair.
Return only the transplant-relevant fields. Do not add metadata fields or ids.

Treat the provided human translation as a MEANING REFERENCE ONLY — it tells you what the text means, in the old target language.
Translate source_text afresh into transplant_lang; do not carry over the old translation's phrasing or structure by default.
Where a natural rendering in transplant_lang happens to line up closely with the old translation, that is fine — but let that come from what reads naturally in transplant_lang, not from following the old translation.

If `transplant_side` is "target":
- Keep input `source_text` and `source_lang` unchanged.
- Set `target_lang` to `transplant_lang`.
- If `source_instructions` is present, treat it as binding: it may specify target
  style, audience, register, or tone. Your `transplant_lang` translation must
  satisfy it. If following it requires a choice the source leaves open (e.g.
  formality level), make that choice as `source_instructions` directs.
- Produce a NEW human translation by translating `source_text` directly into
  `transplant_lang`, as a fluent native speaker would naturally write it. Use the
  original human translation ONLY to see how a difficulty (pun, idiom, wordplay,
  ambiguous referent) was resolved in meaning -- never as a model for phrasing,
  word order, or structure.

  Before writing, resolve the intended SENSE of each word or referent (which
  meaning of a polysemous noun, singular vs. plural, literal vs. figurative).
  Translate that resolved meaning, not the surface form.

  Actively avoid these literal-translation failures:
    - WORD ORDER: use the natural word order of `transplant_lang`, even when it
      differs from the source. Do not preserve source order when the target
      language would place elements differently.
    - CALQUED IDIOMS: render idioms, set phrases, and wordplay as the nearest
      NATURAL equivalent in `transplant_lang`. Never translate an idiom
      word-for-word if `transplant_lang` expresses the concept differently.
    - WRONG SENSE: never carry over a literal reading when context makes another
      sense correct (e.g. a "drinking glass" must not become a generic/plural
      "glass").
    - CONCEPT GAPS: if a concept, idiom, or referent has no natural analogue in
      `transplant_lang`, use what a native writer would ACTUALLY say. Prefer the
      real-world localized referent (e.g. the actual local name of a species or
      object) over both a literal calque and an invented literal construction.
    - UNITS, NAMES, TITLES: render honorifics, name order, and units in the form
      native to `transplant_lang` (e.g. correct honorific placement for names).
    - GRAMMATICALLY FORCED FEATURES: if `transplant_lang` obligatorily marks
      something the source leaves unspecified (e.g. grammatical gender,
      formality/honorific level, number, evidentiality), choose the value that
      best fits the source's context, register, and any `source_instructions`,
      and apply it consistently throughout.

  Preserve deliberate features of the source: numeric wordplay, puns, register,
  and tone should be recreated with `transplant_lang` equivalents, not dropped
  and not calqued. Match the register of the source -- do not make a neutral
  source casual, or a casual source neutral.

  When wordplay and localization conflict, prefer preserving the wordplay if the
  joke or meaning depends on it; otherwise prefer the natural localized referent.

  The result must read as if originally written in `transplant_lang`.

  Before returning, re-read your `human` translation on its own (ignore the
  source) and check: does any phrase read as translated rather than native? Is
  the word order natural? Are idioms native? Is each referent the correct sense?
  Are grammatically forced features (gender, formality, number) filled in
  consistently and appropriately? Is the register faithful to the source? Does it
  satisfy every verification rule and any `source_instructions`? Fix anything
  that fails.

- Adapt each verification rule minimally so it applies to the new language pair
  and tests the same aspect. If a rule requires a specific feature (e.g. "uses a
  target-language idiom"), your new human translation MUST actually satisfy that
  rule.

If `transplant_side` is "source":
- Set `source_lang` to `transplant_lang`.
- Rewrite `source_text` naturally in `transplant_lang`, as a native speaker would
  write it — natural word order, idioms, and register, not a calque of the
  original source.
- Keep output `target_lang` unchanged.
- Maintain the original human translation.
- Make minimal changes to each verification rule but ensure that it is applicable
  to the new language pair and testing the same aspect as the original
  verification rule.
""",
4: """
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
2. `transplant_lang`, the language to transplant into.

Adapt the submission to the new language pair.
Return only the transplant-relevant fields. Do not add metadata fields or ids.

Treat the provided human translation as a MEANING REFERENCE ONLY — it tells you what the text means, in the old target language.
Translate source_text afresh into transplant_lang; do not carry over the old translation's phrasing or structure by default.
Where a natural rendering in transplant_lang happens to line up closely with the old translation, that is fine — but let that come from what reads naturally in transplant_lang, not from following the old translation.

If `transplant_side` is "target":
- Keep input `source_text` and `source_lang` unchanged.
- Set `target_lang` to `transplant_lang`.
- If `source_instructions` is present, treat it as binding: it may specify target
  style, audience, register, or tone. Your `transplant_lang` translation must
  satisfy it. If following it requires a choice the source leaves open (e.g.
  formality level), make that choice as `source_instructions` directs.
- Produce a NEW human translation by translating `source_text` directly into
  `transplant_lang`, as a fluent native speaker would naturally write it. Use the
  original human translation ONLY to see how a difficulty (pun, idiom, wordplay,
  ambiguous referent) was resolved in meaning -- never as a model for phrasing,
  word order, or structure.

  Before writing, resolve the intended SENSE of each word or referent (which
  meaning of a polysemous noun, singular vs. plural, literal vs. figurative).
  Translate that resolved meaning, not the surface form.

  Actively avoid these literal-translation failures:
    - WORD ORDER: use the natural word order of `transplant_lang`, even when it
      differs from the source. Do not preserve source order when the target
      language would place elements differently.
    - CALQUED IDIOMS: render idioms, set phrases, and wordplay as the nearest
      NATURAL equivalent in `transplant_lang`. Never translate an idiom
      word-for-word if `transplant_lang` expresses the concept differently.
    - WRONG SENSE: never carry over a literal reading when context makes another
      sense correct (e.g. a "drinking glass" must not become a generic/plural
      "glass").
    - CONCEPT GAPS: if a concept, idiom, or referent has no natural analogue in
      `transplant_lang`, use what a native writer would ACTUALLY say. Prefer the
      real-world localized referent (e.g. the actual local name of a species or
      object) over both a literal calque and an invented literal construction.
    - UNITS, NAMES, TITLES: render honorifics, name order, and units in the form
      native to `transplant_lang` (e.g. correct honorific placement for names).
    - GRAMMATICALLY FORCED FEATURES: if `transplant_lang` obligatorily marks
      something the source leaves unspecified (e.g. grammatical gender,
      formality/honorific level, number, evidentiality), choose the value that
      best fits the source's context, register, and any `source_instructions`,
      and apply it consistently throughout.

  Preserve deliberate features of the source: numeric wordplay, puns, register,
  and tone should be recreated with `transplant_lang` equivalents, not dropped
  and not calqued. Match the register of the source -- do not make a neutral
  source casual, or a casual source neutral.

  When wordplay and localization conflict, prefer preserving the wordplay if the
  joke or meaning depends on it; otherwise prefer the natural localized referent.

  The result must read as if originally written in `transplant_lang`.

  Before returning, re-read your `human` translation on its own (ignore the
  source) and check: does any phrase read as translated rather than native? Is
  the word order natural? Are idioms native? Is each referent the correct sense?
  Are grammatically forced features (gender, formality, number) filled in
  consistently and appropriately? Is the register faithful to the source? Does it
  satisfy every verification rule and any `source_instructions`? Fix anything
  that fails.

- Adapt each verification rule minimally so it applies to the new language pair
  and tests the same aspect:
    - If a rule tests something about `source_text` (an ambiguity, pun, referent,
      or word in the source), keep it essentially unchanged; only update any
      reference to the target language in its wording.
    - If a rule tests a feature of the OLD target language:
        - If `transplant_lang` has an equivalent feature, re-anchor the rule to
          that feature.
        - If `transplant_lang` has no analogue for that feature, drop the rule.
    - If a rule requires a specific feature (e.g. "uses a target-language idiom"),
      your new `human` translation MUST actually satisfy that rule. Every rule you
      keep must be satisfied by your new translation — the two outputs must not
      contradict.
    - Keep rules general (testing a concept or sense), not tied to one specific
      output word or phrase. Do not rewrite a rule so it checks for an exact
      target word.
    - If `transplant_lang` obligatorily marks something the source leaves
      unspecified (e.g. grammatical gender, formality/honorific level, number),
      you may add one rule that checks this feature was resolved correctly and
      consistently. Your new `human` translation must satisfy any such rule.
    - When a rule quotes or names a token from `source_text` or the `translation`,
      reproduce it in a single consistent script — do not mix scripts within one word or
      splice characters from different writing systems. Quote source tokens exactly as
      they appear in `source_text`.

If `transplant_side` is "source":
- Set `source_lang` to `transplant_lang`.
- Rewrite `source_text` naturally in `transplant_lang`, as a native speaker would
  write it — natural word order, idioms, and register, not a calque of the
  original source.
- Keep output `target_lang` unchanged.
- Maintain the original human translation.
- Make minimal changes to each verification rule but ensure that it is applicable
  to the new language pair and testing the same aspect as the original
  verification rule.
""",
}
