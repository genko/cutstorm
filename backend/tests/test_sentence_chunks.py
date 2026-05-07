from app.models import Word
from app.sentence_chunks import chunks_by_sentence


def W(text: str, t: float = 0.0) -> Word:
    return Word(start=t, end=t + 0.1, text=text)


def texts(chunks: list[list[Word]]) -> list[list[str]]:
    return [[w.text for w in c] for c in chunks]


def test_empty():
    assert chunks_by_sentence([], 4) == []


def test_no_punctuation_chunks_by_size():
    ws = [W(f"w{i}") for i in range(5)]
    assert [len(c) for c in chunks_by_sentence(ws, 4)] == [4, 1]


def test_period_breaks_chunk_early():
    ws = [W("Hello"), W("world."), W("Foo"), W("bar"), W("baz")]
    assert texts(chunks_by_sentence(ws, 4)) == [
        ["Hello", "world."],
        ["Foo", "bar", "baz"],
    ]


def test_question_mark_breaks():
    ws = [W("How"), W("are"), W("you?"), W("Fine"), W("thanks")]
    assert texts(chunks_by_sentence(ws, 4)) == [
        ["How", "are", "you?"],
        ["Fine", "thanks"],
    ]


def test_exclamation_breaks():
    ws = [W("Hi!"), W("Wow!"), W("Done")]
    assert texts(chunks_by_sentence(ws, 4)) == [
        ["Hi!"],
        ["Wow!"],
        ["Done"],
    ]


def test_unicode_ellipsis_breaks():
    ws = [W("Wait…"), W("really")]
    assert texts(chunks_by_sentence(ws, 4)) == [["Wait…"], ["really"]]


def test_three_dot_ellipsis_breaks():
    ws = [W("Wait..."), W("really")]
    assert texts(chunks_by_sentence(ws, 4)) == [["Wait..."], ["really"]]


def test_long_sentence_still_chunks_by_size():
    ws = [W(f"w{i}") for i in range(10)]
    assert [len(c) for c in chunks_by_sentence(ws, 4)] == [4, 4, 2]


def test_period_at_end_no_extra_empty_chunk():
    assert texts(chunks_by_sentence([W("End.")], 4)) == [["End."]]


def test_chunk_size_zero_treated_as_one():
    ws = [W("a"), W("b"), W("c")]
    assert [len(c) for c in chunks_by_sentence(ws, 0)] == [1, 1, 1]


def test_trailing_whitespace_after_period():
    ws = [W("End. "), W("New")]
    assert texts(chunks_by_sentence(ws, 4)) == [["End. "], ["New"]]


def test_comma_does_not_break():
    ws = [W("Hi,"), W("you,"), W("ok")]
    assert texts(chunks_by_sentence(ws, 4)) == [["Hi,", "you,", "ok"]]


def test_size_break_and_sentence_break_compose():
    # 5 words, chunk=2, period after 3rd word.
    # Step-by-step: [w0,w1] (size break) -> [w2.] (sentence break) -> [w3,w4]
    ws = [W("a"), W("b"), W("c."), W("d"), W("e")]
    assert texts(chunks_by_sentence(ws, 2)) == [
        ["a", "b"],
        ["c."],
        ["d", "e"],
    ]
