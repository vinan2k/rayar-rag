"""
rag.py — Retrieval-augmented generation.

Retrieves relevant passages, builds a grounded prompt, and generates an answer
with inline citations. The prompts are written to resist fabrication, which is
the failure that matters here: an invented figure in a consulting deliverable
costs more than a refusal to answer.
"""

from typing import Optional

from core.embeddings import VectorStore
from core.models import Backend

# How much of a document to put in front of the model when summarising.
# Bounded by characters rather than passages, because passages vary in length
# and a fixed count either wastes context on short ones or truncates long ones.
SUMMARY_CHAR_LIMIT = 12_000

ANSWER_PROMPT = """You are a research assistant working from a document repository.

Use the provided excerpts to answer the question. Follow these rules:

1. EXTRACT information plainly present in the excerpts, even where it is not
   formatted as a list. If the question asks who was involved and the excerpts
   contain names with roles, extract those names. That IS answering from the
   context.

2. DO NOT INVENT facts absent from the excerpts. No fabricated names, numbers,
   dates or quotations.

3. DO NOT COMBINE unrelated content into a structure that is not there. If a
   genuine list exists, extract it. If only scattered mentions exist, present
   them as scattered mentions.

4. If the excerpts genuinely lack what was asked, say so:
   "The retrieved excerpts do not contain [the specific thing]. They cover
   [the actual topics]. Try a more specific question, or read the source."

CITATIONS:
- Use [1], [2], [3] inline. Each number is a document, not an excerpt.
- Several excerpts may share a number because they come from the same
  document. Cite the number as often as it applies.
- Do not mention filenames in the body of the answer.

EXCERPTS:
{context}

QUESTION: {query}

ANSWER:"""

SUMMARY_PROMPT = """Summarise the following document.

A document may contain several distinct sections or articles. Where it does,
summarise each separately rather than blending them into one account.

For the document, or for each section:

1. Topic and purpose, in a sentence.
2. Key arguments or findings, as three to five points.
3. What a practitioner would take from it.

Be specific. Name the actual concepts, frameworks, figures and recommendations
that appear in the text. A summary that could describe any document in the
collection is of no use to anyone.

If the content is too sparse to summarise meaningfully, say so plainly.

DOCUMENT: {source}

CONTENT:
{content}

SUMMARY:"""


def build_context(results: dict, max_chars_per_chunk: int = 2000) -> str:
    """
    Format retrieval results into a context block numbered by document.

    Every passage from the same document carries the same number, so a citation
    points at a source rather than at a chunk. An earlier version numbered each
    passage separately, which meant a document supplying five passages appeared
    once in the list beside the answer but five times in the context, under
    numbers the reader could not resolve: the answer would cite [6] with
    nothing on screen to say what [6] was.

    The model will use the same number more than once. That is correct, and it
    is what the reader sees.
    """
    docs = results["documents"][0]
    metas = results["metadatas"][0]

    # Numbered by first appearance, which is relevance order, so the same
    # sequence as the list of sources shown beside the answer.
    numbers: dict[str, int] = {}
    for meta in metas:
        source = meta.get("source", "unknown")
        if source not in numbers:
            numbers[source] = len(numbers) + 1

    parts = []
    for doc, meta in zip(docs, metas):
        source = meta.get("source", "unknown")
        parts.append(f"[{numbers[source]}] ({source})\n{doc[:max_chars_per_chunk]}")
    return "\n\n".join(parts)


def answer(
    store: VectorStore,
    ollama: Backend,
    collection: str,
    query: str,
    model: str,
    top_k: int = 15,
    temperature: float = 0.3,
    where: Optional[dict] = None,
) -> tuple[str, dict]:
    """
    Retrieve and answer. Returns (answer_text, raw_results).

    The raw results come back so the caller can show which sources the answer
    rests on without running the retrieval twice.
    """
    results = store.query(collection, query, top_k=top_k, where=where)
    if not results["documents"][0]:
        return "No matching content found in this collection.", results
    prompt = ANSWER_PROMPT.format(context=build_context(results), query=query)
    text = ollama.chat(model, prompt, temperature=temperature,
                       num_predict=1500, think=False)
    return (text or "(No response generated)"), results


def summarize(
    store: VectorStore,
    ollama: Backend,
    collection: str,
    source: str,
    model: str,
    temperature: float = 0.3,
) -> str:
    """
    Summarise one document from its stored passages.

    The whole document goes to the model, in order, truncated only if it
    exceeds the character limit. Sampling a fixed number of passages instead
    would produce a summary of an arbitrary slice while reading like a summary
    of the whole.
    """
    chunks = store.chunks_from_source(collection, source, limit=5000)
    if not chunks:
        return f"No content found for {source}."

    content = "\n\n".join(chunks)
    if len(content) > SUMMARY_CHAR_LIMIT:
        content = content[:SUMMARY_CHAR_LIMIT] + "\n\n[Document truncated for length]"

    prompt = SUMMARY_PROMPT.format(source=source, content=content)
    text = ollama.chat(model, prompt, temperature=temperature,
                       num_predict=1500, think=False)

    # A model given too much text sometimes emits a heading marker and stops.
    # Three characters render as nothing on screen, which reads as a silent
    # failure rather than a short answer, so it is reported as one.
    if len(text.strip().strip("#*-_ ")) < 40:
        return (
            f"The model returned almost nothing for this document "
            f"({len(chunks)} passages, {len(content):,} characters). It may be "
            f"too long for the context window. Lower SUMMARY_CHAR_LIMIT in "
            f"core/rag.py, or use a model with a larger context."
        )
    return text


def unique_sources(results: dict) -> list[tuple[str, int]]:
    """
    Distinct sources in a result set with their hit counts, ordered by
    first appearance so the most relevant document leads.
    """
    metas = results["metadatas"][0]
    order, counts = [], {}
    for meta in metas:
        src = meta.get("source", "unknown")
        if src not in counts:
            order.append(src)
            counts[src] = 0
        counts[src] += 1
    return [(src, counts[src]) for src in order]
