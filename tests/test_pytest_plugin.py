"""Tests for the agentcassette pytest plugin (via the `pytester` fixture).

Each test generates an inner test file, runs pytest on it in-process, and
asserts on the outcome. A sentinel log file records every *real* call so we
can prove replay never touches the wrapped function.
"""


def test_records_then_replays(pytester, monkeypatch):
    sentinel = pytester.path / "calls.log"
    monkeypatch.setenv("AC_SENTINEL", str(sentinel))
    pytester.makepyfile(
        test_inner='''
        import os, agentcassette

        @agentcassette.intercept(kind="llm")
        def call(prompt):
            with open(os.environ["AC_SENTINEL"], "a") as f:
                f.write("x")
            return {"echo": prompt}

        def test_agent(cassette):
            assert call("hi") == {"echo": "hi"}
        '''
    )
    # First run: records — the real function runs once.
    r1 = pytester.runpytest()
    r1.assert_outcomes(passed=1)
    assert sentinel.read_text() == "x"
    cassettes = list((pytester.path / "cassettes").glob("*.json"))
    assert len(cassettes) == 1

    # Second run: replays — the real function must NOT run again.
    r2 = pytester.runpytest()
    r2.assert_outcomes(passed=1)
    assert sentinel.read_text() == "x"


def test_record_mode_none_missing_cassette_fails(pytester):
    pytester.makepyfile(
        test_inner='''
        import agentcassette

        @agentcassette.intercept
        def call(prompt):
            return {"echo": prompt}

        def test_agent(cassette):
            call("hi")
        '''
    )
    result = pytester.runpytest("--record-mode=none")
    assert result.ret != 0
    result.stdout.fnmatch_lines(["*no cassette*record-mode=none*"])


def test_record_mode_all_rerecords(pytester, monkeypatch):
    sentinel = pytester.path / "calls.log"
    monkeypatch.setenv("AC_SENTINEL", str(sentinel))
    pytester.makepyfile(
        test_inner='''
        import os, agentcassette

        @agentcassette.intercept
        def call(prompt):
            with open(os.environ["AC_SENTINEL"], "a") as f:
                f.write("x")
            return {"echo": prompt}

        def test_agent(cassette):
            call("hi")
        '''
    )
    pytester.runpytest().assert_outcomes(passed=1)      # records (1 real call)
    assert sentinel.read_text() == "x"
    pytester.runpytest("--record-mode=all").assert_outcomes(passed=1)  # re-records
    assert sentinel.read_text() == "xx"                 # real function ran again


def test_strict_marker_detects_divergence(pytester, monkeypatch):
    pytester.makepyfile(
        test_inner='''
        import os, pytest, agentcassette

        @agentcassette.intercept
        def call(prompt):
            return {"echo": prompt}

        @pytest.mark.cassette(strict=True)
        def test_agent(cassette):
            call(os.environ["AC_PROMPT"])
        '''
    )
    monkeypatch.setenv("AC_PROMPT", "first")
    pytester.runpytest().assert_outcomes(passed=1)       # record with "first"
    monkeypatch.setenv("AC_PROMPT", "different")
    result = pytester.runpytest()                        # replay strict → diverge
    assert result.ret != 0


def test_custom_path_marker(pytester):
    pytester.makepyfile(
        test_inner='''
        import pytest, agentcassette

        @agentcassette.intercept
        def call(prompt):
            return {"echo": prompt}

        @pytest.mark.cassette(path="tapes/custom.json")
        def test_agent(cassette):
            call("hi")
        '''
    )
    pytester.runpytest().assert_outcomes(passed=1)
    assert (pytester.path / "tapes" / "custom.json").exists()


def test_fixture_yields_player_with_divergences_on_replay(pytester, monkeypatch):
    pytester.makepyfile(
        test_inner='''
        import os, agentcassette

        @agentcassette.intercept
        def call(prompt):
            return {"echo": prompt}

        def test_agent(cassette):
            call(os.environ["AC_PROMPT"])
            # On the replay run, `cassette` is a Player; assert we can read it.
            if hasattr(cassette, "divergences"):
                assert isinstance(cassette.divergences, list)
        '''
    )
    monkeypatch.setenv("AC_PROMPT", "first")
    pytester.runpytest().assert_outcomes(passed=1)   # record
    monkeypatch.setenv("AC_PROMPT", "first")
    pytester.runpytest().assert_outcomes(passed=1)   # replay, player readable
