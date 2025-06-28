@echo off
REM pan123-scraper Windows构建脚本
REM 用于测试PyInstaller打包

echo 🚀 开始构建 pan123-scraper...

REM 检查Python环境
echo 📋 检查Python环境...
python --version
if %errorlevel% neq 0 (
    echo ❌ 错误: Python未安装或不在PATH中
    pause
    exit /b 1
)

pip --version
if %errorlevel% neq 0 (
    echo ❌ 错误: pip未安装或不在PATH中
    pause
    exit /b 1
)

REM 检查必要文件
echo 📋 检查必要文件...
if not exist "app.py" (
    echo ❌ 错误: 缺少必要文件 app.py
    pause
    exit /b 1
)
echo ✅ 找到文件: app.py



if not exist "requirements.txt" (
    echo ❌ 错误: 缺少必要文件 requirements.txt
    pause
    exit /b 1
)
echo ✅ 找到文件: requirements.txt

if not exist "pan123-scraper.spec" (
    echo ❌ 错误: 缺少必要文件 pan123-scraper.spec
    pause
    exit /b 1
)
echo ✅ 找到文件: pan123-scraper.spec

REM 检查并创建必要目录
echo 📋 检查并创建必要目录...
if not exist "templates" mkdir templates
if not exist "static" mkdir static

REM 检查模板文件
if not exist "templates\index.html" (
    echo ⚠️  警告: templates\index.html 不存在，创建占位符文件
    echo ^<html^>^<body^>^<h1^>pan123-scraper^</h1^>^<p^>请确保正确的模板文件存在^</p^>^</body^>^</html^> > templates\index.html
)

REM 检查静态文件
if not exist "static\style.css" (
    echo ⚠️  警告: static\style.css 不存在，创建占位符文件
    echo /* pan123-scraper styles - 请确保正确的CSS文件存在 */ > static\style.css
)

if not exist "static\script.js" (
    echo ⚠️  警告: static\script.js 不存在，创建占位符文件
    echo // pan123-scraper scripts - 请确保正确的JS文件存在 > static\script.js
)

REM 安装依赖
echo 📦 安装依赖...
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo ❌ 错误: pip升级失败
    pause
    exit /b 1
)

pip install pyinstaller
if %errorlevel% neq 0 (
    echo ❌ 错误: PyInstaller安装失败
    pause
    exit /b 1
)

echo 📦 安装项目依赖...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ❌ 错误: 项目依赖安装失败
    pause
    exit /b 1
)

REM 清理之前的构建
echo 🧹 清理之前的构建...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
if exist "*.spec.bak" del "*.spec.bak"

REM 运行PyInstaller
echo 🔨 开始PyInstaller构建...
pyinstaller pan123-scraper.spec
if %errorlevel% neq 0 (
    echo ❌ 错误: PyInstaller构建失败
    pause
    exit /b 1
)

REM 检查构建结果
echo 🔍 检查构建结果...
if exist "dist" (
    echo ✅ dist目录已创建
    dir dist
    
    if exist "dist\pan123-scraper-win.exe" (
        echo ✅ 可执行文件构建成功: dist\pan123-scraper-win.exe
        for %%A in ("dist\pan123-scraper-win.exe") do echo 📊 文件大小: %%~zA 字节
    ) else (
        echo ❌ 错误: 预期的可执行文件不存在: dist\pan123-scraper-win.exe
        echo 📋 dist目录内容:
        dir /s dist
        pause
        exit /b 1
    )
) else (
    echo ❌ 错误: dist目录未创建
    pause
    exit /b 1
)

echo.
echo 🎉 构建完成！
echo 📁 可执行文件位置: dist\pan123-scraper-win.exe
echo 📊 构建统计:
echo    - 构建时间: %date% %time%
echo    - 平台: Windows
python --version | findstr /C:"Python"
echo.
echo 💡 使用说明:
echo    1. 将可执行文件复制到目标机器
echo    2. 确保config.json配置文件存在
echo    3. 运行可执行文件启动应用
echo.
echo 🔗 更多信息请查看 README.md
echo.
echo 按任意键退出...
pause > nul
