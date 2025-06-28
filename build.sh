#!/bin/bash

# pan123-scraper 本地构建脚本
# 用于测试PyInstaller打包

set -e  # 遇到错误立即退出

echo "🚀 开始构建 pan123-scraper..."

# 检查Python环境
echo "📋 检查Python环境..."
python --version
pip --version

# 检查必要文件
echo "📋 检查必要文件..."
required_files=("app.py" "requirements.txt" "pan123-scraper.spec")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ 错误: 缺少必要文件 $file"
        exit 1
    fi
    echo "✅ 找到文件: $file"
done

# 检查并创建必要目录
echo "📋 检查并创建必要目录..."
mkdir -p templates static

# 检查模板文件
if [ ! -f "templates/index.html" ]; then
    echo "⚠️  警告: templates/index.html 不存在，创建占位符文件"
    echo "<html><body><h1>pan123-scraper</h1><p>请确保正确的模板文件存在</p></body></html>" > templates/index.html
fi

# 检查静态文件
if [ ! -f "static/style.css" ]; then
    echo "⚠️  警告: static/style.css 不存在，创建占位符文件"
    echo "/* pan123-scraper styles - 请确保正确的CSS文件存在 */" > static/style.css
fi

if [ ! -f "static/script.js" ]; then
    echo "⚠️  警告: static/script.js 不存在，创建占位符文件"
    echo "// pan123-scraper scripts - 请确保正确的JS文件存在" > static/script.js
fi

# 安装依赖
echo "📦 安装依赖..."
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --upgrade pip
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org pyinstaller

# 检查requirements.txt并安装
if [ -f "requirements.txt" ]; then
    echo "📦 安装项目依赖..."
    pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt
else
    echo "⚠️  警告: requirements.txt 不存在，手动安装基础依赖"
    pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org flask requests cryptography
fi

# 清理之前的构建
echo "🧹 清理之前的构建..."
rm -rf build/ dist/ *.spec.bak

# 运行PyInstaller
echo "🔨 开始PyInstaller构建..."
pyinstaller pan123-scraper.spec

# 检查构建结果
echo "🔍 检查构建结果..."
if [ -d "dist" ]; then
    echo "✅ dist目录已创建"
    ls -la dist/
    
    # 根据平台检查可执行文件
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        expected_exe="dist/pan123-scraper-win.exe"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        expected_exe="dist/pan123-scraper-mac"
    else
        expected_exe="dist/pan123-scraper-linux"
    fi
    
    if [ -f "$expected_exe" ]; then
        echo "✅ 可执行文件构建成功: $expected_exe"
        file_size=$(du -h "$expected_exe" | cut -f1)
        echo "📊 文件大小: $file_size"
    else
        echo "❌ 错误: 预期的可执行文件不存在: $expected_exe"
        echo "📋 dist目录内容:"
        find dist/ -type f -exec ls -la {} \;
        exit 1
    fi
else
    echo "❌ 错误: dist目录未创建"
    exit 1
fi

# 测试可执行文件（可选）
echo "🧪 测试可执行文件..."
if [ -f "$expected_exe" ]; then
    echo "ℹ️  尝试运行可执行文件进行基本测试..."
    timeout 5s "$expected_exe" --help 2>/dev/null || echo "⚠️  可执行文件测试超时或失败（这可能是正常的）"
fi

echo ""
echo "🎉 构建完成！"
echo "📁 可执行文件位置: $expected_exe"
echo "📊 构建统计:"
echo "   - 构建时间: $(date)"
echo "   - 平台: $OSTYPE"
echo "   - Python版本: $(python --version)"
echo ""
echo "💡 使用说明:"
echo "   1. 将可执行文件复制到目标机器"
echo "   2. 确保config.json配置文件存在"
echo "   3. 运行可执行文件启动应用"
echo ""
echo "🔗 更多信息请查看 README.md"
