from managers.state_manager import StateManager


def test_pending_data_lifecycle_and_clear_state_side_effect():
    manager = StateManager()
    user_id = 1001
    chat_id = 2002

    manager.set_state(user_id, chat_id, "set_ai_rewrite_prompt:9", None, "ai_enhance")
    manager.set_pending_data(user_id, chat_id, {"rule_id": 9, "new_prompt": "hello"})

    assert manager.get_pending_data(user_id, chat_id) == {"rule_id": 9, "new_prompt": "hello"}

    manager.clear_state(user_id, chat_id)

    assert manager.get_state(user_id, chat_id) == (None, None, None)
    assert manager.get_pending_data(user_id, chat_id) is None
