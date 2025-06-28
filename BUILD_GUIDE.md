# 🔨 构建指南

本文档介绍如何将pan123-scraper打包为可执行文件。

## 🎯 构建方式

### 1. 自动构建（推荐）

#### GitHub Actions自动构建
- 推送代码到GitHub后自动触发构建
- 支持Windows、Linux、macOS三个平台
- 构建产物自动上传为Artifacts

#### 本地脚本构建
```bash
# Linux/macOS
./build.sh

# Windows
build.bat
```

### 2. 手动构建

#### 环境准备
```bash
# 安装依赖
pip install -r requirements.txt
pip install pyinstaller

# 创建必要目录（如果不存在）
mkdir -p templates static
```

#### 执行构建
```bash
# 使用spec文件构建
pyinstaller pan123-scraper.spec

# 或者直接构建（不推荐）
pyinstaller --onefile app.py
```

## 📋 构建要求

### 系统要求
- Python 3.8+
- pip包管理器
- 足够的磁盘空间（至少500MB）

### 必要文件
- ✅ `app.py` - 主应用文件
- ✅ `requirements.txt` - 依赖列表
- ✅ `pan123-scraper.spec` - PyInstaller配置
- ✅ `templates/` - HTML模板目录
- ✅ `static/` - 静态资源目录

### 可选文件
- `config.json.example` - 配置示例
- `README.md` - 项目文档
- `LICENSE` - 许可证文件

## 🔧 构建配置

### PyInstaller Spec文件
`pan123-scraper.spec` 包含以下配置：

```python
# 平台特定的可执行文件名
if sys.platform == "win32":
    exe_name = 'pan123-scraper-win'
elif sys.platform == "darwin":
    exe_name = 'pan123-scraper-mac'
else:
    exe_name = 'pan123-scraper-linux'

# 包含的数据文件
datas=[
    ('templates', 'templates'),
    ('static', 'static'),
    ('config.json.example', '.'),
    # ... 其他文件
]

# 隐藏导入的模块
hiddenimports=[
    'cryptography.fernet',
    'cryptography.hazmat.primitives.kdf.pbkdf2',
    # ... 其他模块
]
```

### 构建选项说明
- `--onefile`: 打包为单个可执行文件
- `--console`: 保留控制台窗口
- `--upx`: 使用UPX压缩（如果可用）
- `--strip`: 去除调试信息（Linux/macOS）

## 📦 构建产物

### 文件结构
```
dist/
├── pan123-scraper-win.exe    # Windows可执行文件
├── pan123-scraper-linux      # Linux可执行文件
└── pan123-scraper-mac        # macOS可执行文件
```

### 文件大小
- Windows: ~50-80MB
- Linux: ~50-70MB
- macOS: ~50-70MB

*实际大小取决于依赖和压缩设置*

## 🚀 部署说明

### 1. 准备配置文件
```bash
# 复制配置示例
cp config.json.example config.json

# 编辑配置
nano config.json
```

### 2. 运行可执行文件
```bash
# Windows
pan123-scraper-win.exe

# Linux
./pan123-scraper-linux

# macOS
./pan123-scraper-mac
```

### 3. 访问应用
打开浏览器访问: http://localhost:5001

## 🔍 故障排除

### 常见构建问题

#### 1. 模块导入错误
```
ModuleNotFoundError: No module named 'xxx'
```
**解决方案**: 在spec文件的`hiddenimports`中添加缺失的模块

#### 2. 文件未找到错误
```
FileNotFoundError: [Errno 2] No such file or directory: 'templates/index.html'
```
**解决方案**: 确保所有必要文件存在，或在spec文件的`datas`中正确配置

#### 3. 权限错误（Linux/macOS）
```
Permission denied
```
**解决方案**: 
```bash
chmod +x pan123-scraper-linux
# 或
chmod +x pan123-scraper-mac
```

#### 4. 构建过程中断
**解决方案**: 
- 检查磁盘空间
- 检查网络连接
- 重新运行构建脚本

### 运行时问题

#### 1. 端口被占用
```
Address already in use
```
**解决方案**: 
- 关闭占用5001端口的程序
- 或修改app.py中的端口配置

#### 2. 配置文件错误
```
Configuration file error
```
**解决方案**: 
- 检查config.json格式
- 确保所有必要配置项存在
- 参考config.json.example

#### 3. API密钥无效
```
API authentication failed
```
**解决方案**: 
- 验证123云盘API密钥
- 检查TMDB API密钥
- 确保网络连接正常

## 📊 性能优化

### 构建优化
```bash
# 启用UPX压缩
pip install upx-ucl

# 排除不必要的模块
# 在spec文件的excludes中添加
```

### 运行优化
- 使用SSD存储
- 确保足够的内存（推荐4GB+）
- 关闭不必要的后台程序

## 🔄 持续集成

### GitHub Actions工作流
- 自动触发：推送到main分支
- 多平台构建：Windows、Linux、macOS
- 自动测试：构建验证和基本功能测试
- 产物上传：构建结果自动保存

### 本地开发流程
1. 修改代码
2. 运行本地测试
3. 执行构建脚本
4. 验证构建结果
5. 提交代码

## 📝 注意事项

### 安全考虑
- 不要在可执行文件中包含敏感信息
- 配置文件应单独提供
- 定期更新依赖包

### 兼容性
- 在目标平台上测试可执行文件
- 注意Python版本兼容性
- 考虑系统依赖差异

### 维护
- 定期更新构建脚本
- 监控构建日志
- 及时修复构建问题

---

**💡 提示**: 如果遇到问题，请查看构建日志或提交Issue获取帮助。
