from pathlib import Path

from snipai.history import MAX_ANSWERS, AnswerHistory


def test_add_keeps_newest_first_and_caps(tmp_path: Path):
    path = tmp_path / "answers.json"
    hist = AnswerHistory(path, max_items=3)
    hist.add("one", "full one")
    hist.add("two", "full two")
    hist.add("three", "full three")
    hist.add("four", "full four")
    assert [e.headline for e in hist.entries] == ["four", "three", "two"]
    reloaded = AnswerHistory(path, max_items=3)
    assert [e.headline for e in reloaded.entries] == ["four", "three", "two"]
    assert reloaded.get(reloaded.entries[0].id).full == "full four"


def test_corrupt_file_starts_empty(tmp_path: Path):
    path = tmp_path / "answers.json"
    path.write_text("{not json", encoding="utf-8")
    hist = AnswerHistory(path)
    assert hist.entries == []


def test_memory_history_does_not_need_path():
    hist = AnswerHistory()
    hist.add("408", "ANSWER: 408")
    assert len(hist.entries) == 1
    assert MAX_ANSWERS >= 10
