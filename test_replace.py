#!/usr/bin/env python3
"""
测试替换规则功能
"""

import re

def test_replace(text, pattern, content):
    """测试替换功能"""
    print(f"原始文本: {repr(text)}")
    print(f"替换模式: {repr(pattern)}")
    print(f"替换内容: {repr(content)}")
    
    try:
        result = re.sub(pattern, content or '', text)
        print(f"替换结果: {repr(result)}")
        print(f"是否改变: {result != text}")
        return result
    except re.error as e:
        print(f"正则错误: {e}")
        return text

print("=" * 60)
print("测试替换规则")
print("=" * 60)
print()

# 测试1: 简单的 @username 替换
print("测试1: @tx188 → @tgxiunv")
test_text = "这是一个测试消息 @tx188 请关注"
test_replace(test_text, "@tx188", "@tgxiunv")
print()

# 测试2: 包含其他字符的情况
print("测试2: 消息中包含多个@")
test_text = "联系 @tx188 或者 @other 获取更多信息"
test_replace(test_text, "@tx188", "@tgxiunv")
print()

# 测试3: @在开头
print("测试3: @在消息开头")
test_text = "@tx188 发布了新消息"
test_replace(test_text, "@tx188", "@tgxiunv")
print()

# 测试4: @在结尾
print("测试4: @在消息结尾")
test_text = "请关注 @tx188"
test_replace(test_text, "@tx188", "@tgxiunv")
print()

# 测试5: 特殊字符转义
print("测试5: 需要转义的特殊字符")
test_text = "访问 https://t.me/tx188 获取信息"
test_replace(test_text, "https://t.me/tx188", "https://t.me/tgxiunv")
print()

# 测试6: 替换为带方括号的版本
print("测试6: @tx188 → [@tgxiunv]")
test_text = "联系 @tx188 获取信息"
test_replace(test_text, "@tx188", "[@tgxiunv]")
print()

print("=" * 60)
print("结论:")
print("如果上述测试都正常替换，说明正则表达式本身没问题。")
print("如果实际使用中仍不生效，可能是以下原因:")
print("1. 消息文本获取不正确（使用了错误的属性）")
print("2. 替换后的文本没有正确发送")
print("3. Telegram的消息实体（entities）影响了显示")
print("=" * 60)

