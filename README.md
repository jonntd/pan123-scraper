# pan123-scraper

一个功能强大的123云盘智能文件管理工具，集成AI智能分组、TMDB刮削、文件重命名等功能。

![主界面](img/WX20250630-231558@2x.png)
![文件浏览](img/WX20250630-231814@2x.png)
![智能分组](img/WX20250630-232024@2x.png)
![刮削预览](img/WX20250630-232056@2x.png)
![批量重命名](img/WX20250630-234227@2x.png)
![配置管理](img/WX20250630-234710@2x.png)

## 🌟 主要功能

### 📁 智能文件管理
- **智能分组**: 使用AI模型自动分析和分组相关文件
- **批量操作**: 支持文件移动、删除、重命名等批量操作
- **文件夹浏览**: 直观的文件夹树形结构浏览
- **空文件夹清理**: 自动检测和删除空文件夹

### 🎬 媒体刮削功能
- **TMDB集成**: 自动从TMDB获取电影和电视剧信息
- **智能重命名**: 基于刮削信息自动生成标准化文件名
- **多媒体类型支持**: 支持电影、电视剧、动漫等多种媒体类型
- **刮削预览**: 重命名前预览建议的新文件名

### 🤖 AI增强功能
- **智能文件分析**: 使用AI模型分析文件内容和结构
- **自动分类**: 基于文件名和内容智能分类
- **质量评估**: 自动评估刮削和分组质量
- **智能文件夹命名**: 根据内容自动建议文件夹名称

### ⚡ 性能优化
- **多线程并发**: 支持多线程并行处理，提高处理速度
- **智能缓存**: 文件夹内容、分组结果、刮削结果多级缓存
- **QPS限制**: 智能API调用频率控制，避免触发限制
- **批量处理**: 支持大批量文件的高效处理

### 🔧 系统功能
- **智能端口管理**: 自动检测和处理端口冲突
- **应用重启**: 支持热重启功能，无需手动重启
- **任务管理**: 完整的任务队列和状态管理系统
- **日志系统**: 详细的操作日志和错误追踪


## 🚀 快速开始

### 环境要求
- **Python**: 3.8+ (推荐 3.9+)
- **123云盘账号**: 需要开放平台API权限
- **TMDB API密钥**: 用于电影和电视剧信息获取
- **AI API服务**: 支持OpenAI兼容接口的AI服务（如Gemini Balance等）
- **系统要求**: Windows 10+/macOS 10.14+/Linux (Ubuntu 18.04+)

### 安装方式

#### 方式一：使用预编译版本（推荐）
1. **下载可执行文件**
   - 从 [Releases](https://github.com/jonntd/pan123-scraper/releases) 页面下载对应平台的可执行文件
   - Windows: `pan123-scraper-win.exe`
   - macOS: `pan123-scraper-mac`
   - Linux: `pan123-scraper-linux`

2. **运行应用**
   ```bash
   # Windows
   pan123-scraper-win.exe

   # macOS/Linux
   ./pan123-scraper-mac
   ./pan123-scraper-linux
   ```

3. **访问Web界面**
   打开浏览器访问: http://localhost:5001

#### 方式二：从源码运行
1. **克隆项目**
   ```bash
   git clone https://github.com/jonntd/pan123-scraper.git
   cd pan123-scraper
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置应用**
   ```bash
   # 复制配置模板
   cp config.json.example config.json

   # 编辑配置文件
   nano config.json
   ```

4. **启动应用**
   ```bash
   python app.py
   ```

5. **访问Web界面**
   打开浏览器访问: http://localhost:5001

## ⚙️ 配置说明

### 首次配置
1. **启动应用后，访问配置页面**
2. **填写必要的API配置**：
   - **123云盘配置**: CLIENT_ID 和 CLIENT_SECRET
   - **TMDB配置**: TMDB_API_KEY
   - **AI配置**: AI_API_KEY 和 AI_API_URL（支持OpenAI兼容接口）

### 基础配置
```json
{
  "CLIENT_ID": "e10xxxx",
  "CLIENT_SECRET": "c4dxxx",
  "TMDB_API_KEY": "504xxx",
  "GEMINI_API_KEY": "sk-xxx",
  "GEMINI_API_URL": "http://your-ai-service.com/v1/chat/completions",
  "MODEL": "gpt-3.5-turbo",
  "GROUPING_MODEL": "gpt-3.5-turbo"
}
```

### AI服务配置说明
本项目支持多种AI服务：

1. **Gemini Balance**: 使用 [gemini-balance](https://github.com/snailyp/gemini-balance) 搭建的服务
2. **OpenAI兼容接口**: 任何支持OpenAI API格式的服务
3. **其他AI服务**: 只要提供OpenAI兼容的接口即可

配置示例：
```json
{
  "GEMINI_API_KEY": "your-api-key",
  "GEMINI_API_URL": "http://your-service-url/v1/chat/completions",
  "MODEL": "gpt-3.5-turbo",
  "GROUPING_MODEL": "gpt-4"
}
```

### 性能配置
```json
{
  "QPS_LIMIT": 8,
  "CHUNK_SIZE": 50,
  "MAX_WORKERS": 6,
  "API_MAX_RETRIES": 3,
  "API_RETRY_DELAY": 2,
  "AI_API_TIMEOUT": 60,
  "TMDB_API_TIMEOUT": 60
}
```

### 系统配置
```json
{
  "LANGUAGE": "zh-CN",
  "KILL_OCCUPIED_PORT_PROCESS": true,
  "ENABLE_QUALITY_ASSESSMENT": false,
  "ENABLE_SCRAPING_QUALITY_ASSESSMENT": true,
  "TASK_QUEUE_GET_TIMEOUT": 1.0
}
```

### 配置说明
- **QPS_LIMIT**: API请求频率限制（每秒请求数，默认8）
- **CHUNK_SIZE**: 批处理大小（默认50）
- **MAX_WORKERS**: 最大并发线程数（默认6）
- **KILL_OCCUPIED_PORT_PROCESS**: 是否自动结束占用端口的进程（默认true）
- **ENABLE_QUALITY_ASSESSMENT**: 是否启用智能分组质量评估（默认false）
- **ENABLE_SCRAPING_QUALITY_ASSESSMENT**: 是否启用刮削质量评估（默认true）

## 📖 使用指南

### 1. 初始设置
1. **启动应用**: 运行可执行文件或 `python app.py`
2. **访问界面**: 打开浏览器访问 http://localhost:5001
3. **配置API**: 在配置页面填写必要的API密钥
4. **测试连接**: 使用"测试连接"功能验证配置

### 2. 文件夹浏览
- **导航**: 点击文件夹图标浏览子文件夹
- **面包屑**: 使用顶部导航快速跳转到上级目录
- **文件信息**: 查看文件大小、修改时间等详细信息
- **批量选择**: 支持多选文件进行批量操作

### 3. 智能分组
1. **选择文件夹**: 在文件夹浏览器中选择要分析的文件夹
2. **启动分组**: 点击"智能分组"按钮
3. **AI分析**: 等待AI模型分析文件内容和结构
4. **查看结果**: 查看AI建议的分组方案
5. **执行分组**: 选择要执行的分组并确认操作

### 4. 媒体刮削
1. **选择文件**: 在文件列表中选择要刮削的媒体文件
2. **刮削预览**: 点击"刮削预览"按钮
3. **TMDB匹配**: 系统自动从TMDB获取媒体信息
4. **预览结果**: 查看建议的新文件名格式
5. **应用重命名**: 确认后批量执行重命名操作

### 5. 批量操作
- **文件移动**: 选择文件后使用"移动到"功能
- **文件删除**: 选择文件后点击删除按钮（支持批量删除）
- **文件重命名**: 支持单个和批量重命名
- **文件夹创建**: 在任意位置创建新文件夹
- **空文件夹清理**: 自动检测和删除空文件夹

### 6. 任务管理
- **任务队列**: 查看当前正在执行和等待的任务
- **任务状态**: 实时监控任务执行进度
- **任务取消**: 支持取消正在执行的任务
- **任务历史**: 查看已完成任务的详细信息

## 🔧 API接口

### 文件管理接口
- `GET /get_folder_content/<folder_id>` - 获取文件夹内容（GET方式）
- `POST /get_folder_content` - 获取文件夹内容（POST方式）
- `POST /get_folder_properties` - 获取文件夹属性信息
- `POST /move_files_direct` - 直接移动文件
- `POST /delete_files` - 删除文件
- `POST /rename_files` - 重命名文件
- `POST /create_folder` - 创建文件夹
- `POST /delete_empty_folders` - 删除空文件夹

### 智能功能接口
- `POST /api/grouping_task/submit` - 提交智能分组任务
- `GET /api/grouping_task/status/<task_id>` - 查询任务状态
- `GET /api/grouping_task/queue_info` - 获取任务队列信息
- `POST /api/grouping_task/cancel/<task_id>` - 取消任务
- `POST /scrape_preview` - 刮削预览
- `POST /apply_rename` - 应用重命名
- `POST /suggest_folder_name` - 智能文件夹命名
- `POST /organize_files_by_groups` - 按分组组织文件

### 系统管理接口
- `GET /config` - 获取当前配置
- `POST /save_config` - 保存配置
- `GET /token_status` - 获取访问令牌状态
- `POST /refresh_token` - 刷新访问令牌
- `POST /test_ai_api` - 测试AI API连接
- `POST /restart` - 重启应用
- `GET /restart_status` - 获取重启状态

### 缓存管理接口
- `POST /clear_cache` - 清理缓存
- `GET /cache_status` - 获取缓存状态
- `POST /cancel_task` - 取消当前任务

### 日志接口
- `GET /logs` - 获取应用日志


## 🔍 故障排除

### 常见问题

**Q: 应用启动失败，提示端口被占用？**
A: 应用会自动检测端口冲突并尝试结束占用进程，如果仍有问题，可以在配置中设置 `KILL_OCCUPIED_PORT_PROCESS: false` 来禁用自动结束进程功能。

**Q: 访问令牌过期怎么办？**
A: 应用会自动检测令牌过期并尝试刷新，也可以在界面上手动点击"刷新令牌"按钮。

**Q: AI功能不可用？**
A: 检查以下配置：
- GEMINI_API_KEY 是否正确设置
- GEMINI_API_URL 是否可访问（确保AI服务正常运行）
- 网络连接是否正常
- AI服务是否支持OpenAI兼容接口
- 可以使用"测试AI API"功能进行诊断

**Q: TMDB刮削失败？**
A: 验证 TMDB_API_KEY 是否有效，确保网络可以访问 TMDB API。

**Q: 智能分组任务卡住？**
A: 可以在任务管理页面取消当前任务，或者重启应用程序。

**Q: 文件上传或处理速度慢？**
A: 可以调整以下配置参数：
- 增加 `MAX_WORKERS` 提高并发度
- 调整 `QPS_LIMIT` 控制API调用频率
- 调整 `CHUNK_SIZE` 优化批处理大小

**Q: 应用崩溃或异常退出？**
A: 查看 `rename_log.log` 文件获取详细错误信息，必要时可以使用重启功能。

### 日志查看
- **应用日志**: 查看 `rename_log.log` 文件
- **Web日志**: 在界面上点击"查看日志"按钮
- **备份文件**: 重命名操作会自动创建备份文件 `rename_data_backup_*.json`

## 🧪 开发和测试

### 开发环境设置
```bash
# 克隆项目
git clone https://github.com/jonntd/pan123-scraper.git
cd pan123-scraper

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt

# 启用调试模式
export FLASK_DEBUG=1      # Linux/macOS
set FLASK_DEBUG=1         # Windows

# 启动开发服务器
python app.py
```

### 项目结构
```
pan123-scraper/
├── app.py                    # 主应用文件
├── config.json              # 配置文件
├── config.json.example      # 配置模板
├── requirements.txt         # Python依赖列表
├── pan123-scraper.spec      # PyInstaller打包配置
├── static/                  # 静态资源
│   ├── script.js           # 前端JavaScript
│   └── style.css           # 样式文件
├── templates/              # HTML模板
│   └── index.html          # 主页面模板
├── build.sh               # Linux/macOS构建脚本
├── build.bat              # Windows构建脚本
├── test_*.py              # 测试脚本
├── rename_log.log         # 应用日志文件
├── 123_access_token.txt   # 访问令牌缓存
└── docs/                  # 文档目录
    ├── BUILD_GUIDE.md
    ├── PORT_MANAGEMENT_GUIDE.md
    └── *.md               # 其他文档
```

### 构建可执行文件
```bash
# 使用构建脚本（推荐）
./build.sh              # Linux/macOS
build.bat               # Windows

# 或手动构建
pip install pyinstaller
pyinstaller pan123-scraper.spec
```

### 测试功能
```bash
# 运行端口管理测试
python test_port_management.py

# 运行Windows兼容性测试
python test_windows_compatibility.py

# 测试可执行文件
./test_executable.sh    # Linux/macOS
```


## � 部署指南

### 生产环境部署
1. **使用预编译版本**（推荐）
   - 下载对应平台的可执行文件
   - 配置 `config.json` 文件
   - 直接运行可执行文件

2. **使用源码部署**
   ```bash
   # 安装生产环境依赖
   pip install -r requirements.txt gunicorn

   # 使用Gunicorn启动（Linux）
   gunicorn -w 4 -b 0.0.0.0:5001 app:app
   ```

3. **Docker部署**（可选）
   ```dockerfile
   FROM python:3.9-slim
   WORKDIR /app
   COPY . .
   RUN pip install -r requirements.txt
   EXPOSE 5001
   CMD ["python", "app.py"]
   ```

### 系统服务配置
创建系统服务文件（Linux）：
```ini
[Unit]
Description=pan123-scraper
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/pan123-scraper
ExecStart=/path/to/pan123-scraper-linux
Restart=always

[Install]
WantedBy=multi-user.target
```

## 🔒 安全说明

### 数据安全
- **本地存储**: 所有配置和令牌信息存储在本地
- **API密钥**: 配置文件中的API密钥请妥善保管
- **访问控制**: 建议在内网环境使用，避免暴露到公网
- **备份机制**: 重要操作会自动创建备份文件

### 隐私保护
- **文件内容**: 应用不会上传或泄露您的文件内容
- **API调用**: 仅用于获取媒体信息，不涉及敏感数据
- **日志记录**: 日志文件不包含敏感信息

## �📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- [123云盘](https://www.123pan.com/) - 提供云存储服务
- [TMDB](https://www.themoviedb.org/) - 提供电影数据库API
- [Gemini Balance](https://github.com/snailyp/gemini-balance) - AI服务代理工具
- OpenAI兼容API服务 - 提供AI分析能力
- [Flask](https://flask.palletsprojects.com/) - Web框架
- [PyInstaller](https://pyinstaller.org/) - 应用打包工具

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. **Fork项目**
2. **创建功能分支** (`git checkout -b feature/AmazingFeature`)
3. **提交更改** (`git commit -m 'Add some AmazingFeature'`)
4. **推送到分支** (`git push origin feature/AmazingFeature`)
5. **创建Pull Request**

### 开发规范
- 遵循PEP 8代码风格
- 添加适当的注释和文档
- 确保新功能有相应的测试
- 更新相关文档

## 📞 支持与反馈

- **问题报告**: [GitHub Issues](https://github.com/jonntd/pan123-scraper/issues)
- **功能建议**: [GitHub Discussions](https://github.com/jonntd/pan123-scraper/discussions)
- **文档问题**: 欢迎提交PR改进文档

---

**⭐ 如果这个项目对你有帮助，请给个Star支持一下！**

## 📊 项目统计

![GitHub stars](https://img.shields.io/github/stars/jonntd/pan123-scraper)
![GitHub forks](https://img.shields.io/github/forks/jonntd/pan123-scraper)
![GitHub issues](https://img.shields.io/github/issues/jonntd/pan123-scraper)
![GitHub license](https://img.shields.io/github/license/jonntd/pan123-scraper)
![Python version](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)