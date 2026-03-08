# Knotclaw

> 大模型对话归档工具 - 支持 DeepSeek 和 Gemini 的对话导出

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

Knotclaw 是一个本地运行的对话归档工具，支持从 DeepSeek 和 Gemini 等 AI 平台抓取分享的对话，通过友好的交互界面筛选消息，并导出为结构化的 Markdown 文件。

## 核心特性

- **多平台支持** - 支持 DeepSeek 和 Gemini，易于扩展新平台
- **双界面模式** - 命令行 (CLI) 和 Web 图形界面
- **智能筛选** - 分页浏览、单选/多选/范围选择
- **优化加载** - 增量处理、懒加载、Token 消耗监控
- **熔断保护** - 异常场景自动熔断，支持断点续传
- **结构化导出** - Markdown 格式，包含元数据和统计信息

## 支持平台

| 平台 | 状态 | URL 格式 |
|------|------|----------|
| DeepSeek | 已支持 | `https://chat.deepseek.com/share/*` |
| Gemini | 已支持 | `https://gemini.google.com/share/*` |

## 快速开始

### 环境要求

- Python 3.8+
- Chrome 浏览器 (用于 Selenium 自动化)

### 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/knotclaw.git
cd knotclaw

# 创建虚拟环境 (推荐)
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

### 运行

**Web 界面 (推荐):**

```bash
python -m src.web.app
# 或
python main.py --web
```

浏览器访问 `http://localhost:8080`

**命令行界面:**

```bash
python main.py
```

## 使用流程

### 1. 获取分享链接

在 AI 平台对话页面点击"分享"按钮，复制分享链接。

### 2. 加载对话

- **Web 界面**: 粘贴链接到输入框，点击"加载"
- **CLI**: 输入链接后按回车

### 3. 筛选消息

使用导航命令选择需要导出的消息:

| 命令 | 说明 |
|------|------|
| `n` / `p` | 下一页 / 上一页 |
| `<编号>` | 选择消息 (如: `1`, `2-5`, `1,3,5`) |
| `a` | 选择当前页全部 |
| `c` | 清除所有选择 |
| `s` | 显示已选消息 |
| `e` | 导出 |
| `q` | 退出 |

### 4. 导出

导出的 Markdown 文件保存在 `output/` 目录。

## 导出格式示例

```markdown
# 对话标题

## 对话信息

- **来源**: https://chat.deepseek.com/share/xxxxx
- **平台**: DeepSeek
- **创建时间**: 2026-03-08 15:30:00
- **消息数量**: 10
- **预估 Token 数**: 5,000

---

### 用户 (#1)

*2026-03-08 15:25:00*

请帮我写一个 Python 函数...

*Token 数: 50*

### 助手 (#2)

*2026-03-08 15:25:30*

好的，这是一个示例函数...

*Token 数: 200*

---

## 导出统计

- 导出时间: 2026-03-08 15:35:00
- 总消息数: 10
- 总 Token 数: 5,000

---

*由 Knotclaw 导出*
```

## 项目结构

```
knotclaw/
├── main.py                 # 主入口
├── requirements.txt        # 依赖列表
├── src/
│   ├── fetcher/           # 网页抓取模块
│   │   ├── base_fetcher.py    # 抓取器基类
│   │   ├── deepseek_fetcher.py
│   │   ├── gemini_fetcher.py
│   │   └── fetcher_factory.py # 抓取器工厂
│   ├── exporter/          # 导出模块
│   │   ├── markdown_exporter.py
│   │   ├── post_processor.py  # 后处理器
│   │   └── platform_utils.py  # 平台工具
│   ├── web/               # Web 模块
│   │   ├── app.py             # Flask 应用
│   │   ├── routes/            # 路由
│   │   ├── services/          # 服务层
│   │   └── middleware/        # 中间件
│   ├── cli/               # CLI 模块
│   ├── monitor/           # 监控模块
│   │   ├── token_monitor.py   # Token 监控
│   │   └── circuit_breaker.py # 熔断器
│   └── models/            # 数据模型
├── static/                # 静态文件 (Web UI)
├── tests/                 # 测试
├── output/                # 导出输出目录
└── temp/                  # 临时文件目录
```

## 架构设计

### 抓取器模式

采用工厂模式 + 策略模式，支持灵活扩展:

```python
from src.fetcher import BaseFetcher, FetcherFactory

class NewPlatformFetcher(BaseFetcher):
    SUPPORTED_DOMAINS = ["newplatform.com"]

    @classmethod
    def can_handle(cls, url: str) -> bool:
        return "newplatform.com" in url

    # 实现其他抽象方法...

FetcherFactory.register(NewPlatformFetcher)
```

### 性能优化

- **增量加载**: 分页获取，避免一次性加载大量数据
- **懒加载**: 仅在导出时加载完整消息内容
- **元数据压缩**: 导航仅使用索引、角色、摘要等必要信息

### 熔断机制

- Token 使用量实时监控
- 超过阈值自动触发紧急备份
- 支持断点续传

## 调试工具

```bash
# 抓取并保存原始 HTML
python scripts/debug_fetch.py --browser --url "https://chat.deepseek.com/share/xxxxx"

# 分析本地 HTML 文件
python scripts/debug_fetch.py --analyze
```

## 注意事项

### DeepSeek 访问限制

DeepSeek 分享页面使用 AWS WAF 保护，需要 JavaScript 验证。程序通过 Selenium 自动化浏览器处理。

### Gemini 访问

Gemini 分享页面同样需要 JavaScript 渲染，使用 Selenium 自动获取。

## 开发

```bash
# 运行测试
python -m pytest tests/

# 开发模式启动 Web 服务
python -m src.web.app --debug
```

## 许可证

[MIT License](LICENSE)

## 致谢

感谢 DeepSeek 和 Google Gemini 提供的对话分享功能。
