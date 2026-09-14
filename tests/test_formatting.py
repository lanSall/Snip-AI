from snipai.formatting import compact, parse_solution, toast_body


def test_parse_answer_and_why():
    headline, full = parse_solution("ANSWER: 408\nWHY: 17 times 24 is 408.")
    assert headline == "408"
    assert "17 times 24" in full


def test_parse_falls_back_to_first_line():
    headline, full = parse_solution("The root cause is a missing import.\nInstall pillow.")
    assert headline == "The root cause is a missing import."
    assert "Install pillow." in full


def test_parse_empty():
    headline, full = parse_solution("   ")
    assert headline == "No answer"
    assert full == ""


def test_compact_truncates():
    assert compact("one two three", max_chars=7) == "one tw…"
    assert compact("short", max_chars=80) == "short"


def test_toast_body_prefers_answer_and_why():
    body = toast_body("ANSWER: 408\nWHY: Multiply 17 by 24.", max_chars=180)
    assert body.startswith("408")
    assert "Multiply" in body
    assert "\n" in body
