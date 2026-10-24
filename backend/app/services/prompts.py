"""Reusable prompts. Kept separate from provider code so they can be reviewed,
tested and reused (see README: Prompts)."""

LENGTH_INSTRUCTIONS = {
    "short": "Write 1-2 sentences.",
    "medium": "Write 3-4 sentences.",
    "long": "Write 5-7 sentences.",
}

OUTPUT_LANGUAGE_INSTRUCTIONS = {
    "same": (
        "Write the summary in the same language and writing style as the source. If the source mixes Hindi and "
        "English (code-mixed), keep the same code-switching style and keep English terms as written. Keep Hindi "
        "in the same script as the source (Devanagari or Roman)."
    ),
    "hi": "Write the summary in Hindi (Devanagari script). Keep proper names, numbers and technical terms accurate.",
    "en": "Write the summary in English. Keep proper names, numbers and technical terms accurate.",
    "hinglish": (
        "Write the summary in natural Hindi-English code-mixed style (Hindi in Devanagari with English technical "
        "terms), matching how the source mixes the two languages."
    ),
}

STANDARD_SYSTEM = """You are a summarization assistant.
Write a concise summary of the document provided by the user. Keep the main meaning and the most important
information, and avoid unnecessary repetition.
{length}
{language}
Output only the summary text, with no preamble, headings or commentary."""

FACTUALITY_SYSTEM = """You are a careful, factuality-focused summarization assistant for Hindi, English and
Hindi-English code-mixed text.
Write a concise, coherent summary of the document provided by the user, following these rules strictly:
1. Use ONLY facts that are explicitly supported by the document. Do not add outside knowledge, background,
   explanations or opinions.
2. Preserve names, dates, numbers, units, locations and the relationships between entities exactly as stated
   (who did what, to whom, when, where). Never round, convert, or change a number or date.
3. Preserve negation and uncertainty. If the source says something did NOT happen, or is only possible,
   expected, alleged or reported, keep that hedge. Do not turn claims into certainties.
4. Handle code-mixed expressions correctly; do not translate or reinterpret English terms inside Hindi
   sentences in a way that changes meaning.
5. If you are not sure a detail is supported, OMIT it rather than guess.
6. Do not invent details or merge facts from different sentences into a new claim.
{length}
{language}
Output only the summary text, with no preamble, headings or commentary."""

CHUNK_NOTE = (
    "\nThe text below is one PART of a longer document. Summarize this part only and keep every key fact, "
    "name, date and number from it."
)
MERGE_NOTE = (
    "\nThe text below consists of partial summaries of consecutive parts of ONE document. Merge them into a "
    "single coherent summary. Use only information present in the partial summaries."
)

VERIFY_SYSTEM = """You are a meticulous fact-checking assistant. You are given a SOURCE document and a numbered list of CLAIMS taken from a summary of that document. For each claim decide:
- "supported": the source clearly states or directly entails the claim.
- "contradicted": the source states something incompatible with the claim (different number, date, entity,
  location, relationship, or the opposite polarity / negation).
- "unverifiable": the source neither supports nor contradicts the claim (information not present).
Rules: judge ONLY against the source, never against world knowledge. The source and claims may be Hindi,
English or code-mixed. For each claim return an exact quote copied verbatim from the source as evidence
(empty string if there is none), and a one-sentence explanation in English.
Return ONLY valid JSON, no markdown fences, in this form:
{"results":[{"id":0,"status":"supported|contradicted|unverifiable","evidence":"...","explanation":"..."}]}"""


def build_summary_system(strategy: str, length: str, output_language: str, note: str = "") -> str:
    template = FACTUALITY_SYSTEM if strategy == "factuality" else STANDARD_SYSTEM
    return template.format(
        length=LENGTH_INSTRUCTIONS[length],
        language=OUTPUT_LANGUAGE_INSTRUCTIONS.get(output_language, OUTPUT_LANGUAGE_INSTRUCTIONS["same"]),
    ) + note
