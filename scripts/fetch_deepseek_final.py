"""
DeepSeek 对话获取工具 - 最终版
由于 DeepSeek 使用 Cloudflare 保护，需要手动操作获取内容
"""
import sys
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict


def get_clipboard_content() -> Optional[str]:
    """从剪贴板获取内容"""
    try:
        result = subprocess.run(
            ['powershell', '-command', 'Get-Clipboard'],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"获取剪贴板失败: {e}")
        return None


def parse_conversation(content: str) -> List[Dict[str, str]]:
    """解析对话内容"""
    messages = []
    lines = content.split('\n')
    
    current_role = 'unknown'
    current_content = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_content:
                current_content.append('')
            continue
        
        # 检测用户/助手标记
        lower_line = stripped.lower()
        is_user = any(m in lower_line for m in ['user:', '用户:', 'you:', '提问:', 'q:'])
        is_assistant = any(m in lower_line for m in ['deepseek:', 'assistant:', 'ai:', '回答:', 'a:'])
        
        if is_user or is_assistant:
            # 保存之前的消息
            if current_content:
                text = '\n'.join(current_content).strip()
                if text:
                    messages.append({
                        'role': current_role,
                        'content': text
                    })
                current_content = []
            
            current_role = 'user' if is_user else 'assistant'
            # 移除标记
            for marker in ['user:', '用户:', 'you:', '提问:', 'q:', 'deepseek:', 'assistant:', 'ai:', '回答:', 'a:']:
                stripped = re.sub(f'^{re.escape(marker)}\\s*', '', stripped, flags=re.IGNORECASE)
            if stripped:
                current_content.append(stripped)
        else:
            current_content.append(stripped)
    
    # 保存最后一条消息
    if current_content:
        text = '\n'.join(current_content).strip()
        if text:
            messages.append({
                'role': current_role,
                'content': text
            })
    
    return messages


def save_to_files(content: str, output_dir: Path, timestamp: str) -> List[Path]:
    """保存内容到多个文件"""
    saved_files = []
    
    # 1. 保存原始文本
    txt_file = output_dir / f"deepseek_{timestamp}.txt"
    txt_file.write_text(content, encoding='utf-8')
    saved_files.append(txt_file)
    print(f"   ✅ TXT: {txt_file.name}")
    
    # 2. 解析并保存 JSON
    messages = parse_conversation(content)
    json_data = {
        "source": "deepseek",
        "url": "https://chat.deepseek.com/share/bz0etehaisvzmm1tlg",
        "export_time": datetime.now().isoformat(),
        "message_count": len(messages),
        "messages": messages
    }
    json_file = output_dir / f"deepseek_{timestamp}.json"
    json_file.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding='utf-8')
    saved_files.append(json_file)
    print(f"   ✅ JSON: {json_file.name} ({len(messages)} 条消息)")
    
    # 3. 生成 Markdown
    md = f"# DeepSeek 对话\n\n"
    md += f"- 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    md += f"- 消息数量: {len(messages)}\n\n"
    md += "---\n\n"
    
    for msg in messages:
        role = msg['role']
        icon = "👤" if role == 'user' else "🤖" if role == 'assistant' else "📝"
        name = "用户" if role == 'user' else "DeepSeek" if role == 'assistant' else "内容"
        md += f"## {icon} {name}\n\n{msg['content']}\n\n---\n\n"
    
    md_file = output_dir / f"deepseek_{timestamp}.md"
    md_file.write_text(md, encoding='utf-8')
    saved_files.append(md_file)
    print(f"   ✅ Markdown: {md_file.name}")
    
    return saved_files


def main():
    print("=" * 70)
    print("🚀 DeepSeek 对话获取工具 - 最终版")
    print("=" * 70)
    
    url = "https://chat.deepseek.com/share/bz0etehaisvzmm1tlg"
    
    print(f"\n📋 目标链接: {url}")
    
    print("\n" + "=" * 70)
    print("📖 操作步骤（请按顺序执行）:")
    print("=" * 70)
    print("""
1. 打开浏览器，访问上面的链接
   
2. 等待页面完全加载（直到能看到完整的对话内容）

3. 按键盘快捷键全选并复制：
   - Windows: Ctrl+A（全选）然后 Ctrl+C（复制）
   - Mac: Cmd+A（全选）然后 Cmd+C（复制）

4. 回到这里，选择输入方式
""")
    
    print("\n请选择输入方式：")
    print("  1. 从剪贴板读取（推荐 - 刚才复制的内容）")
    print("  2. 手动输入/粘贴内容")
    print("  3. 从已有文件读取")
    
    choice = input("\n请选择 (1/2/3): ").strip()
    
    content = None
    
    if choice == '1':
        print("\n正在从剪贴板读取...")
        content = get_clipboard_content()
        if content:
            print(f"✅ 读取到 {len(content)} 个字符")
        else:
            print("❌ 剪贴板为空或读取失败")
    
    elif choice == '2':
        print("\n请粘贴内容（输入完成后，在新的一行输入 END 并回车）：")
        lines = []
        while True:
            try:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            except EOFError:
                break
        content = '\n'.join(lines)
        if content:
            print(f"✅ 接收到 {len(content)} 个字符")
    
    elif choice == '3':
        file_path = input("\n请输入文件路径: ").strip().strip('"\'')
        try:
            path = Path(file_path)
            if path.exists():
                content = path.read_text(encoding='utf-8')
                print(f"✅ 读取到 {len(content)} 个字符")
            else:
                print(f"❌ 文件不存在: {file_path}")
        except Exception as e:
            print(f"❌ 读取失败: {e}")
    
    else:
        print("❌ 无效选择")
        return False
    
    # 检查内容
    if not content or len(content) < 20:
        print("\n❌ 没有获取到有效内容")
        print("   请确保已经复制了页面内容")
        return False
    
    # 创建输出目录
    output_dir = Path("deepseek_output")
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"\n💾 正在保存文件到: {output_dir.absolute()}")
    saved_files = save_to_files(content, output_dir, timestamp)
    
    # 显示结果
    print("\n" + "=" * 70)
    print("📋 保存结果")
    print("=" * 70)
    
    print(f"\n✅ 成功保存 {len(saved_files)} 个文件")
    print(f"\n📁 文件位置: {output_dir.absolute()}")
    
    total_size = 0
    for f in saved_files:
        size = f.stat().st_size
        total_size += size
        print(f"   - {f.name} ({size:,} bytes)")
    
    print(f"\n📊 总大小: {total_size:,} bytes")
    
    # 预览
    print(f"\n📄 内容预览 (前 300 字符):")
    print("-" * 50)
    print(content[:300])
    if len(content) > 300:
        print(f"... (共 {len(content)} 字符)")
    print("-" * 50)
    
    print("\n✅ 完成！你可以用文本编辑器或浏览器打开保存的文件查看完整内容")
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        input("\n按回车键退出...")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n已取消")
        sys.exit(1)