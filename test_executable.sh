#!/bin/bash

# 测试可执行文件脚本

echo "🧪 测试 pan123-scraper 可执行文件..."

# 检查可执行文件是否存在
if [ ! -f "dist/pan123-scraper-mac" ]; then
    echo "❌ 错误: 可执行文件不存在"
    exit 1
fi

echo "✅ 可执行文件存在: dist/pan123-scraper-mac"

# 检查文件权限
if [ ! -x "dist/pan123-scraper-mac" ]; then
    echo "❌ 错误: 文件没有执行权限"
    exit 1
fi

echo "✅ 文件具有执行权限"

# 检查文件大小
file_size=$(du -h dist/pan123-scraper-mac | cut -f1)
echo "📊 文件大小: $file_size"

# 检查文件类型
file_type=$(file dist/pan123-scraper-mac)
echo "📋 文件类型: $file_type"

# 尝试运行可执行文件（短时间测试）
echo "🚀 尝试运行可执行文件..."

# 在后台启动应用
./dist/pan123-scraper-mac &
app_pid=$!

echo "📱 应用已启动，PID: $app_pid"

# 等待几秒让应用启动
sleep 3

# 检查进程是否还在运行
if kill -0 $app_pid 2>/dev/null; then
    echo "✅ 应用正在运行"
    
    # 等待服务器完全启动
    echo "⏳ 等待服务器启动..."
    sleep 5

    # 尝试访问应用
    if command -v curl >/dev/null 2>&1; then
        echo "🌐 测试HTTP连接..."

        # 测试主页
        if curl -s --connect-timeout 10 http://localhost:5001 | grep -q "123云盘刮削工具"; then
            echo "✅ HTTP服务器响应正常，主页加载成功"

            # 测试API接口
            echo "🔧 测试API接口..."
            if curl -s --connect-timeout 5 http://localhost:5001/config | grep -q "QPS_LIMIT"; then
                echo "✅ API接口响应正常"
            else
                echo "⚠️  API接口可能有问题"
            fi
        else
            echo "❌ HTTP服务器响应异常"
        fi
    else
        echo "ℹ️  curl不可用，跳过HTTP测试"
    fi
    
    # 停止应用
    echo "🛑 停止应用..."
    kill $app_pid
    sleep 2
    
    # 确保进程已停止
    if kill -0 $app_pid 2>/dev/null; then
        echo "⚠️  强制停止应用..."
        kill -9 $app_pid
    fi
    
    echo "✅ 应用已停止"
else
    echo "❌ 应用启动失败或立即退出"
    exit 1
fi

echo ""
echo "🎉 可执行文件测试完成！"
echo "📁 可执行文件位置: $(pwd)/dist/pan123-scraper-mac"
echo "📊 文件大小: $file_size"
echo ""
echo "💡 使用说明:"
echo "   1. 确保config.json配置文件存在"
echo "   2. 运行: ./dist/pan123-scraper-mac"
echo "   3. 访问: http://localhost:5001"
