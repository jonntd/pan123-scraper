# pan23-scraper

一个功能强大的123云盘智能文件管理工具，集成AI智能分组、TMDB刮削、文件重命名等功能。

## 🌟 主要功能

### 📁 智能文件管理
- **智能分组**: 使用AI自动分析和分组相关文件
- **批量操作**: 支持文件移动、删除、重命名等批量操作
- **文件夹浏览**: 直观的文件夹树形结构浏览

### 🎬 媒体刮削功能
- **TMDB集成**: 自动从TMDB获取电影和电视剧信息
- **智能重命名**: 基于刮削信息自动生成标准化文件名
- **多媒体类型支持**: 支持电影、电视剧、动漫等多种媒体类型

### 🤖 AI增强功能
- **智能文件分析**: 使用Gemini AI分析文件内容和结构
- **自动分类**: 基于文件名和内容智能分类
- **质量评估**: 自动评估刮削和分组质量


## 🚀 快速开始

### 环境要求
- Python 3.8+
- 123云盘账号
- TMDB API密钥
- Gemini API密钥

### 安装步骤

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

### 基础配置
```json
{
  "CLIENT_ID": "你的123云盘客户端ID",
  "CLIENT_SECRET": "你的123云盘客户端密钥",
  "TMDB_API_KEY": "你的TMDB API密钥",
  "GEMINI_API_KEY": "你的Gemini API密钥"
}
```

### 高级配置
- `QPS_LIMIT`: API请求频率限制（默认12）
- `CHUNK_SIZE`: 批处理大小（默认50）
- `MAX_WORKERS`: 最大并发线程数（默认12）
- `TASK_TIMEOUT_SECONDS`: 任务超时时间（默认1800秒）

## 📖 使用指南

### 1. 123云盘授权

### 2. 文件夹浏览

- 点击文件夹图标浏览子文件夹
- 使用面包屑导航快速跳转
- 支持文件搜索和过滤

### 3. 智能分组

1. 右键点击文件夹
2. 选择"智能分组"
3. 等待AI分析完成
4. 查看分组结果并确认操作

### 4. 媒体刮削

1. 选择要刮削的文件
2. 点击"刮削预览"按钮
3. 查看建议的新文件名
4. 确认后执行重命名

### 5. 批量操作

- **移动文件**: 选择文件后拖拽到目标文件夹
- **删除文件**: 选择文件后点击删除按钮
- **重命名**: 双击文件名进行编辑

## 🔧 API接口

### 文件管理接口
- `GET /api/folder/<folder_id>` - 获取文件夹内容
- `POST /api/move_files` - 移动文件
- `POST /api/delete_files` - 删除文件
- `POST /api/rename_file` - 重命名文件

### 智能功能接口
- `POST /api/submit_grouping_task` - 提交智能分组任务
- `GET /api/task_status/<task_id>` - 查询任务状态
- `POST /api/scrape_preview` - 刮削预览
- `POST /api/rename_files` - 批量重命名

### 安全接口
- `GET /api/security_status` - 获取安全状态
- `GET /api/backup_path` - 获取备份路径
- `POST /api/backup_path` - 设置备份路径


## 🔍 故障排除

### 常见问题

**Q: 访问令牌过期怎么办？**
A: 重新进行123云盘授权流程即可。

**Q: AI功能不可用？**
A: 检查Gemini API密钥配置和网络连接。

**Q: TMDB刮削失败？**
A: 验证TMDB API密钥是否有效。

**Q: 智能分组任务卡住？**
A: 可以取消当前任务并重新提交。




## 🧪 开发和测试

### 开发模式
```bash
# 启用调试模式
export FLASK_DEBUG=1
python app.py
```

### 项目结构
```
pan23-scraper/
├── app.py                 # 主应用文件
├── config.json           # 配置文件
├── requirements.txt      # 依赖列表
├── static/              # 静态资源
│   ├── script.js        # 前端JavaScript
│   └── style.css        # 样式文件
├── templates/           # HTML模板
│   └── index.html       # 主页面
└── docs/               # 文档目录
    ├── SECURITY_ENHANCEMENTS.md
    └── SECURITY_VERIFICATION_REPORT.md
```


## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- [123云盘](https://www.123pan.com/) - 提供云存储服务
- [TMDB](https://www.themoviedb.org/) - 提供电影数据库API
- [Google Gemini](https://ai.google.dev/) - 提供AI分析能力
- [Flask](https://flask.palletsprojects.com/) - Web框架


---

**⭐ 如果这个项目对你有帮助，请给个Star支持一下！**

## 📊 项目统计

![GitHub stars](https://img.shields.io/github/stars/jonntd/pan123-scraper)
![GitHub forks](https://img.shields.io/github/forks/jonntd/pan123-scraper)
![GitHub issues](https://img.shields.io/github/issues/jonntd/pan123-scraper)
![GitHub license](https://img.shields.io/github/license/jonntd/pan123-scraper)