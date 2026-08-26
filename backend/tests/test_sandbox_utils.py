from worker.sandbox import normalize_output


def test_normalize_strips_trailing_newline():
    assert normalize_output("hello\n") == normalize_output("hello")


def test_normalize_strips_trailing_whitespace_per_line():
    assert normalize_output("1 2 3   \n4 5 6\t\n") == "1 2 3\n4 5 6"


def test_normalize_strips_trailing_blank_lines():
    assert normalize_output("a\nb\n\n\n") == normalize_output("a\nb")


def test_normalize_preserves_meaningful_content():
    assert normalize_output("0 1") == "0 1"
    assert normalize_output("0 1") != "1 0"


def test_normalize_handles_windows_line_endings():
    # `str.rstrip()` treats \r as whitespace, so CRLF output (e.g. from a
    # submission run in a Windows-flavored environment) still compares equal
    # to LF-only expected output. This is intentional: we're judging logic,
    # not line-ending discipline.
    assert normalize_output("a\r\nb") == normalize_output("a\nb")
