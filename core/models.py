"""
models.py — Talking to a local inference server.

Two kinds are supported. Ollama has its own API and reports enough metadata to
tell a chat model from an embedding one. Everything else worth using speaks the
OpenAI API: LM Studio, llama.cpp's server, vLLM, LocalAI. That second case is
one client rather than one integration per tool.

The interface above this file does not know which is underneath. Retrieval,
generation and the tabs call the same two methods either way.

Context length is handled here rather than left to chance. A model's context
window is independent of its parameter count, and a GGUF packaged with four
thousand tokens will refuse a dozen retrieved passages. Ollama accepts an
explicit setting; an OpenAI-compatible server decides for itself. In both cases
the failure is caught and turned into a sentence that names the numbers and
says what to change.
"""

import re
from typing import Optional

# Fragments that mark an embedding model when no better signal exists.
# Used only for OpenAI-compatible servers, which report names and nothing else.
EMBED_NAME_MARKERS = (
    "embed", "embedding", "bge", "gte", "e5-", "minilm", "nomic", "mxbai",
)

# Model families Ollama reports for embedding models. Preferred over name
# matching, which misfires on anything with "e5" or "bge" inside its name.
EMBED_FAMILIES = {"bert", "nomic-bert", "xlm-roberta", "gemma2-embed"}


class ContextTooSmall(Exception):
    """
    The prompt did not fit the model's context window.

    Carries the numbers so the caller can say what to change rather than
    reporting that something went wrong.
    """

    def __init__(self, sent: Optional[int], available: Optional[int], model: str):
        self.sent = sent
        self.available = available
        self.model = model
        super().__init__(str(self))

    def __str__(self) -> str:
        if self.sent and self.available:
            return (
                f"{self.model} has room for {self.available:,} tokens and the "
                f"request came to {self.sent:,}. Retrieve fewer passages by "
                f"lowering retrieval.top_k, raise backend.num_ctx if the model "
                f"supports it, or use a model with a larger context window."
            )
        return (
            f"The request was too long for {self.model}. Lower "
            f"retrieval.top_k, or use a model with a larger context window."
        )


def _context_error(text: str) -> Optional[tuple[Optional[int], Optional[int]]]:
    """
    Recognise a context-length failure and pull the numbers out.

    Servers word this differently, so the match is on the shape rather than an
    exact phrase. Returns None when the error is something else.
    """
    lowered = text.lower()
    markers = (
        "exceed_context_size", "context_length_exceeded",
        "exceeds the available context", "maximum context length",
        "too many tokens", "context window", "context length",
    )
    if not any(m in lowered for m in markers):
        return None

    sent = available = None
    for pattern, target in (
        (r'"?n_prompt_tokens"?\s*[:=]\s*(\d+)', "sent"),
        (r'"?n_ctx"?\s*[:=]\s*(\d+)', "available"),
        (r"\((\d+) tokens\) exceeds", "sent"),
        (r"context size \((\d+) tokens\)", "available"),
        (r"maximum context length is (\d+)", "available"),
        (r"you requested (\d+)", "sent"),
        (r"context length of (\d+)", "available"),
    ):
        found = re.search(pattern, text)
        if found:
            if target == "sent" and sent is None:
                sent = int(found.group(1))
            elif target == "available" and available is None:
                available = int(found.group(1))
    return sent, available


class Backend:
    """What every inference server must provide."""

    def __init__(self, url: str, num_ctx: Optional[int] = None):
        self.url = url
        self.num_ctx = num_ctx

    def is_reachable(self) -> bool:
        raise NotImplementedError

    def all_models(self) -> list[str]:
        raise NotImplementedError

    def chat_models(self) -> list[str]:
        raise NotImplementedError

    def embed_models(self) -> list[str]:
        raise NotImplementedError

    def chat(self, model: str, prompt: str, temperature: float = 0.3,
             num_predict: int = 1000, think: Optional[bool] = None) -> str:
        raise NotImplementedError

    def embed(self, model: str, text: str) -> list[float]:
        raise NotImplementedError

    def unload(self, model: str) -> None:
        """Free a model from memory. Not every server supports this."""
        return


class OllamaBackend(Backend):
    """Ollama's own API."""

    name = "Ollama"

    def __init__(self, url: str, keep_alive: str = "5m",
                 num_ctx: Optional[int] = None):
        super().__init__(url, num_ctx)
        import ollama
        self.keep_alive = keep_alive
        self._client = ollama.Client(host=url)

    def is_reachable(self) -> bool:
        try:
            self._client.list()
            return True
        except Exception:
            return False

    def _details(self) -> dict[str, str]:
        """Model name to family, as Ollama reports it."""
        try:
            return {
                m.model: (m.details.family or "").lower()
                for m in self._client.list().models
            }
        except Exception:
            return {}

    def _is_embed(self, name: str, family: str) -> bool:
        if family in EMBED_FAMILIES:
            return True
        return family == "" and "embed" in name.lower()

    def all_models(self) -> list[str]:
        return list(self._details().keys())

    def chat_models(self) -> list[str]:
        return [n for n, f in self._details().items() if not self._is_embed(n, f)]

    def embed_models(self) -> list[str]:
        return [n for n, f in self._details().items() if self._is_embed(n, f)]

    def chat(self, model: str, prompt: str, temperature: float = 0.3,
             num_predict: int = 1000, think: Optional[bool] = None) -> str:
        options = {"temperature": temperature, "num_predict": num_predict}
        if self.num_ctx:
            options["num_ctx"] = self.num_ctx

        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "options": options,
            "keep_alive": self.keep_alive,
        }
        if think is not None:
            kwargs["think"] = think

        try:
            response = self._client.chat(**kwargs)
        except Exception as e:
            numbers = _context_error(str(e))
            if numbers:
                raise ContextTooSmall(numbers[0], numbers[1], model) from None
            raise

        content = response["message"]["content"] or ""
        return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    def embed(self, model: str, text: str) -> list[float]:
        clean = text.encode("utf-8", errors="replace").decode("utf-8")
        return self._client.embeddings(model=model, prompt=clean)["embedding"]

    def unload(self, model: str) -> None:
        try:
            self._client.generate(model=model, prompt="", keep_alive=0)
        except Exception:
            pass


class OpenAIBackend(Backend):
    """
    Any server speaking the OpenAI API: LM Studio, llama.cpp, vLLM, LocalAI.

    These report model names and nothing else, so a chat model can only be told
    from an embedding one by its name. That is guesswork, and it is why the
    setup step asks the person to confirm rather than deciding silently.
    """

    name = "OpenAI-compatible"

    def __init__(self, url: str, api_key: str = "not-needed",
                 num_ctx: Optional[int] = None):
        super().__init__(url.rstrip("/"), num_ctx)
        self.api_key = api_key or "not-needed"

    def _request(self, path: str, payload: Optional[dict] = None,
                 timeout: int = 180) -> dict:
        import json
        import urllib.request

        request = urllib.request.Request(
            f"{self.url}{path}",
            data=json.dumps(payload).encode() if payload else None,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST" if payload else "GET",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode())

    def is_reachable(self) -> bool:
        try:
            self._request("/models", timeout=10)
            return True
        except Exception:
            return False

    def all_models(self) -> list[str]:
        try:
            return [m["id"] for m in self._request("/models", timeout=10)["data"]]
        except Exception:
            return []

    def _is_embed(self, name: str) -> bool:
        return any(marker in name.lower() for marker in EMBED_NAME_MARKERS)

    def chat_models(self) -> list[str]:
        return [m for m in self.all_models() if not self._is_embed(m)]

    def embed_models(self) -> list[str]:
        return [m for m in self.all_models() if self._is_embed(m)]

    def chat(self, model: str, prompt: str, temperature: float = 0.3,
             num_predict: int = 1000, think: Optional[bool] = None) -> str:
        # `think` is an Ollama setting and is not sent here.
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": num_predict,
        }
        try:
            result = self._request("/chat/completions", payload)
        except Exception as e:
            detail = getattr(e, "read", lambda: b"")()
            text = detail.decode(errors="replace") if detail else str(e)
            numbers = _context_error(text)
            if numbers:
                raise ContextTooSmall(numbers[0], numbers[1], model) from None
            raise RuntimeError(text[:400]) from None

        content = result["choices"][0]["message"]["content"] or ""
        return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    def embed(self, model: str, text: str) -> list[float]:
        clean = text.encode("utf-8", errors="replace").decode("utf-8")
        result = self._request("/embeddings", {"model": model, "input": clean})
        return result["data"][0]["embedding"]


def create(cfg) -> Backend:
    """
    Build the backend named in the configuration.

    Reads the backend section, falling back to the older ollama section so an
    installation made before this existed keeps working.
    """
    kind = cfg.get("backend.type") or "ollama"
    num_ctx = cfg.get("backend.num_ctx")

    if kind == "openai-compatible":
        return OpenAIBackend(
            cfg.get("backend.url", "http://localhost:1234/v1"),
            cfg.get("backend.api_key", "not-needed"),
            num_ctx,
        )

    return OllamaBackend(
        cfg.get("backend.url") or cfg.get("ollama.url", "http://localhost:11434"),
        cfg.get("backend.keep_alive") or cfg.get("ollama.keep_alive", "5m"),
        num_ctx,
    )


# The previous name, so existing imports keep working.
OllamaClient = OllamaBackend
