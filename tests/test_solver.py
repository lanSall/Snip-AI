import httpx

from snipai import SnipError
from snipai.config import Config
from snipai.solver import AnthropicSolver, MockSolver, OpenAICompatibleSolver, make_solver


def test_mock_solver_rejects_empty():
    try:
        MockSolver().solve(b"")
        assert False, "expected SnipError"
    except SnipError as exc:
        assert "empty" in str(exc).lower()


def test_mock_solver_returns_reply(tiny_png: bytes):
    assert "42" in MockSolver().solve(tiny_png)


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
        return httpx.Response(200, json={"choices": [{"message": {"content": "ANSWER: 1"}}]})

    solver = make_solver(
        Config(provider="gemini", api_key="AIza-test", model="gemini-3.1-pro-preview"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert solver.solve(tiny_png).startswith("ANSWER: 1")
    assert "generativelanguage.googleapis.com" in captured["url"]
    assert captured["url"].rstrip("/").endswith("chat/completions")
    assert captured["auth"] == "Bearer AIza-test"
