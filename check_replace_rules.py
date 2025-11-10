#!/usr/bin/env python3
"""
诊断替换规则配置的脚本
用于检查为什么替换规则不生效
"""

from models.models import get_session, ForwardRule, Chat
from sqlalchemy.orm import joinedload

def check_replace_rules():
    """检查所有规则的替换规则配置"""
    session = get_session()
    try:
        # 查询所有规则，预加载相关数据
        rules = session.query(ForwardRule).options(
            joinedload(ForwardRule.source_chat),
            joinedload(ForwardRule.target_chat),
            joinedload(ForwardRule.replace_rules)
        ).all()
        
        if not rules:
            print("❌ 没有找到任何转发规则")
            print("请先使用 /bind 命令创建转发规则")
            return
        
        print("=" * 60)
        print("📋 转发规则和替换规则检查报告")
        print("=" * 60)
        print()
        
        has_issues = False
        
        for rule in rules:
            source_name = rule.source_chat.name if rule.source_chat else "未知"
            target_name = rule.target_chat.name if rule.target_chat else "未知"
            
            print(f"规则 ID: {rule.id}")
            print(f"  源聊天: {source_name}")
            print(f"  目标聊天: {target_name}")
            print(f"  规则启用: {'✅ 是' if rule.enable_rule else '❌ 否'}")
            print(f"  使用机器人: {'✅ 是' if rule.use_bot else '❌ 否'}")
            print(f"  替换模式开关: {'✅ 已开启' if rule.is_replace else '❌ 未开启'}")
            
            if rule.replace_rules:
                print(f"  替换规则数量: {len(rule.replace_rules)} 条")
                for idx, rr in enumerate(rule.replace_rules, 1):
                    print(f"    {idx}. \"{rr.pattern}\" → \"{rr.content}\"")
            else:
                print(f"  替换规则数量: 0 条")
            
            # 检查问题
            issues = []
            if not rule.enable_rule:
                issues.append("❌ 规则未启用")
            if rule.replace_rules and not rule.is_replace:
                issues.append("⚠️ 有替换规则但替换模式未开启")
                has_issues = True
            if rule.replace_rules and rule.is_replace:
                issues.append("✅ 替换规则配置正确")
            if not rule.replace_rules:
                issues.append("ℹ️ 没有配置替换规则")
            
            if issues:
                print("  状态:")
                for issue in issues:
                    print(f"    {issue}")
            
            print()
        
        # 提供建议
        print("=" * 60)
        if has_issues:
            print("🔧 发现问题！请按以下步骤修复：")
            print()
            print("1. 对于有替换规则但替换模式未开启的规则：")
            print("   执行: /settings <规则ID>")
            print("   然后点击按钮开启 \"替换模式\" 开关")
            print()
            print("2. 检查替换规则是否添加到了正确的规则上：")
            print("   执行: /switch")
            print("   选择正确的源聊天")
            print("   执行: /list_replace")
            print("   确认替换规则是否正确")
            print()
        else:
            print("✅ 所有规则配置看起来正常")
            print()
            print("如果替换规则仍然不生效，请检查：")
            print("1. 替换规则的正则表达式是否正确匹配消息内容")
            print("2. 消息中是否确实包含要替换的文本")
            print("3. 查看日志文件确认是否有错误信息")
            print()
            print("查看日志命令:")
            print("  tail -f nohup.out | grep -i replace")
        
        print("=" * 60)
        
    finally:
        session.close()

if __name__ == "__main__":
    check_replace_rules()

