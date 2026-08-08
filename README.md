# Rayar RAG

Ask questions of your own documents, on your own machine. Nothing is uploaded
anywhere. The model runs locally, the index sits on your disk, and every answer
shows the documents it came from.

**Version 0.1.0** — first public release.

---

## What it does

**Ask a question of a collection.** The answer appears beside a list of the
documents it drew on, numbered to match the markers in the text, so a claim can
be checked without scrolling away from it.

**Open any of those sources.** Summarise it, or question that document on its
own rather than the whole collection.

**Add documents through the browser.** PDF, Word, PowerPoint, Outlook messages,
plain email, Markdown and text. Originals are kept, because changing the
embedding model later means rebuilding from source.

That is the whole of it. There is no chat history, no document generation, no
agent. It answers questions about documents you own.

---

## Requirements

- Python 3.10 or later
- An inference server, either [Ollama](https://ollama.com) or anything speaking
  the OpenAI API: LM Studio, llama.cpp's server, vLLM, LocalAI
- One chat model and one embedding model

A machine with a graphics card is much faster but not required. On a computer
without one, use a small model and expect answers in tens of seconds rather
than seconds.

---

## Install

```bash
git clone https://github.com/vinan2k/rayar-rag.git
cd rayar-rag
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501`. A setup wizard runs on first start: it checks
your packages and inference server, asks where to keep things, and creates the
first account.

The requirements are pinned to an exact tested set. Installing anything newer
by hand may break the application in ways that are hard to diagnose.

---

## Models

Two are needed. With Ollama:

```bash
ollama pull qwen3:8b            # writes answers, about 5 GB
ollama pull nomic-embed-text    # indexes documents, about 300 MB
```

On a machine with 8 GB of memory or no graphics card, `llama3.2:3b` is a better
choice than `qwen3:8b`. With 24 GB or more, `qwen2.5:14b` and `phi4` both
produce longer and more careful answers.

**The embedding model cannot be changed later** without rebuilding every
collection. Retrieval does not fail loudly when it is changed; it quietly
returns worse results. Choose it once and leave it.

**Models differ in how well they follow instructions.** If a summary comes back
short or empty, or an answer arrives without citation markers, try a different
model before assuming something is broken. This is the most common cause of a
disappointing result.

### Using LM Studio or another OpenAI-compatible server

Choose *OpenAI-compatible server* in the setup wizard and give the address,
usually `http://localhost:1234/v1`. Any value will do for the API key; local
servers ignore it.

Two differences from Ollama. Models must be loaded before the API will serve
them — `lms load <model>` for LM Studio — and the server must accept
connections from outside the loopback: `lms server start --bind 0.0.0.0`.

These servers report model names and nothing else, so the split between chat
and embedding models in the wizard is guessed from those names. Correct it if
either is wrong.

---

## Configuration

`config.yaml` holds the inference server, storage paths and retrieval settings.
The setup wizard writes it; `config.yaml.example` documents every key.

Colours and typefaces live in `.streamlit/config.toml`. Four themes ship in
`themes/` and can be switched from the appearance control in the page.

If a theme change does not take effect, use Streamlit's rerun button at the top
right, or restart the server.

---

## Accounts

The first account created is an administrator: it can see every collection,
add documents and create collections. Further accounts can be restricted to
named collections.

Accounts live in a SQLite database on your machine. Passwords are stored as
PBKDF2 hashes. There is no password reset — an administrator sets a new one.

---

## What it does not do

Worth knowing before you install rather than after.

**Summaries cover the opening of a long document, not all of it.** Up to about
12,000 characters is sent to the model, which is roughly the first fifteen
pages of a report. The summary does not always say so.

**One collection is searched at a time.** There is no cross-collection query.

**Uploading is for a handful of documents at a time.** For a directory of
hundreds, index it with a script rather than through the browser.

**It is single-user in practice.** Several people can have accounts, but the
application is not built for concurrent load.

**Scanned documents produce nothing.** There is no OCR. A PDF without a text
layer will index with almost no content, which shows as a very low passage
count beside its name.

---

## Licence

Dual licensed.

**GNU Affero General Public License v3.0** for personal, internal, research and
teaching use, and for anyone willing to publish the source of a modified
version they make available over a network. The full text is in
[LICENSE](LICENSE).

**A commercial licence** is available from Rayar Consulting for organisations
that cannot meet those terms. See [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).

For a good number of enquiries no commercial licence is needed. If you are
unsure, describe your situation and we will tell you plainly.

---

## Contributing

Contributions are welcome. Because the project is dual licensed, a contributor
licence agreement is needed before a change can be merged; it is short and
provided when a pull request is opened.

Bug reports are more useful with the model you were using, since so much
behaviour depends on it.

---

## Built by

[Rayar Consulting](mailto:vinod.krishnan@consultant.com) — strategy, turnaround
and advisory.

Rayar RAG was built to make twelve years of consulting archives searchable, and
released because the problem is not unusual.

© 2026 Rayar Consulting. All rights reserved.
