"""
本地调试 - 在已保存的HTML上测试提取逻辑
运行: python debug_local.py
"""

import re
from bs4 import BeautifulSoup
from pathlib import Path

def test_extraction():
    html_path = Path("temp/debug_page.html")
    if not html_path.exists():
        print("Error: temp/debug_page.html not exist")
        return None
    
    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    
    print("=" * 60)
    print("Test extraction logic")
    print("=" * 60)
    
    all_md = soup.find_all(class_="ds-markdown")
    print(f"\n1. Found {len(all_md)} .ds-markdown elements")
    
    results = []
    seen = set()
    
    for i, md in enumerate(all_md):
        text = (md.get_text() or "").strip()
        
        if "One more step" in text:
            continue
        if len(text) < 5:
            continue
            
        key = text[:50]
        if key in seen:
            continue
        seen.add(key)
        
        results.append({"idx": i, "len": len(text), "first50": text[:50]})
        print(f"  [{i}] len={len(text)}: {text[:60]}...")
    
    print(f"\n2. Passed: {len(results)} messages")
    
    print("\n3. Assign roles (A->B->C):")
    for i, r in enumerate(results):
        pos = i % 3
        r["role"] = "user" if pos == 0 else "assistant"
        r["isThinking"] = (pos == 1)
        print(f"  [{i}] role={r['role']}, thinking={r['isThinking']}")
    
    return results

if __name__ == "__main__":
    results = test_extraction()
    if results:
        print(f"\nFinal: {len(results)} messages")
