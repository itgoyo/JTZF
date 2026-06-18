# AI改写提示词确认提交流程设计

日期: 2026-06-18  
范围: 在不改动其他业务代码前提下，修复 AI 改写提示词被误写入的问题，并新增确认/取消提交流程。

## 1. 背景与问题

当前行为中，用户点击“设置AI改写提示词”后，只要系统状态存在，后续收到的文本可能被直接当作提示词写入数据库。

这会导致两个问题:
1. 用户关闭设置窗口后，状态仍残留，监听转发过来的消息可能被误当作提示词。
2. 用户发送提示词后立即写库，缺少“确认/取消”步骤，交互不符合预期。

## 2. 目标

1. 将 AI 改写提示词设置改为两阶段提交: 输入 -> 确认 -> 落库。
2. 关闭设置窗口后，必须清理提示词输入相关状态，避免串扰。
3. 仅对 AI 改写提示词链路做最小改动，不调整转发处理逻辑、不改数据库结构。

## 3. 非目标

1. 不改 AI 去广告提示词提交流程。
2. 不改其他模板/提示词流程。
3. 不调整规则同步、模型选择、转发过滤、调度逻辑。

## 4. 方案选型

已评估三种路径:
1. 两阶段提交状态机（推荐）
2. 仅加输入来源校验与关闭清状态
3. 独立临时缓存，不扩展主状态

最终选择方案 1，原因:
1. 完整满足“用户设置后需确认/取消”需求。
2. 从机制上消除误写风险，而不是只靠条件拦截。
3. 改动集中于状态、回调、提示词处理，边界清晰。

## 5. 设计总览

### 5.1 状态模型

沿用现有 `state_manager`，新增 pending 数据能力，用于缓存待确认内容。

状态阶段:
1. 输入态: `set_ai_rewrite_prompt:{rule_id}`
2. 待确认态: `confirm_ai_rewrite_prompt:{rule_id}`

pending 数据内容:
1. `rule_id`
2. `field_name` 固定为 `ai_rewrite_prompt`
3. `new_prompt` 用户输入的新提示词
4. `template_type` 固定为 `ai_enhance`

键维度保持现有设计: `(user_id, chat_id)`。

### 5.2 交互流程

1. 用户点击“设置AI改写提示词”
2. 进入输入态，显示当前提示词和“取消”按钮
3. 用户发送新提示词文本
4. 系统仅缓存 pending，不写数据库
5. 系统切换到待确认态并返回预览消息，按钮为“确定/取消”
6. 用户点“确定”才写数据库并清理状态
7. 用户点“取消”丢弃 pending 并清理状态
8. 返回 AI 增强设置页面

### 5.3 关闭行为修复

`close_settings` 回调从“仅删除消息”改为:
1. 清理当前用户当前聊天的状态
2. 清理对应 pending 缓存
3. 删除设置消息

保证用户关闭窗口后不会残留输入态。

## 6. 代码改动点

### 6.1 `managers/state_manager.py`

新增方法:
1. `set_pending_data(user_id, chat_id, data)`
2. `get_pending_data(user_id, chat_id)`
3. `clear_pending_data(user_id, chat_id)`

并在 `clear_state` 中联动清理 pending 数据。

### 6.2 `handlers/prompt_handlers.py`

在 `handle_prompt_setting` 中调整 `set_ai_rewrite_prompt` 分支:
1. 收到输入文本时不再直接 `setattr + commit`
2. 改为写入 pending 并切换状态为 `confirm_ai_rewrite_prompt:{rule_id}`
3. 发送确认消息（预览 + 确定/取消按钮）

新增对待确认态的处理入口可选两种方式之一:
1. 在回调里提交，`prompt_handlers` 只负责输入阶段
2. 或在 `prompt_handlers` 识别 confirm 文本指令（本方案采用回调提交）

### 6.3 `handlers/button/callback/ai_callback.py`

新增回调:
1. `callback_confirm_set_ai_rewrite_prompt`
2. `callback_cancel_confirm_ai_rewrite_prompt`

确认回调逻辑:
1. 校验规则存在
2. 读取 pending，校验字段与 rule_id 一致
3. 写入 `rule.ai_rewrite_prompt`
4. 提交事务
5. 清状态与 pending
6. 返回 AI 增强设置页

取消回调逻辑:
1. 清状态与 pending
2. 返回 AI 增强设置页

补强现有 `callback_cancel_set_ai_enhance`:
1. 明确同时清理 pending

### 6.4 `handlers/button/callback/callback_handlers.py`

1. 在 `CALLBACK_HANDLERS` 注册两个新回调 action。
2. 修改 `callback_close_settings`，在删消息前执行状态与 pending 清理。

## 7. 数据流与一致性

### 7.1 正常流

输入文本 -> pending 缓存 -> 用户确认 -> 数据库写入 -> 状态清理。

### 7.2 取消流

输入文本 -> pending 缓存 -> 用户取消 -> 不写库 -> 状态清理。

### 7.3 关闭流

任意输入阶段 -> 点击关闭 -> 不写库 -> 状态与 pending 清理。

## 8. 异常与边界处理

1. pending 缺失: 提示“待确认内容不存在，请重新设置”，不写库。
2. 规则不存在: 提示“规则不存在”，清理状态与 pending。
3. 数据库提交异常: rollback，提示失败，清理状态避免重复提交。
4. 超时取消: 保持 5 分钟超时，超时时清状态并清 pending。
5. 重入场景: 同用户同 chat 新输入覆盖旧 pending，以最后一次输入为准。

## 9. 验收标准

1. 正向流程: 输入后必须先看到“确定/取消”，点确定后才更新提示词。
2. 取消流程: 点取消后提示词值不变。
3. 关闭防串扰: 关闭设置窗口后，监听转发消息不再写入提示词。
4. 超时流程: 超时后发送普通消息不触发提示词保存。
5. 并发重入: 连续输入多次后，仅确认的那一次写入。

## 10. 回归检查范围

1. AI 增强设置页渲染正常。
2. AI 改写提示词设置按钮可正常进入输入态。
3. `close_settings` 在其他设置页面仍可正常关闭消息。
4. 其他命令与转发链路行为不变。

## 11. 风险与回退

风险:
1. 新增 pending 结构若清理不完整，可能引入旧数据残留。
2. 回调 action 命名冲突会导致按钮无响应。

缓解:
1. `clear_state` 联动 `clear_pending_data`。
2. 所有确认回调前做 pending 校验，失败即终止写库。

回退:
1. 仅涉及状态与提示词回调，回退为移除确认分支并恢复原 direct-commit 逻辑。

## 12. 实施清单

1. 扩展 `state_manager` pending 能力。
2. 改造 AI 改写提示词输入为“缓存+确认消息”。
3. 新增确认/取消回调并注册。
4. 修复 `close_settings` 的状态清理。
5. 自测验收标准 1-5。
