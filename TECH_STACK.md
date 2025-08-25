# Smart Media Organizer - 技术栈详解

## 🏗️ 架构概览

基于2024年Python最佳实践的现代化AI媒体整理工具。

### 核心设计原则
- **类型安全优先**: 100% 类型注解 + mypy检查
- **异步优先**: 高性能并发处理
- **配置驱动**: Pydantic Settings管理
- **结构化日志**: 便于监控和调试
- **测试驱动**: 90%+ 测试覆盖率

---

## 🛠️ 核心技术栈

### 环境管理
```toml
# pyproject.toml
[tool.poetry]
python = "^3.10"  # 现代Python版本
```

- **pyenv**: Python版本管理 (固定3.11.0)
- **Poetry**: 现代依赖管理和打包工具
- **src布局**: 标准项目结构

### CLI框架
```python
# Typer - 类型安全的现代CLI
import typer
from typing import Optional
from pathlib import Path

app = typer.Typer()

@app.command()
def organize(
    path: Path,                          # 自动路径验证
    media_type: MediaType = MediaType.AUTO,  # 枚举类型
    dry_run: bool = False,               # 类型安全标志
) -> None:
    """AI-powered media organizer with type safety."""
```

**优势**:
- 基于类型注解的自动CLI生成
- Rich集成的美观帮助信息
- 自动参数验证和错误处理

### 数据验证和配置
```python
# Pydantic - 运行时类型验证
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    hf_token: str = Field(..., env="HF_TOKEN")
    tmdb_api_key: str = Field(..., env="TMDB_API_KEY")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"

class MovieModel(BaseModel):
    title: str
    year: Optional[int] = None
    imdb_id: Optional[str] = None
```

**优势**:
- 运行时数据验证
- 自动环境变量处理
- 类型安全的配置管理

### HTTP客户端
```python
# httpx - 现代异步HTTP客户端
import httpx
from typing import AsyncGenerator

class HuggingFaceClient:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=10)
        )
    
    async def generate_text(self, prompt: str) -> str:
        response = await self.client.post(
            "https://api-inference.huggingface.co/models/...",
            json={"inputs": prompt}
        )
        return response.json()
```

**优势**:
- 完整的异步支持
- 连接池和请求限制
- 优秀的性能和类型支持

### 结构化日志
```python
# structlog - 现代结构化日志
import structlog
from rich.logging import RichHandler

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# 使用示例
logger.info("Processing file", filename="movie.mkv", size_mb=1024)
```

**优势**:
- JSON格式便于分析
- 结构化上下文信息
- Rich终端美观显示

### 用户界面
```python
# Rich - 美观的终端输出
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()

# 进度条
with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    console=console
) as progress:
    task = progress.add_task("Processing files...", total=100)
    # 处理逻辑...
```

**优势**:
- 美观的进度条和表格
- 彩色输出和格式化
- 终端检测和适配

---

## 🔧 开发工具链

### 代码质量 (统一工具链)
```toml
# pyproject.toml - 一站式配置

[tool.ruff]
# 现代linter，替代 flake8 + isort + pycodestyle
target-version = "py310"
select = ["E", "W", "F", "I", "B", "C4", "UP"]

[tool.black]
# 代码格式化
line-length = 88
target-version = ['py310', 'py311']

[tool.mypy]
# 类型检查
python_version = "3.10"
disallow_untyped_defs = true
strict = true
```

### 测试框架
```python
# pytest - 现代测试框架
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_file_scanner():
    scanner = FileScanner()
    files = await scanner.scan_directory("/test/path")
    assert len(files) > 0

@pytest.fixture
async def mock_hf_client():
    client = AsyncMock()
    client.generate_text.return_value = {"title": "Test Movie"}
    return client
```

**工具栈**:
- `pytest`: 测试框架
- `pytest-asyncio`: 异步测试支持
- `pytest-mock`: Mock对象
- `pytest-cov`: 覆盖率报告

### Git工作流
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
  - repo: https://github.com/psf/black
    rev: 23.0.0
    hooks:
      - id: black
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
```

---

## 📊 性能特性

### 异步架构
```python
# 异步文件处理
async def process_files(files: List[Path]) -> List[ProcessResult]:
    semaphore = asyncio.Semaphore(10)  # 限制并发数
    
    async def process_single(file: Path) -> ProcessResult:
        async with semaphore:
            # AI识别
            ai_result = await ai_client.identify(file.name)
            # 元数据获取
            metadata = await tmdb_client.search(ai_result.title)
            return ProcessResult(file=file, metadata=metadata)
    
    # 并发处理所有文件
    tasks = [process_single(file) for file in files]
    return await asyncio.gather(*tasks)
```

### 内存优化
- **流式处理**: 大文件夹分批处理
- **连接池**: 复用HTTP连接
- **缓存机制**: 减少重复API调用

### 错误恢复
```python
# 指数退避重试
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def api_call_with_retry():
    # API调用逻辑
    pass
```

---

## 🏛️ 项目结构详解

```
src/smart_media_organizer/
├── cli/
│   └── main.py           # Typer CLI应用
├── core/
│   ├── scanner.py        # 异步文件扫描
│   ├── ai_identifier.py  # AI识别核心
│   ├── metadata.py       # TMDB元数据
│   └── organizer.py      # 文件组织
├── services/
│   ├── huggingface.py    # HF异步客户端
│   ├── tmdb.py           # TMDB异步客户端
│   └── media_parser.py   # 媒体信息解析
├── models/
│   ├── config.py         # 配置模型
│   ├── movie.py          # 电影数据模型
│   ├── tv_show.py        # 电视剧模型
│   └── media_file.py     # 文件模型
└── utils/
    ├── logging.py        # 日志配置
    ├── file_ops.py       # 文件操作
    └── formatting.py     # 格式化工具
```

### 设计模式
- **依赖注入**: 服务间松耦合
- **策略模式**: 多AI模型支持
- **工厂模式**: 客户端创建
- **装饰器模式**: 重试和缓存

---

## 🎯 与传统方案对比

| 方面 | 传统方案 | 现代化方案 |
|------|----------|------------|
| **依赖管理** | pip + requirements.txt | Poetry + pyproject.toml |
| **CLI框架** | argparse/Click | Typer (类型驱动) |
| **HTTP客户端** | requests (同步) | httpx (异步) |
| **配置管理** | 环境变量/JSON | Pydantic Settings |
| **日志系统** | logging | structlog + Rich |
| **代码质量** | flake8 + isort + pycodestyle | ruff (统一工具) |
| **类型检查** | 可选 | 强制 (mypy) |
| **测试框架** | unittest | pytest + 异步支持 |
| **项目结构** | flat布局 | src布局标准 |
| **用户界面** | 简单文本 | Rich美观界面 |

---

## 🚀 开发体验

### 快速开始
```bash
# 环境设置
pyenv local 3.11.0
poetry install
poetry shell

# 开发工具
poetry run ruff check .      # 代码检查
poetry run black .           # 格式化
poetry run mypy .            # 类型检查
poetry run pytest --cov     # 测试覆盖率

# 运行应用
poetry run smart-organizer /path/to/media --dry-run
```

### IDE集成
- **VSCode**: 完整的类型提示和错误检查
- **PyCharm**: 智能重构和调试
- **vim/neovim**: LSP支持

### 调试体验
```python
# 结构化日志调试
logger.debug("AI API call", model="chatglm3-6b", prompt_length=156)
logger.info("File processed", file="movie.mkv", confidence=0.95)
logger.error("API failed", error_type="timeout", retry_count=2)
```

---

这个技术栈确保了：
- ✅ **开发效率**: 现代工具链提升开发速度
- ✅ **代码质量**: 自动化检查保证质量
- ✅ **类型安全**: 编译时错误发现
- ✅ **性能优化**: 异步架构提升性能
- ✅ **用户体验**: Rich界面提升交互
- ✅ **可维护性**: 清晰架构易于维护
