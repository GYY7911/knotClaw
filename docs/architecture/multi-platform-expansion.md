# 多平台抓取器扩容架构设计

## 概述

本文档记录了从 DeepSeek 扩展到支持 Gemini 的架构设计方案。

**日期**: 2026-03-08
**状态**: 设计完成，待实现

---

## 当前架构分析

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    FetcherFactory                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  _registered_fetchers: [DeepSeekFetcher, ...]        │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│            get_fetcher(url) → BaseFetcher 实例              │
└─────────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │DeepSeek     │ │ Gemini      │ │ Future...   │
    │Fetcher      │ │ Fetcher     │ │ Fetcher     │
    └─────────────┘ └─────────────┘ └─────────────┘
```

### 设计模式

- **策略模式 (Strategy)**: 每个 Fetcher 实现不同的抓取策略
- **工厂模式 (Factory)**: FetcherFactory 根据URL自动选择合适的抓取器
- **模板方法模式**: BaseFetcher 定义抽象接口，子类实现具体逻辑

### 核心接口

```python
class BaseFetcher(ABC):
    SUPPORTED_DOMAINS: List[str]  # 支持的域名

    @classmethod
    @abstractmethod
    def can_handle(cls, url: str) -> bool: ...

    @abstractmethod
    def fetch_page(self, url: str, page: int = 0) -> FetchResult: ...

    @abstractmethod
    def fetch_all_metadata(self, url: str) -> FetchResult: ...

    @abstractmethod
    def load_message_content(self, message_id: str) -> Optional[str]: ...
```

---

## 平台对比

### DeepSeek vs Gemini

| 维度 | DeepSeek | Gemini |
|------|----------|--------|
| URL 格式 | `chat.deepseek.com/share/{id}` | `gemini.google.com/share/{id}` |
| 登录要求 | 公开分享页 | 需登录查看 |
| WAF/验证 | AWS WAF + 验证码 | Google 账户验证 |
| 框架 | 自定义 | Angular |
| 思考链 | `.ds-think-content` | 无 |
| **用户消息** | ✅ 可见 | ✅ 可见 |
| **AI 回复** | ✅ 可见 | ✅ 可见 |

> **注意**: Gemini 分享页面中用户消息容器（`.user-query-container`）可能有多个嵌套层级，需要去重处理。

### DOM 结构对比

**DeepSeek:**
```html
<div class="ds-message">
  <div class="ds-markdown">用户消息</div>
  <div class="ds-think-content">
    <div class="ds-markdown">思考内容</div>
  </div>
  <div class="ds-markdown">回答内容</div>
</div>
```

**Gemini:**
```html
<div class="user-query-container">用户消息</div>
<div class="response-container">
  <div class="response-container-content">
    <div class="message-content">回答内容</div>
  </div>
</div>
```

---

## Gemini 关键选择器

| 用途 | CSS 选择器 |
|------|------------|
| 用户消息容器 | `.user-query-container` |
| AI 响应容器 | `.response-container` |
| 消息内容 | `.message-content` |
| 聊天历史 | `.chat-history` |
| 分享轮次 | `.share-turn-viewer` |

---

## 扩容实施步骤

### 阶段 1: 创建 GeminiFetcher

1. 创建 `src/fetcher/gemini_fetcher.py`
2. 继承 `BaseFetcher`
3. 实现 `can_handle()` 方法
4. 实现 JavaScript 提取脚本

### 阶段 2: 注册到工厂

1. 在 `FetcherFactory._registered_fetchers` 添加 `GeminiFetcher`
2. 更新 `src/fetcher/__init__.py` 导出

### 阶段 3: 测试验证

1. 单元测试
2. 端到端测试

---

## 风险与缓解

| 风险 | 级别 | 缓解措施 |
|------|------|----------|
| Gemini 页面结构变化 | 高 | 使用稳定选择器，添加降级提取 |
| Google 登录检测 | 中 | 使用用户真实浏览器配置 |
| 速率限制 | 中 | 添加重试机制 |

---

## 目录结构优化

原 `temp/` 目录用于保存调试 HTML，存在误删风险。

**建议方案**: 改为 `.cache/` 目录，已在 `.gitignore` 中排除。

```
.cache/
├── debug/          # 调试文件
│   ├── deepseek/
│   └── gemini/
└── sessions/       # 会话缓存
```

---

## 附录: 代码文件清单

| 文件 | 用途 |
|------|------|
| `src/fetcher/base_fetcher.py` | 抽象基类 |
| `src/fetcher/deepseek_fetcher.py` | DeepSeek 实现 |
| `src/fetcher/gemini_fetcher.py` | Gemini 实现 (待创建) |
| `src/fetcher/fetcher_factory.py` | 工厂类 |
| `src/models/conversation.py` | 数据模型 |
