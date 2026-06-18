# tests/test_ai_rewrite_prompt_confirmation_flow.py
from handlers import prompt_handlers


def test_prepare_ai_rewrite_prompt_confirmation_payload():
    payload, next_state = prompt_handlers.prepare_ai_rewrite_prompt_confirmation(
        rule_id=9,
        new_prompt="rewrite me"
    )

    assert payload == {
        "rule_id": 9,
        "field_name": "ai_rewrite_prompt",
        "new_prompt": "rewrite me",
        "template_type": "ai_enhance",
    }
    assert next_state == "confirm_ai_rewrite_prompt:9"


import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from handlers.button.callback.ai_callback import (
    callback_confirm_set_ai_rewrite_prompt,
    callback_cancel_confirm_ai_rewrite_prompt,
)


@pytest.mark.asyncio
async def test_confirm_callback_commits_pending_prompt():
    """测试确认回调会提交待确认的提示词"""
    # 创建模拟对象
    event = AsyncMock()
    event.sender_id = 1001
    event.chat_id = -2002
    
    session = MagicMock()
    rule = MagicMock()
    rule.id = 9
    session.query().get.return_value = rule
    
    message = MagicMock()
    data = "confirm_set_ai_rewrite_prompt:9"
    
    # 模拟state_manager
    with patch('handlers.button.callback.ai_callback.state_manager') as mock_state:
        mock_state.get_pending_data.return_value = {
            "rule_id": 9,
            "field_name": "ai_rewrite_prompt",
            "new_prompt": "test prompt",
            "template_type": "ai_enhance",
        }
        
        # 模拟辅助函数
        with patch('handlers.button.callback.ai_callback.get_ai_enhance_settings_text') as mock_text, \
             patch('handlers.button.callback.ai_callback.create_ai_enhance_settings_buttons') as mock_buttons:
            mock_text.return_value = "settings text"
            mock_buttons.return_value = []
            
            # 执行回调
            await callback_confirm_set_ai_rewrite_prompt(event, "9", session, message, data)
            
            # 验证规则被更新
            assert rule.ai_rewrite_prompt == "test prompt"
            # 验证session提交
            session.commit.assert_called_once()
            # 验证状态被清理
            mock_state.clear_state.assert_called_once_with(1001, 2002)
            # 验证消息被编辑
            event.edit.assert_called_once()
            event.answer.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_callback_discards_pending_prompt():
    """测试取消回调会丢弃待确认的提示词"""
    # 创建模拟对象
    event = AsyncMock()
    event.sender_id = 1001
    event.chat_id = -2002
    
    session = MagicMock()
    rule = MagicMock()
    rule.id = 9
    session.query().get.return_value = rule
    
    message = MagicMock()
    data = "cancel_confirm_ai_rewrite_prompt:9"
    
    # 模拟state_manager
    with patch('handlers.button.callback.ai_callback.state_manager') as mock_state:
        # 模拟辅助函数
        with patch('handlers.button.callback.ai_callback.get_ai_enhance_settings_text') as mock_text, \
             patch('handlers.button.callback.ai_callback.create_ai_enhance_settings_buttons') as mock_buttons:
            mock_text.return_value = "settings text"
            mock_buttons.return_value = []
            
            # 执行回调
            await callback_cancel_confirm_ai_rewrite_prompt(event, "9", session, message, data)
            
            # 验证状态被清理
            mock_state.clear_state.assert_called_once_with(1001, 2002)
            # 验证session未提交（没有修改规则）
            session.commit.assert_not_called()
            # 验证消息被编辑回设置页面
            event.edit.assert_called_once()
            event.answer.assert_called_once()


@pytest.mark.asyncio
async def test_close_settings_clears_state_and_pending():
    """测试关闭设置会清理待确认状态和待处理数据"""
    from handlers.button.callback.callback_handlers import callback_close_settings
    
    # 创建模拟对象
    event = AsyncMock()
    event.sender_id = 1001
    event.chat_id = -2002
    
    session = MagicMock()
    message = AsyncMock()
    data = "close_settings"
    
    # 模拟state_manager
    with patch('handlers.button.callback.callback_handlers.state_manager') as mock_state:
        # 执行回调
        await callback_close_settings(event, None, session, message, data)
        
        # 验证状态被清理
        mock_state.clear_state.assert_called_once_with(1001, 2002)
        # 验证消息被删除
        message.delete.assert_called_once()


@pytest.mark.asyncio
async def test_confirm_callback_uses_env_user_id_in_channel_context(monkeypatch):
    """频道场景下应使用 USER_ID 作为状态键。"""
    event = AsyncMock()
    event.sender_id = 5555
    event.chat_id = -3003

    class DummyChannel:
        pass

    event.chat = DummyChannel()

    session = MagicMock()
    rule = MagicMock()
    rule.id = 9
    session.query().get.return_value = rule

    with patch('handlers.button.callback.ai_callback.state_manager') as mock_state, \
         patch('handlers.button.callback.ai_callback.os.getenv', return_value='9999'), \
         patch('handlers.button.callback.ai_callback.types.Channel', DummyChannel), \
         patch('handlers.button.callback.ai_callback.get_ai_enhance_settings_text', return_value='settings text'), \
         patch('handlers.button.callback.ai_callback.create_ai_enhance_settings_buttons', return_value=[]):

        mock_state.get_pending_data.return_value = {
            'rule_id': 9,
            'field_name': 'ai_rewrite_prompt',
            'new_prompt': 'channel prompt',
            'template_type': 'ai_enhance',
        }

        await callback_confirm_set_ai_rewrite_prompt(
            event,
            '9',
            session,
            message=MagicMock(),
            data='confirm_set_ai_rewrite_prompt:9',
        )

        mock_state.get_pending_data.assert_called_once_with('9999', 3003)
        mock_state.clear_state.assert_called_once_with('9999', 3003)


@pytest.mark.asyncio
async def test_close_settings_uses_env_user_id_in_channel_context():
    """频道场景关闭设置时应清理 USER_ID 对应状态。"""
    from handlers.button.callback.callback_handlers import callback_close_settings

    event = AsyncMock()
    event.sender_id = 4444
    event.chat_id = -4004

    class DummyChannel:
        pass

    event.chat = DummyChannel()
    message = AsyncMock()

    with patch('handlers.button.callback.callback_handlers.state_manager') as mock_state, \
         patch('handlers.button.callback.callback_handlers.os.getenv', return_value='8888'), \
         patch('handlers.button.callback.callback_handlers.types.Channel', DummyChannel):

        await callback_close_settings(event, None, MagicMock(), message, 'close_settings')

        mock_state.clear_state.assert_called_once_with('8888', 4004)
        message.delete.assert_called_once()
