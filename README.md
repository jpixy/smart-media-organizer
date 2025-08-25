# Smart Media Organizer

一个基于AI的智能媒体文件整理工具，能够自动识别电影和电视剧信息，并按照标准格式重新组织文件结构。

## ✨ 特性

- 🤖 **纯AI识别**: 使用Hugging Face API智能解析文件名
- 🎬 **电影和电视剧支持**: 自动识别并分别处理
- 🌍 **多语言支持**: 支持中英文混合文件名识别  
- 📊 **元数据获取**: 通过TMDB API获取完整的电影/剧集信息
- 🏷️ **标准化命名**: 统一的文件夹和文件命名格式
- 📁 **智能组织**: 自动创建规范的目录结构
- 🖼️ **海报下载**: 自动下载1-3张电影海报
- 📝 **信息文件**: 生成包含简介、演员、导演等信息的文件
- ⚡ **现代化技术栈**: 基于2024年Python最佳实践

## 🏗️ 现代化架构设计

### 核心技术栈 (2024最佳实践)
- **依赖管理**: Poetry + pyenv
- **CLI框架**: Typer (类型注解驱动)
- **日志系统**: structlog + Rich (结构化日志)
- **HTTP客户端**: httpx (异步支持)
- **配置管理**: Pydantic Settings
- **代码质量**: ruff + black
- **项目结构**: src布局标准

### 项目结构 (src布局)
```
smart-media-organizer/
├── src/
│   └── smart_media_organizer/           # 主包 (下划线命名)
│       ├── __init__.py
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py                  # Typer应用入口
│       ├── core/
│       │   ├── __init__.py
│       │   ├── scanner.py               # 异步文件扫描器
│       │   ├── ai_identifier.py         # AI识别器 (类型注解)
│       │   ├── metadata.py              # TMDB元数据获取器
│       │   └── organizer.py             # 文件重新组织器
│       ├── services/
│       │   ├── __init__.py
│       │   ├── huggingface.py           # HF异步客户端
│       │   ├── tmdb.py                  # TMDB异步客户端
│       │   └── media_parser.py          # 媒体信息解析
│       ├── models/
│       │   ├── __init__.py
│       │   ├── config.py                # Pydantic配置模型
│       │   ├── movie.py                 # 电影数据模型
│       │   ├── tv_show.py               # 电视剧数据模型
│       │   └── media_file.py            # 媒体文件模型
│       └── utils/
│           ├── __init__.py
│           ├── logging.py               # structlog配置
│           ├── file_ops.py              # 文件操作工具
│           └── formatting.py            # 格式化工具
├── tests/                               # 测试目录
│   ├── __init__.py
│   ├── conftest.py                      # pytest配置
│   ├── unit/
│   └── integration/
├── docs/                                # 文档目录
├── pyproject.toml                       # Poetry配置 (替代requirements.txt)
├── .python-version                      # pyenv Python版本
├── .env.example                         # 环境变量模板
├── .gitignore
└── README.md
```

## 🔄 现代化异步工作流程

```
📁 输入目录
    ↓
🔍 异步文件扫描器 (async scanner)
    ↓ 并发发现媒体文件
🤖 AI识别器 (typed + async)
    ↓ HF API异步调用 + 结构化日志
📊 TMDB异步匹配器 (httpx)
    ↓ 并发获取完整信息
📂 安全文件组织器 (原子操作)
    ↓ 类型安全的重命名和移动
✅ 完成整理 (Rich进度显示)
```

### 详细处理步骤 (现代化)

1. **异步文件扫描**: 使用`asyncio`并发遍历目录，高效识别媒体文件
2. **类型安全AI识别**: 基于Pydantic模型的HF API调用，完整类型注解
3. **异步元数据获取**: 使用`httpx`异步客户端，并发TMDB API调用
4. **原子化文件组织**: 安全的文件操作，支持回滚和错误恢复

## 📁 输出格式

### 电影组织格式
```
[Original Title]-[Title](Edition)-Year-IMDB-TMDB/
├── [Original Title]-[Title](Edition)-Year-Resolution-Format-Codec-BitDepth-AudioCodec-Channels.ext
├── movie-info.json
├── poster-1.jpg
├── poster-2.jpg (可选)
└── poster-3.jpg (可选)
```

**示例**:
```
[Matrix, The]-[黑客帝国]-1999-tt0133093-603/
├── [Matrix, The]-[黑客帝国]-1999-1080p-BluRay-x264-10bit-DTS-7.1.mkv
├── movie-info.json
└── poster-1.jpg
```

### 电视剧组织格式
```
[Show Original Title]-[Show Title]-Year-IMDB-TMDB/
├── Season-01/
│   ├── [Show Original Title]-S01E01-[Episode Original Title]-[Episode Title]-Format-Codec-BitDepth-AudioCodec-Channels.ext
│   ├── [Show Original Title]-S01E02-[Episode Original Title]-[Episode Title]-Format-Codec-BitDepth-AudioCodec-Channels.ext
│   └── ...
├── Season-02/
├── show-info.json
└── poster-1.jpg
```

**示例**:
```
[Breaking Bad]-[绝命毒师]-2008-tt0903747-1396/
├── Season-01/
│   ├── [Breaking Bad]-S01E01-[Pilot]-[试播集]-BluRay-x264-10bit-DTS-5.1.mkv
│   └── [Breaking Bad]-S01E02-[Cat's in the Bag...]-[麻烦大了]-BluRay-x264-10bit-DTS-5.1.mkv
├── show-info.json
└── poster-1.jpg
```

## 🤖 AI识别特性

### 多模型支持
- THUDM/chatglm3-6b (中文理解强)
- baichuan-inc/Baichuan2-7B-Chat (中英文兼容)  
- microsoft/DialoGPT-medium (稳定性好)
- google/flan-t5-large (备选方案)

### 智能提示词
- 针对电影和电视剧优化的不同提示词模板
- 支持中英文混合文件名解析
- 自动提取年份、版本、季集等信息

### 可靠性保证
- 多模型自动切换
- 智能重试机制
- API调用频率控制
- 结果验证和置信度评估

## 🛠️ 现代化安装和配置

### 环境要求 (2024标准)
- Python 3.10+ (推荐 3.11)
- pyenv (Python版本管理)
- Poetry (依赖管理)
- Hugging Face账户 (免费)
- TMDB账户 (免费)

### 快速安装

#### 1. Python环境设置
```bash
# 安装pyenv (如果未安装)
curl https://pyenv.run | bash

# 安装并设置Python版本
pyenv install 3.11.0
pyenv local 3.11.0
```

#### 2. Poetry安装和项目设置
```bash
# 安装Poetry (如果未安装)
curl -sSL https://install.python-poetry.org | python3 -

# 克隆项目
git clone <repository-url>
cd smart-media-organizer

# Poetry安装依赖 (自动创建虚拟环境)
poetry install

# 激活虚拟环境
poetry shell
```

#### 3. API配置 (Pydantic Settings)
1. **Hugging Face API Token**:
   - 注册 [Hugging Face](https://huggingface.co/) 账户
   - 生成API Token (Settings → Access Tokens)
   - 免费额度: 300次/小时

2. **TMDB API Key**:
   - 注册 [TMDB](https://www.themoviedb.org/) 账户
   - 申请API Key
   - 免费额度: 1000次/日

3. **配置文件设置**:
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置
vim .env
```

`.env` 文件内容:
```bash
# API配置
HF_TOKEN=hf_your_huggingface_token
TMDB_API_KEY=your_tmdb_api_key

# 日志配置
LOG_LEVEL=INFO
LOG_FORMAT=json

# 性能配置
MAX_CONCURRENT=10
TIMEOUT_SECONDS=30
```

## 🚀 现代化使用方法

### Typer CLI接口 (类型安全)
```bash
# Poetry方式运行
poetry run smart-organizer [OPTIONS] PATH

# 或在虚拟环境中
smart-organizer [OPTIONS] PATH
```

### 参数说明 (类型注解自动验证)
```python
@app.command()
def organize(
    path: Path,                          # 媒体文件目录路径 (必需)
    media_type: MediaType = MediaType.AUTO,  # 媒体类型枚举
    dry_run: bool = False,               # 预览模式
    verbose: bool = False,               # 详细日志
    max_concurrent: int = 10,            # 并发数量
    timeout: int = 30,                   # 超时时间(秒)
    config_file: Optional[Path] = None,  # 配置文件路径
):
```

### 现代化使用示例

#### 基础使用
```bash
# 自动识别类型并整理 (Rich进度条)
poetry run smart-organizer /path/to/media

# 指定媒体类型
poetry run smart-organizer /path/to/movies --media-type movie

# 预览模式 (安全预览)
poetry run smart-organizer /path/to/media --dry-run
```

#### 高级使用
```bash
# 详细结构化日志输出
poetry run smart-organizer /path/to/media --verbose

# 自定义并发数和超时
poetry run smart-organizer /path/to/media --max-concurrent 20 --timeout 60

# 使用配置文件
poetry run smart-organizer /path/to/media --config-file config.toml

# 组合使用
poetry run smart-organizer /path/to/tv \
    --media-type tv \
    --dry-run \
    --verbose \
    --max-concurrent 5
```

#### 交互式使用
```bash
# Typer自动提供的帮助 (Rich格式化)
poetry run smart-organizer --help

# 参数补全 (如果启用)
poetry run smart-organizer /path/to/media --<TAB>
```

## 📊 性能指标

- **识别准确率**: 85-95% (纯AI识别)
- **处理速度**: 10-20文件/分钟 (受API限制)
- **成本**: 约100文件免费处理
- **支持格式**: MP4, MKV, AVI, MOV, WMV等主流格式

## 🔧 现代化技术依赖

### Poetry依赖配置 (pyproject.toml)
```toml
[tool.poetry.dependencies]
python = "^3.10"                    # 现代Python版本
typer = {extras = ["all"], version = "^0.9.0"}  # 现代CLI框架
pydantic = "^2.5.0"                 # 类型验证和设置
pydantic-settings = "^2.1.0"        # 配置管理
httpx = "^0.25.0"                   # 现代异步HTTP客户端
structlog = "^23.2.0"               # 结构化日志
rich = "^13.7.0"                    # 美观输出和进度条
huggingface-hub = "^0.19.0"         # HF官方SDK (最新)
pymediainfo = "^6.1.0"             # 媒体文件信息

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"                  # 测试框架
pytest-asyncio = "^0.21.0"         # 异步测试
pytest-mock = "^3.12.0"            # Mock支持
pytest-cov = "^4.1.0"              # 覆盖率
ruff = "^0.1.0"                     # 现代linter (替代flake8)
black = "^23.0.0"                   # 代码格式化
mypy = "^1.7.0"                     # 类型检查
pre-commit = "^3.6.0"              # Git hooks

[tool.poetry.scripts]
smart-organizer = "smart_media_organizer.cli.main:app"
```

### 开发工具链 (2024标准)
- **Linting**: ruff (统一linter，替代flake8+isort+pycodestyle)
- **Formatting**: black (代码格式化)
- **Type Checking**: mypy (静态类型检查)
- **Testing**: pytest + coverage
- **Git Hooks**: pre-commit (代码质量保证)

### API服务
- Hugging Face Inference API (免费额度: 300次/小时)
- TMDB API v3 (免费额度: 1000次/日)

## 🎯 现代化设计原则

- **类型安全**: 完整的类型注解，运行时类型验证
- **异步优先**: 高性能的并发处理，充分利用I/O时间
- **结构化日志**: 便于监控、调试和分析的JSON日志
- **配置驱动**: 基于Pydantic的类型安全配置管理
- **智能化**: 完全依赖AI理解文件名，无需复杂规则
- **标准化**: 统一的命名格式，兼容主流媒体管理软件
- **简洁性**: 无前缀设计，保持文件夹名称干净
- **可扩展**: 模块化架构，易于添加新功能
- **用户友好**: Rich界面、预览模式、详细反馈
- **可靠性**: 原子操作、错误恢复、完整测试覆盖

## 📝 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个项目。

---

> 注意: 本工具会移动和重命名文件，建议首次使用时先使用 `--dry-run` 参数进行预览。