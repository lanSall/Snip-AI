"""Send a screenshot or typed question to a model and return the solution text."""

from __future__ import annotations

import base64
from typing import Protocol

import httpx

from snipai import SnipError
from snipai.config import Config, prepare_config

USER_PROMPT = (
    "Solve the problem shown in this screenshot. "
    "Put ANSWER on the first line and WHY on the second."
)

ASK_SYSTEM = """You are a concise problem-solver.

The user typed a question. Solve it. Be correct and concise.

Format your reply EXACTLY like this:
ANSWER: <the final answer, as short as possible>
WHY: <one or two sentences>

Do not use markdown."""


class Solver(Protocol):
    def solve(self, png: bytes) -> str: ...

    def ask(self, question: str) -> str: ...


def _b64(png: bytes) -> str:
    return base64.b64encode(png).decode("ascii")


def _data_url(png: bytes) -> str:
    return f"data:image/png;base64,{_b64(png)}"


def _require_question(question: str) -> str:
    text = (question or "").strip()
    if not text:
        raise SnipError("Type a question first.")
    return text


class MockSolver:
    """Used for dry-runs and tests. Does not call a network API."""

    def __init__(self, reply: str | None = None) -> None:
        self.reply = reply or "ANSWER: 42\nWHY: Mock solver is configured (no API key)."

    def solve(self, png: bytes) -> str:
        if not png:
            raise SnipError("Screenshot was empty.")
        return self.reply

    def ask(self, question: str) -> str:
        _require_question(question)
        return self.reply


class OpenAICompatibleSolver:
    def __init__(self, config: Config, client: httpx.Client | None = None) -> None:
        self.config = config
        self.client = client

    def solve(self, png: bytes) -> str:
        user = [
            {"type": "text", "text": USER_PROMPT},
            {
                "type": "image_url",
                "image_url": {"url": _data_url(png)},
            },
        ]
        return self._chat(self.config.system_prompt, user)

    def ask(self, question: str) -> str:
        text = _require_question(question)
        return self._chat(ASK_SYSTEM, [{"type": "text", "text": text}])

    def _chat(self, system: str, user_content: list) -> str:
        key = self.config.resolved_api_key()
        if not key:
            raise SnipError(
                "No API key. Run snip-ai and paste a key in the setup window, "
                "or: snip-ai init --key YOUR_KEY"
            )
        url = f"{self.config.resolved_base_url()}/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        if self.config.provider.lower().strip() == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/snip-ai"
            headers["X-Title"] = "snip-ai"
        payload = {
            "model": self.config.model,
            "max_tokens": 400,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
        }
        if self.config.provider.lower().strip() in {"gemini", "google"}:
            # Flash/Pro "thinking" can exceed a short HTTP timeout on screenshots.
            payload["extra_body"] = {
                "google": {"thinking_config": {"thinking_level": "low"}}
            }
        response = _post(self.client, url, headers=headers, json=payload)
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise SnipError(f"Unexpected API response: {response!r}") from exc
        if not content:
            raise SnipError("The model returned an empty answer.")
        return str(content).strip()


class AnthropicSolver:
    def __init__(self, config: Config, client: httpx.Client | None = None) -> None:
        self.config = config
        self.client = client

    def solve(self, png: bytes) -> str:
        user = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": _b64(png),
                },
            },
            {"type": "text", "text": USER_PROMPT},
        ]
        return self._chat(self.config.system_prompt, user)

    def ask(self, question: str) -> str:
        text = _require_question(question)
        return self._chat(ASK_SYSTEM, [{"type": "text", "text": text}])

    def _chat(self, system: str, user_content: list) -> str:
        key = self.config.resolved_api_key()
        if not key:
            raise SnipError(
                "No API key. Run snip-ai and paste a key in the setup window, "
                "or: snip-ai init --key YOUR_KEY"
            )
        url = f"{self.config.resolved_base_url()}/v1/messages"
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "max_tokens": 400,
            "system": system,
            "messages": [
                {
                    "role": "user",
                    "content": user_content,
                }
            ],
        }
        response = _post(self.client, url, headers=headers, json=payload)
        try:
            blocks = response["content"]
            text_parts = [block.get("text", "") for block in blocks if block.get("type") == "text"]
            content = "\n".join(part for part in text_parts if part).strip()
        except (KeyError, TypeError) as exc:
            raise SnipError(f"Unexpected API response: {response!r}") from exc
        if not content:
            raise SnipError("The model returned an empty answer.")
        return content


class OllamaSolver:
    def __init__(self, config: Config, client: httpx.Client | None = None) -> None:
        self.config = config
        self.client = client

    def solve(self, png: bytes) -> str:
        return self._chat(self.config.system_prompt, USER_PROMPT, images=[_b64(png)])

    def ask(self, question: str) -> str:
        text = _require_question(question)
        return self._chat(ASK_SYSTEM, text)

    def _chat(self, system: str, user_content: str, images: list[str] | None = None) -> str:
        url = f"{self.config.resolved_base_url()}/api/chat"
        message: dict = {"role": "user", "content": user_content}
        if images:
            message["images"] = images
        payload = {
            "model": self.config.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                message,
            ],
        }
        response = _post(self.client, url, headers={"Content-Type": "application/json"}, json=payload)
        try:
            content = response["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise SnipError(f"Unexpected Ollama response: {response!r}") from exc
        if not content:
            raise SnipError("The model returned an empty answer.")
        return str(content).strip()


def _http_timeout() -> httpx.Timeout:
    return httpx.Timeout(connect=20.0, read=180.0, write=60.0, pool=20.0)


def _post(
    client: httpx.Client | None,
    url: str,
    *,
    headers: dict[str, str],
    json: dict,
) -> dict:
    closer = None
    http = client
    if http is None:
        http = httpx.Client(timeout=_http_timeout())
        closer = http
    try:
        response = None
        last_timeout: httpx.TimeoutException | None = None
        for _attempt in range(2):
            try:
                response = http.post(url, headers=headers, json=json)
                last_timeout = None
                break
            except httpx.TimeoutException as exc:
                last_timeout = exc
                continue
            except httpx.HTTPError as exc:
                raise SnipError(f"Could not reach the model API: {exc}") from exc
        if last_timeout is not None:
            raise SnipError(
                "The model took too long to answer. Try Ctrl+Shift+. and snip a smaller "
                "area, or set model to gemini-3.1-flash-lite."
            ) from last_timeout
        assert response is not None
    finally:
        if closer is not None:
            closer.close()
    if response.status_code == 401:
        raise SnipError("API rejected the key (401). Check api_key / OPENAI_API_KEY.")
    if response.status_code >= 400:
        detail = response.text.strip().replace("\n", " ")
        if len(detail) > 300:
            detail = detail[:299] + "…"
        raise SnipError(f"API error {response.status_code}: {detail or response.reason_phrase}")
    try:
        return response.json()
    except ValueError as exc:
        raise SnipError("API did not return JSON.") from exc


def make_solver(config: Config, client: httpx.Client | None = None) -> Solver:
    config = prepare_config(config)
    provider = config.provider.lower().strip()
    if provider == "mock":
        return MockSolver(config.mock_reply or None)
    if provider == "anthropic":
        return AnthropicSolver(config, client=client)
    if provider == "ollama":
        return OllamaSolver(config, client=client)
    if provider in {"openai", "openai_compatible", "openrouter", "gemini", "google"}:
        return OpenAICompatibleSolver(config, client=client)
    raise SnipError(
        f"Unknown provider {config.provider!r}. "
        "Use gemini, openai, anthropic, openrouter, openai_compatible, ollama, or mock."
    )
