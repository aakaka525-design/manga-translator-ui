from __future__ import annotations

import asyncio
from contextvars import copy_context

from manga_translator.translators.common import CommonTranslator


class _DummyTranslator(CommonTranslator):
    async def _translate(self, from_lang, to_lang, queries, use_mtpe: bool = False):  # noqa: ARG002
        return list(queries)


def test_attempt_state_is_isolated_between_contexts():
    translator = _DummyTranslator()
    translator.attempts = 2

    main_ctx = copy_context()
    peer_ctx = copy_context()

    def _main_setup():
        translator._reset_global_attempt_count()
        assert translator._increment_global_attempt() is True
        return translator._global_attempt_count, translator._max_total_attempts

    assert main_ctx.run(_main_setup) == (1, 2)

    def _peer_flow():
        translator._reset_global_attempt_count()
        assert translator._increment_global_attempt() is True
        assert translator._increment_global_attempt() is True
        assert translator._increment_global_attempt() is False
        return translator._global_attempt_count, translator._max_total_attempts

    assert peer_ctx.run(_peer_flow) == (2, 2)

    def _main_verify():
        return translator._global_attempt_count, translator._max_total_attempts

    # Peer context updates must not overwrite main context counter.
    assert main_ctx.run(_main_verify) == (1, 2)


def test_translate_with_split_uses_local_attempt_state():
    translator = _DummyTranslator()
    translator.attempts = 2

    main_ctx = copy_context()
    peer_ctx = copy_context()

    def _main_setup():
        translator._reset_global_attempt_count()
        assert translator._increment_global_attempt() is True

    main_ctx.run(_main_setup)

    def _peer_exhaust():
        translator._reset_global_attempt_count()
        translator._increment_global_attempt()
        translator._increment_global_attempt()

    peer_ctx.run(_peer_exhaust)

    async def _translate_identity():
        async def _translator_func(texts, **_kwargs):
            return texts

        return await translator._translate_with_split(_translator_func, ["hello"])

    assert main_ctx.run(asyncio.run, _translate_identity()) == ["hello"]


def test_increment_allows_first_attempt_when_limit_is_one():
    translator = _DummyTranslator()
    translator.attempts = 1
    translator._reset_global_attempt_count()

    assert translator._global_attempt_count == 0
    assert translator._max_total_attempts == 1

    # attempts=1 should still allow exactly one real request.
    assert translator._increment_global_attempt() is True
    assert translator._global_attempt_count == 1

    # second attempt should be rejected.
    assert translator._increment_global_attempt() is False


def test_translate_with_split_allows_single_attempt_limit():
    translator = _DummyTranslator()
    translator.attempts = 1
    translator._reset_global_attempt_count()

    calls = {"count": 0}

    async def _translator_func(texts, **_kwargs):
        if not translator._increment_global_attempt():
            raise RuntimeError("attempt limit reached before request")
        calls["count"] += 1
        return texts

    async def _run():
        result = await translator._translate_with_split(_translator_func, ["hello"])
        return result, translator._global_attempt_count

    result, attempt_count = asyncio.run(_run())

    assert result == ["hello"]
    assert calls["count"] == 1
    assert attempt_count == 1
