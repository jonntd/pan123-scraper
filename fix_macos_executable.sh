#!/bin/bash

# pan123-scraper macOS可执行文件修复脚本
# 解决常见的macOS安全限制和权限问题

echo "🍎 pan123-scraper macOS修复工具"
echo "=================================="

FILE="pan123-scraper-mac"

# 检查文件是否存在
if [ ! -f "$FILE" ]; then
    echo "❌ 错误: 找不到文件 '$FILE'"
    echo ""
    echo "请确保："
    echo "1. 文件已下载到当前目录"
    echo "2. 文件名正确为 'pan123-scraper-mac'"
    echo ""
    echo "当前目录文件列表："
    ls -la | grep -E "(pan|scraper)"
    exit 1
fi

echo "📋 检查当前文件状态..."
echo "文件: $FILE"
ls -la "$FILE"

echo ""
echo "🔍 检查文件属性..."
QUARANTINE=$(xattr -l "$FILE" 2>/dev/null | grep -c "com.apple.quarantine")
if [ $QUARANTINE -gt 0 ]; then
    echo "⚠️  发现隔离属性 (这是问题的常见原因)"
else
    echo "✅ 无隔离属性"
fi

echo ""
echo "🔧 开始修复..."

# 步骤1: 移除隔离属性
echo "1️⃣ 移除隔离属性..."
if xattr -d com.apple.quarantine "$FILE" 2>/dev/null; then
    echo "   ✅ 隔离属性已移除"
else
    echo "   ℹ️  无隔离属性需要移除"
fi

# 步骤2: 移除所有扩展属性
echo "2️⃣ 清理所有扩展属性..."
if xattr -c "$FILE" 2>/dev/null; then
    echo "   ✅ 扩展属性已清理"
else
    echo "   ℹ️  无扩展属性需要清理"
fi

# 步骤3: 添加执行权限
echo "3️⃣ 设置执行权限..."
if chmod +x "$FILE"; then
    echo "   ✅ 执行权限已设置"
else
    echo "   ❌ 设置执行权限失败"
    exit 1
fi

echo ""
echo "🔍 验证修复结果..."
echo "修复后的文件状态:"
ls -la "$FILE"

echo ""
echo "检查剩余属性:"
REMAINING_ATTRS=$(xattr -l "$FILE" 2>/dev/null | wc -l)
if [ $REMAINING_ATTRS -eq 0 ]; then
    echo "✅ 无剩余限制属性"
else
    echo "⚠️  仍有 $REMAINING_ATTRS 个属性:"
    xattr -l "$FILE"
fi

echo ""
echo "🧪 测试文件可执行性..."
if [ -x "$FILE" ]; then
    echo "✅ 文件具有执行权限"
else
    echo "❌ 文件缺少执行权限"
    exit 1
fi

echo ""
echo "🚀 尝试启动应用..."
echo "=================================="
echo ""
echo "如果仍然出现安全警告，请按照以下步骤："
echo "1. 打开'系统偏好设置' → '安全性与隐私'"
echo "2. 在'通用'标签页底部点击'仍要打开'"
echo "3. 或者在终端中运行: sudo spctl --add $FILE"
echo ""
echo "正在启动 pan123-scraper..."
echo "访问地址: http://localhost:5001"
echo ""

# 尝试运行应用
if ./"$FILE"; then
    echo ""
    echo "🎉 应用启动成功！"
else
    echo ""
    echo "❌ 应用启动失败"
    echo ""
    echo "🔧 额外故障排除步骤："
    echo "1. 检查系统架构兼容性:"
    echo "   uname -m"
    echo "   file $FILE"
    echo ""
    echo "2. 检查依赖库:"
    echo "   otool -L $FILE"
    echo ""
    echo "3. 强制绕过安全检查:"
    echo "   sudo spctl --add $FILE"
    echo "   ./$FILE"
    echo ""
    echo "4. 临时禁用Gatekeeper (不推荐):"
    echo "   sudo spctl --master-disable"
    echo "   ./$FILE"
    echo "   sudo spctl --master-enable"
    echo ""
    echo "如果问题持续，请查看 MACOS_EXECUTABLE_FIX.md 获取详细帮助"
fi
