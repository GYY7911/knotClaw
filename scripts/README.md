# Scripts 目录说明

本目录包含开发、调试和工具脚本。

## 目录结构

```
scripts/
├── dev/                    # 开发调试脚本
│   ├── debug_fetch.py      # 调试抓取器（手动验证提取逻辑）
│   ├── debug_local.py      # 本地HTML提取测试
│   ├── fetch_auto.py       # 自动抓取脚本
│   └── fetch_deepseek_final.py  # DeepSeek 抓取（遗留版本）
│
└── tools/                  # 工具脚本
    └── analyze_html.py     # HTML 分析工具
```

## 使用方法

### 调试脚本 (dev/)

```bash
# 调试抓取（使用浏览器）
python scripts/dev/debug_fetch.py --browser --url "https://chat.deepseek.com/share/xxx"

# 本地提取测试
python scripts/dev/debug_local.py

# 自动抓取
python scripts/dev/fetch_auto.py
```

### 工具脚本 (tools/)

```bash
# 分析已保存的 HTML
python scripts/tools/analyze_html.py temp/debug_page.html
```

## 注意

这些脚本主要用于开发调试，正常使用请通过主程序：

```bash
# Web 模式
python -m src.main --web

# CLI 模式
python -m src.main
```
