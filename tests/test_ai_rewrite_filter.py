import types
from unittest.mock import AsyncMock, patch

import pytest

from filters.ai_rewrite_filter import AIRewriteFilter


@pytest.mark.asyncio
async def test_ai_rewrite_keeps_original_when_provider_returns_error_text():
    filter_obj = AIRewriteFilter()

    rule = types.SimpleNamespace(
        enable_ai_rewrite=True,
        ai_rewrite_model="llama-3.3-70b-versatile",
        ai_rewrite_prompt="rewrite prompt",
    )
    context = types.SimpleNamespace(
        rule=rule,
        message_text="原始内容",
    )

    fake_provider = AsyncMock()
    fake_provider.process_message.return_value = "AI处理失败: Error code: 403 - {'error': {'message': 'Forbidden'}}"

    with patch("filters.ai_rewrite_filter.get_ai_provider", new=AsyncMock(return_value=fake_provider)):
        should_continue = await filter_obj._process(context)

    assert should_continue is True
    assert context.message_text == "原始内容"
