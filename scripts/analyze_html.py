"""分析保存的HTML文件"""
import re
import json
from pathlib import Path

def analyze_html(file_path: str):
    path = Path(file_path)
    
    if not path.exists():
        print(f"文件不存在: {file_path}")
        return
    
    html = path.read_text(encoding='utf-8')
    
    print("=" * 60)
    print("HTML 文件分析")
    print("=" * 60)
    
    print(f"\n文件路径: {path.absolute()}")
    print(f"文件大小: {len(html):,} 字符")
    
    # 检查基本内容
    print("\n基本检查:")
    print(f"  包含 'chat': {'chat' in html.lower()}")
    print(f"  包含 'deepseek': {'deepseek' in html.lower()}")
    print(f"  包含 'conversation': {'conversation' in html.lower()}")
    print(f"  包含 'messages': {'messages' in html.lower()}")
    print(f"  包含 '__NEXT_DATA__': {'__NEXT_DATA__' in html}")
    print(f"  包含 'window.__': {'window.__' in html}")
    
    # 查找所有 script 标签的 id
    script_ids = re.findall(r'<script[^>]*id=["\']([^"\'>]+)["\']', html)
    print(f"\n找到 {len(script_ids)} 个带 id 的 script 标签:")
    for sid in script_ids[:20]:
        print(f"  - {sid}")
    
    # 查找可能的 JSON 数据
    print("\n查找 JSON 数据模式:")
    
    # 模式1: 查找大的 JSON 块
    json_patterns = [
        (r'window\.__INITIAL_STATE__\s*=\s*({.*?});', 'window.__INITIAL_STATE__'),
        (r'window\.__DATA__\s*=\s*({.*?});', 'window.__DATA__'),
        (r'"conversation"\s*:\s*({[^}]+})', 'conversation object'),
        (r'"messages"\s*:\s*(\[.*?\])', 'messages array'),
    ]
    
    for pattern, name in json_patterns:
        matches = re.findall(pattern, html, re.DOTALL)
        if matches:
            print(f"  找到 {name}: {len(matches)} 个匹配")
            if len(matches) > 0 and len(matches[0]) < 500:
                print(f"    预览: {matches[0][:200]}...")
    
    # 查找特定的数据属性
    data_attrs = re.findall(r'data-([a-z-]+)=["\']([^"\']+)["\']', html)
    print(f"\n找到 {len(data_attrs)} 个 data 属性:")
    for attr, value in data_attrs[:10]:
        print(f"  data-{attr}: {value[:50]}...")
    
    # 检查 title
    title_match = re.search(r'<title>([^<]+)</title>', html)
    if title_match:
        print(f"\n页面标题: {title_match.group(1)}")
    
    # 提取前2000个字符查看结构
    print("\n文件开头内容预览 (前2000字符):")
    print("-" * 40)
    # 移除多余空白
    preview = ' '.join(html[:2000].split())
    print(preview[:1000])
    
    # 查找包含大量文本的 script 标签
    script_contents = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    large_scripts = [(i, len(s)) for i, s in enumerate(script_contents) if len(s) > 1000]
    
    if large_scripts:
        print(f"\n找到 {len(large_scripts)} 个大型 script 标签:")
        for idx, size in large_scripts[:5]:
            print(f"  Script #{idx}: {size:,} 字符")
            # 检查是否包含 JSON
            content = script_contents[idx]
            if '{' in content and ':' in content:
                # 尝试提取 JSON 开头
                json_start = content.find('{')
                if json_start != -1:
                    print(f"    可能的 JSON 开头: {content[json_start:json_start+100]}...")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    analyze_html("deepseek_conversation.html")