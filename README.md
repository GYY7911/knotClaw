# 🐱 Knotclaw - 大模型对话归档客户端

一个本地运行的命令行工具，用于抓取、筛选和导出大模型对话记录。

## ✨ 核心特性

### 🔍 数据获取与解析
- 支持从 DeepSeek 等大模型平台抓取分享的对话
- 自动解析网页内容，提取结构化对话数据
- 可扩展的抓取器架构，易于添加新平台支持

### 📊 Token 消耗优化策略（核心特性）
- **增量处理**：分页加载机制，仅加载当前需要处理的对话片段
- **进度压缩**：仅保留必要的元数据（索引ID、角色、摘要）用于导航
- **懒加载**：仅在导出时才加载选中消息的完整内容

### ⚡ 异常场景熔断机制
- 实时监控 Token 使用量
- 超限风险时自动触发紧急备份
- 支持断点续传，中断后可恢复

### 🖥️ 交互式筛选
- 友好的命令行交互界面
- 分页浏览对话消息
- 支持多种选择方式（单选、多选、范围选择）
- 实时显示已选消息统计

### 📄 输出规格
- 导出为结构清晰的 Markdown 文件
- 包含元数据、时间戳、Token 统计等信息
- 支持 JSON 格式备份

## 🚀 快速开始

### 环境要求
- Python 3.8+
- 推荐安装: `selenium` 和 `webdriver-manager`（用于自动获取需要JavaScript渲染的页面）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行方式

```bash
# 方式一：直接运行
python main.py

# 方式二：作为模块运行
python -m src.main
```

### 调试抓取工具

用于快速抓取并保存 DeepSeek 分享对话的独立工具：

```bash
# 抓取分享链接内容
python scripts/debug_fetch.py --browser --url "https://chat.deepseek.com/share/xxxxxx"

# 分析已保存的HTML文件
python scripts/debug_fetch.py --analyze

# 查看帮助
python scripts/debug_fetch.py --help
```

**输出文件：**
- 保存到 `temp/` 文件夹
- 文件名带时间戳：`deepseek_YYYYMMDD_HHMMSS.html` 和 `deepseek_YYYYMMDD_HHMMSS.txt`

### ⚠️ 重要说明：DeepSeek网站访问限制

DeepSeek分享页面使用AWS WAF保护，需要JavaScript验证。程序提供三种获取方式：

1. **浏览器自动化**（推荐）
   - 需要安装 `selenium` 和 `webdriver-manager`
   - 程序会自动启动无头浏览器获取页面

2. **手动输入HTML文件**
   - 在浏览器中打开分享链接
   - 等待页面完全加载
   - 按F12打开开发者工具
   - 右键点击`<html>`标签 → Copy → Copy outerHTML
   - 保存到文件，然后选择"从文件读取HTML"

3. **直接粘贴HTML**
   - 同上获取HTML后直接粘贴到程序中

### 使用流程

1. **启动程序**
   ```
   ============================================================
     🐱 Knotclaw - 大模型对话归档客户端
   ============================================================
   ```

2. **输入对话分享链接**
   ```
   请输入对话分享链接: https://chat.deepseek.com/share/xxxxx
   ```

3. **浏览和选择消息**
   ```
   命令:
     n/p     - 下一页/上一页
     <编号>  - 选择/取消选择消息 (如: 1, 2-5, 1,3,5)
     a       - 选择当前页全部
     c       - 清除所有选择
     s       - 显示已选消息
     e       - 导出选中消息
     q       - 退出
   ```

4. **导出为 Markdown**
   ```
   📤 正在导出 5 条消息...
   ✅ 导出成功！
   📄 文件路径: ./output/对话标题_20260304_201500.md
   ```

## 📁 项目结构

```
knotclaw/
├── main.py                 # 主入口
├── requirements.txt        # 依赖列表
├── README.md              # 说明文档
├── src/                   # 核心源代码
│   ├── main.py            # 模块入口
│   ├── models/            # 数据模型
│   ├── fetcher/           # 网页抓取
│   ├── monitor/           # 监控模块
│   ├── exporter/          # 导出模块
│   └── cli/               # 命令行界面
├── scripts/               # 工具脚本
│   └── debug_fetch.py     # 调试抓取工具
├── tests/                 # 测试文件
├── temp/                  # 临时输出文件
└── docs/                  # 文档
```

## 🔧 核心模块说明

### Token 监控器 (`TokenMonitor`)
- 实时追踪 Token 使用量
- 支持警告阈值和临界阈值
- 超限时触发回调函数

### 熔断器 (`CircuitBreaker`)
- 监控操作失败次数
- 达到阈值时触发熔断
- 支持自动恢复和紧急备份

### 断点续传 (`Checkpoint`)
- 记录任务执行进度
- 支持中断后恢复
- 自动检测未完成任务

## 📝 导出示例

```markdown
# 对话标题

## 📋 对话信息

- **来源**: https://chat.deepseek.com/share/xxxxx
- **创建时间**: 2026-03-04 20:15:00
- **消息数量**: 10
- **预估Token数**: 5000

---

### 👤 用户 (#1)

*2026-03-04 20:10:00*

请帮我写一个 Python 函数...

<small>Token数: 50</small>

### 🤖 助手 (#2)

*2026-03-04 20:10:30*

好的，这是一个示例函数...

<small>Token数: 200</small>

---

## 📊 导出统计

- 导出时间: 2026-03-04 20:15:30
- 总消息数: 10
- 总Token数: 5000

---

*由 Knotclaw 大模型对话归档客户端导出*
```

## ⌨️ 支持的平台

| 平台 | 状态 | 链接格式 |
|------|------|----------|
| DeepSeek | ✅ 支持 | `https://chat.deepseek.com/share/*` |

更多平台支持正在开发中...

## 🤝 扩展开发

### 添加新的抓取器

1. 继承 `BaseFetcher` 类
2. 实现必要的方法：
   - `can_handle(url)` - 检查URL是否支持
   - `fetch_page(url, page)` - 抓取指定页
   - `fetch_all_metadata(url)` - 抓取元数据
   - `load_message_content(message_id)` - 加载内容
3. 在 `FetcherFactory` 中注册

```python
from src.fetcher import BaseFetcher, FetcherFactory

class MyPlatformFetcher(BaseFetcher):
    SUPPORTED_DOMAINS = ["myplatform.com"]
    
    @classmethod
    def can_handle(cls, url: str) -> bool:
        return "myplatform.com" in url
    
    # ... 实现其他方法

FetcherFactory.register(MyPlatformFetcher)
```

## 📄 许可证

MIT License

## 🙏 致谢

感谢所有大模型平台提供的分享功能，让知识传递更加便捷。