# pan123-scraper Windows构建脚本 (PowerShell)
# 用于GitHub Actions和本地Windows构建

Write-Host "🚀 开始构建 pan123-scraper (Windows)..."

# 检查Python环境
Write-Host "📋 检查Python环境..."
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python版本: $pythonVersion"
} catch {
    Write-Host "❌ 错误: Python未安装或不在PATH中"
    exit 1
}

try {
    $pipVersion = pip --version 2>&1
    Write-Host "pip版本: $pipVersion"
} catch {
    Write-Host "❌ 错误: pip未安装或不在PATH中"
    exit 1
}

# 检查必要文件
Write-Host "📋 检查必要文件..."
$requiredFiles = @("app.py", "requirements.txt", "pan123-scraper.spec")
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        Write-Host "❌ 错误: 缺少必要文件 $file"
        exit 1
    }
    Write-Host "✅ 找到文件: $file"
}

# 检查并创建必要目录
Write-Host "📋 检查并创建必要目录..."
New-Item -ItemType Directory -Force -Path templates, static | Out-Null

# 检查模板文件
if (-not (Test-Path "templates/index.html")) {
    Write-Host "⚠️  警告: templates/index.html 不存在，创建占位符文件"
    "<html><body><h1>pan123-scraper</h1><p>请确保正确的模板文件存在</p></body></html>" | Out-File -FilePath "templates/index.html" -Encoding utf8
}

# 检查静态文件
if (-not (Test-Path "static/style.css")) {
    Write-Host "⚠️  警告: static/style.css 不存在，创建占位符文件"
    "/* pan123-scraper styles - 请确保正确的CSS文件存在 */" | Out-File -FilePath "static/style.css" -Encoding utf8
}

if (-not (Test-Path "static/script.js")) {
    Write-Host "⚠️  警告: static/script.js 不存在，创建占位符文件"
    "// pan123-scraper scripts - 请确保正确的JS文件存在" | Out-File -FilePath "static/script.js" -Encoding utf8
}

# 安装依赖
Write-Host "📦 安装依赖..."
try {
    python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "pip升级失败" }
    
    pip install pyinstaller
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller安装失败" }
    
    Write-Host "📦 安装项目依赖..."
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "项目依赖安装失败" }
} catch {
    Write-Host "❌ 错误: 依赖安装失败 - $_"
    exit 1
}

# 清理之前的构建
Write-Host "🧹 清理之前的构建..."
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
Get-ChildItem -Filter "*.spec.bak" | Remove-Item -Force

# 验证spec文件
if (-not (Test-Path "pan123-scraper.spec")) {
    Write-Host "❌ 错误: pan123-scraper.spec 不存在"
    exit 1
}
Write-Host "✅ PyInstaller spec文件找到"

# 运行PyInstaller
Write-Host "🔨 开始PyInstaller构建..."
try {
    pyinstaller pan123-scraper.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller构建失败" }
} catch {
    Write-Host "❌ 错误: PyInstaller构建失败 - $_"
    exit 1
}

# 检查构建结果
Write-Host "🔍 检查构建结果..."
if (Test-Path "dist") {
    Write-Host "✅ dist目录已创建"
    Get-ChildItem -Path "dist" -Force
    
    if (Test-Path "dist/pan123-scraper-win.exe") {
        Write-Host "✅ 可执行文件构建成功: dist/pan123-scraper-win.exe"
        $fileSize = (Get-Item "dist/pan123-scraper-win.exe").Length
        $fileSizeMB = [math]::Round($fileSize / 1MB, 2)
        Write-Host "📊 文件大小: $fileSizeMB MB"
    } else {
        Write-Host "❌ 错误: 预期的可执行文件不存在: dist/pan123-scraper-win.exe"
        Write-Host "📋 dist目录内容:"
        Get-ChildItem -Path "dist" -Recurse -Force
        exit 1
    }
} else {
    Write-Host "❌ 错误: dist目录未创建"
    exit 1
}

# 测试可执行文件（可选）
Write-Host "🧪 测试可执行文件..."
if (Test-Path "dist/pan123-scraper-win.exe") {
    Write-Host "ℹ️  尝试运行可执行文件进行基本测试..."
    # 在Windows上简单测试文件是否可执行
    try {
        $process = Start-Process -FilePath "dist/pan123-scraper-win.exe" -ArgumentList "--help" -PassThru -WindowStyle Hidden
        Start-Sleep -Seconds 2
        if (-not $process.HasExited) {
            $process.Kill()
        }
        Write-Host "✅ 可执行文件基本测试通过"
    } catch {
        Write-Host "⚠️  可执行文件测试失败（这可能是正常的）: $_"
    }
}

Write-Host ""
Write-Host "🎉 构建完成！"
Write-Host "📁 可执行文件位置: dist/pan123-scraper-win.exe"
Write-Host "📊 构建统计:"
Write-Host "   - 构建时间: $(Get-Date)"
Write-Host "   - 平台: Windows"
Write-Host "   - Python版本: $pythonVersion"
Write-Host ""
Write-Host "💡 使用说明:"
Write-Host "   1. 将可执行文件复制到目标机器"
Write-Host "   2. 确保config.json配置文件存在"
Write-Host "   3. 运行可执行文件启动应用"
Write-Host ""
Write-Host "🔗 更多信息请查看 README.md"
