import json

import httpx

from snipai import SnipError
from snipai.config import Config
from snipai.solver import AnthropicSolver, MockSolver, OllamaSolver, OpenAICompatibleSolver, make_solver


def test_mock_solver_rejects_empty():
    try:
        MockSolver().solve(b"")
        assert False, "expected SnipError"
    except SnipError as exc:
        assert "empty" in str(exc).lower()


def test_mock_solver_returns_reply(tiny_png: bytes):
    assert "42" in MockSolver().solve(tiny_png)


def test_mock_solver_ask_rejects_empty():
    try:
        MockSolver().ask("  ")
        assert False, "expected SnipError"
    except SnipError as exc:
        assert "question" in str(exc).lower()


def test_mock_solver_ask_returns_reply():
    assert "42" in MockSolver().ask("What is the answer?")


def test_make_solver_mock_custom_reply(tiny_png: bytes):
    solver = make_solver(Config(provider="mock", mock_reply="ANSWER: 408\nWHY: 17 times 24."))
    assert solver.solve(tiny_png).startswith("ANSWER: 408")


def test_make_solver_unknown_provider():
    try:
        make_solver(Config(provider="nope"))
        assert False, "expected SnipError"
    except SnipError as exc:
        assert "Unknown provider" in str(exc)


def test_openai_solver_sends_image(tiny_png: bytes):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.read()
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ANSWER: 408\nWHY: 17*24."}}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    solver = OpenAICompatibleSolver(
        Config(provider="openai", api_key="sk-test", model="gpt-4o"),
        client=client,
    )
    answer = solver.solve(tiny_png)
    assert answer.startswith("ANSWER: 408")
    assert "chat/completions" in captured["url"]
    assert b"data:image/png;base64," in captured["body"]


def test_openai_401(tiny_png: bytes):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="nope")

    solver = OpenAICompatibleSolver(
        Config(provider="openai", api_key="bad", model="gpt-4o"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    try:
        solver.solve(tiny_png)
        assert False, "expected SnipError"
    except SnipError as exc:
        assert "401" in str(exc)


def test_anthropic_solver(tiny_png: bytes):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "sk-ant"
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "ANSWER: 4\nWHY: 2+2."}]},
        )

    solver = AnthropicSolver(
        Config(provider="anthropic", api_key="sk-ant", model="claude-sonnet-4-5"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert "ANSWER: 4" in solver.solve(tiny_png)


def test_openai_requires_key(tiny_png: bytes, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SNIPAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    solver = OpenAICompatibleSolver(Config(provider="openai", api_key=""))
    try:
        solver.solve(tiny_png)
        assert False, "expected SnipError"
    except SnipError as exc:
        assert "API key" in str(exc)


def test_gemini_solver_uses_google_openai_url(tiny_png: bytes):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = request.read()
        return httpx.Response(200, json={"choices": [{"message": {"content": "ANSWER: 1"}}]})

    solver = make_solver(
        Config(provider="gemini", api_key="AIza-test", model="gemini-3.1-pro-preview"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert solver.solve(tiny_png).startswith("ANSWER: 1")
    assert "generativelanguage.googleapis.com" in captured["url"]
    assert captured["url"].rstrip("/").endswith("chat/completions")
    assert captured["auth"] == "Bearer AIza-test"
    assert b"thinking_level" in captured["body"]


def test_timeout_retries_then_explains(tiny_png: bytes):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ReadTimeout("The read operation timed out")

    solver = OpenAICompatibleSolver(
        Config(provider="openai", api_key="sk-test", model="gpt-4o"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    try:
        solver.solve(tiny_png)
        assert False, "expected SnipError"
    except SnipError as exc:
        assert "too long" in str(exc).lower()
    assert calls["n"] == 2


def test_openai_ask_is_text_only():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.read())
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ANSWER: 4\nWHY: 2+2."}}]},
        )

    solver = OpenAICompatibleSolver(
        Config(provider="openai", api_key="sk-test", model="gpt-4o"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    answer = solver.ask("What is 2+2?")
    assert answer.startswith("ANSWER: 4")
    blob = json.dumps(captured["body"])
    assert "2+2" in blob
    assert "image_url" not in blob
    assert "data:image/png" not in blob
    system = captured["body"]["messages"][0]["content"]
    assert "typed a question" in system.lower()


def test_gemini_ask_keeps_thinking_and_skips_image():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(200, json={"choices": [{"message": {"content": "ANSWER: 1"}}]})

    solver = make_solver(
        Config(provider="gemini", api_key="AIza-test", model="gemini-3.8-flash"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert solver.ask("Name a number.").startswith("ANSWER: 1")
    assert b"thinking_level" in captured["body"]
    assert b"data:image/png" not in captured["body"]
    assert b"Name a number." in captured["body"]


def test_anthropic_ask_is_text_only():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.read())
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "ANSWER: 4\nWHY: 2+2."}]},
        )

    solver = AnthropicSolver(
        Config(provider="anthropic", api_key="sk-ant", model="claude-sonnet-4-5"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert "ANSWER: 4" in solver.ask("What is 2+2?")
    content = captured["body"]["messages"][0]["content"]
    assert content == [{"type": "text", "text": "What is 2+2?"}]
    assert "typed a question" in captured["body"]["system"].lower()


def test_ollama_ask_is_text_only():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.read())
        return httpx.Response(200, json={"message": {"content": "ANSWER: 4"}})

    solver = OllamaSolver(
        Config(provider="ollama", model="llama3.2-vision"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert "ANSWER: 4" in solver.ask("What is 2+2?")
    user = captured["body"]["messages"][1]
    assert user["content"] == "What is 2+2?"
    assert "images" not in user


def test_openai_ask_requires_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SNIPAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    solver = OpenAICompatibleSolver(Config(provider="openai", api_key=""))
    try:
        solver.ask("Hello?")
        assert False, "expected SnipError"
    except SnipError as exc:
        assert "API key" in str(exc)
