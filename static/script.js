// 🔒 全局防重复提交状态管理变量
let isGroupingInProgress = false;
let isRenamingInProgress = false;
let currentGroupingFolderId = null;

// 🌐 全局DOM元素引用（用于全局函数访问）
let contextMenuOrganizeFiles = null;
let operationResultsDiv = null;
let organizeFilesStatus = null;

// 🔧 全局辅助函数：显示状态消息
function showStatus(element, message, type) {
    if (!element) {
        console.error('showStatus: element is null');
        return;
    }
    element.innerHTML = message;
    element.className = `alert alert-${type === 'success' ? 'success' : (type === 'error' ? 'danger' : 'info')}`;
    element.style.display = 'block';
}

// 🔧 全局辅助函数：隐藏状态消息
function hideStatus(element) {
    if (!element) {
        console.error('hideStatus: element is null');
        return;
    }
    element.style.display = 'none';
}

document.addEventListener('DOMContentLoaded', () => {
    const getFilesForm = document.getElementById('getFilesForm');
    const folderIdInput = document.getElementById('folder_id');
    const limitInput = document.getElementById('limit');
    const fileListStatus = document.getElementById('fileListStatus');
    const fileListContainer = document.getElementById('fileListContainer');
    const fileCountSpan = document.getElementById('fileCount');
    const fileTableBody = document.querySelector('#fileTable tbody');
    const selectAllFilesCheckbox = document.getElementById('selectAllFiles');
    const scrapePreviewBtn = document.getElementById('scrapePreviewBtn');
    const recursiveGetFilesBtn = document.getElementById('recursiveGetFilesBtn');

    const scrapePreviewContainer = document.getElementById('scrapePreviewContainer');
    const scrapePreviewStatus = document.getElementById('scrapePreviewStatus');
    const previewCountSpan = document.getElementById('previewCount');
    const previewTableBody = document.querySelector('#previewTable tbody');
    const selectAllPreviewsCheckbox = document.getElementById('selectAllPreviews');
    const applyRenameBtn = document.getElementById('applyRenameBtn');
    const scrapeSortSelect = document.getElementById('scrapeSortSelect');

    // 移动文件相关元素
    const moveSelectedBtn = document.getElementById('moveSelectedBtn');
    const moveModal = document.getElementById('moveModal');
    const moveModalClose = document.getElementById('moveModalClose');
    const selectedFileCount = document.getElementById('selectedFileCount');
    const targetFolderIdInput = document.getElementById('targetFolderIdInput');
    const targetFolderPathInput = document.getElementById('targetFolderPathInput');
    const browseFolderBtn = document.getElementById('browseFolderBtn');
    const moveStatus = document.getElementById('moveStatus');
    const cancelMoveBtn = document.getElementById('cancelMoveBtn');
    const confirmMoveBtn = document.getElementById('confirmMoveBtn');

    // 重命名和删除相关元素
    const renameSelectedBtn = document.getElementById('renameSelectedBtn');
    const deleteSelectedBtn = document.getElementById('deleteSelectedBtn');
    const renameModal = document.getElementById('renameModal');
    const renameModalClose = document.getElementById('renameModalClose');
    const renameTableBody = document.getElementById('renameTableBody');
    const renameStatus = document.getElementById('renameStatus');
    const cancelRenameBtn = document.getElementById('cancelRenameBtn');
    const confirmRenameBtn = document.getElementById('confirmRenameBtn');

    // 新增的重命名UI元素
    const renameSelectedFileCount = document.getElementById('selectedFileCount');
    const selectAllRenameBtn = document.getElementById('selectAllRenameBtn');
    const deselectAllRenameBtn = document.getElementById('deselectAllRenameBtn');
    const selectAllRenameCheckbox = document.getElementById('selectAllRenameCheckbox');
    const resetNamesBtn = document.getElementById('resetNamesBtn');
    const toggleBatchOpsBtn = document.getElementById('toggleBatchOpsBtn');
    const previewChangesBtn = document.getElementById('previewChangesBtn');
    const confirmCount = document.getElementById('confirmCount');

    // 批量操作相关元素
    const batchOperations = document.querySelector('.batch-operations');
    const prefixInput = document.getElementById('prefixInput');
    const suffixInput = document.getElementById('suffixInput');
    const findInput = document.getElementById('findInput');
    const replaceInput = document.getElementById('replaceInput');
    const applyPrefixBtn = document.getElementById('applyPrefixBtn');
    const applySuffixBtn = document.getElementById('applySuffixBtn');
    const applyReplaceBtn = document.getElementById('applyReplaceBtn');
    const upperCaseBtn = document.getElementById('upperCaseBtn');
    const lowerCaseBtn = document.getElementById('lowerCaseBtn');
    const titleCaseBtn = document.getElementById('titleCaseBtn');

    // 新建文件夹相关元素
    const createFolderBtn = document.getElementById('createFolderBtn');
    const createFolderModal = document.getElementById('createFolderModal');
    const createFolderModalClose = document.getElementById('createFolderModalClose');
    const folderNameInput = document.getElementById('folderNameInput');
    const createFolderStatus = document.getElementById('createFolderStatus');
    const currentLocationName = document.getElementById('currentLocationName');
    const currentLocationPath = document.getElementById('currentLocationPath');
    const cancelCreateFolderBtn = document.getElementById('cancelCreateFolderBtn');
    const confirmCreateFolderBtn = document.getElementById('confirmCreateFolderBtn');

    // 文件夹浏览相关元素
    const folderBrowserModal = document.getElementById('folderBrowserModal');
    const folderBrowserModalClose = document.getElementById('folderBrowserModalClose');
    const browserPathLinks = document.getElementById('browserPathLinks');
    const folderBrowserTableBody = document.getElementById('folderBrowserTableBody');
    const selectedFolderInfo = document.getElementById('selectedFolderInfo');
    const selectedFolderName = document.getElementById('selectedFolderName');
    const selectedFolderPath = document.getElementById('selectedFolderPath');
    const folderBrowserStatus = document.getElementById('folderBrowserStatus');
    const cancelFolderBrowserBtn = document.getElementById('cancelFolderBrowserBtn');
    const confirmFolderSelectionBtn = document.getElementById('confirmFolderSelectionBtn');

    operationResultsDiv = document.getElementById('operationResults'); // 全局变量赋值
    const logDisplay = document.getElementById('logDisplay');
    const logContainer = document.getElementById('logContainer');

    // 弹窗相关元素
    const scrapePreviewModal = document.getElementById('scrapePreviewModal');
    const scrapePreviewModalClose = document.getElementById('scrapePreviewModalClose');
    const scrapePreviewModalCancel = document.getElementById('scrapePreviewModalCancel');
    const operationResultModal = document.getElementById('operationResultModal');
    const operationResultModalClose = document.getElementById('operationResultModalClose');
    const operationResultModalOk = document.getElementById('operationResultModalOk');

    // 日志控制相关元素
    const clearLogBtn = document.getElementById('clearLogBtn');
    const pauseLogBtn = document.getElementById('pauseLogBtn');
    const downloadLogBtn = document.getElementById('downloadLogBtn');

    // 弹窗控制函数
    function showScrapePreviewModal() {
        scrapePreviewModal.style.display = 'block';
        document.body.style.overflow = 'hidden'; // 防止背景滚动

        // 重置排序选择器为默认值
        if (scrapeSortSelect) {
            scrapeSortSelect.value = 'default';
        }
    }

    function hideScrapePreviewModal() {
        scrapePreviewModal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }

    function showOperationResultModal(content) {
        operationResultsDiv.innerHTML = content;
        operationResultModal.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }

    function hideOperationResultModal() {
        operationResultModal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }

    // 弹窗事件监听器
    scrapePreviewModalClose.addEventListener('click', hideScrapePreviewModal);
    scrapePreviewModalCancel.addEventListener('click', hideScrapePreviewModal);
    operationResultModalClose.addEventListener('click', hideOperationResultModal);
    operationResultModalOk.addEventListener('click', hideOperationResultModal);

    // 点击遮罩层关闭弹窗
    scrapePreviewModal.addEventListener('click', (e) => {
        if (e.target === scrapePreviewModal || e.target.classList.contains('ant-modal-mask')) {
            hideScrapePreviewModal();
        }
    });

    operationResultModal.addEventListener('click', (e) => {
        if (e.target === operationResultModal || e.target.classList.contains('ant-modal-mask')) {
            hideOperationResultModal();
        }
    });

    // ESC键关闭弹窗
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (scrapePreviewModal.style.display === 'block') {
                hideScrapePreviewModal();
            }
            if (operationResultModal.style.display === 'block') {
                hideOperationResultModal();
            }
        }
    });
    const floatLogBtn = document.getElementById('floatLogBtn');

    // 悬浮窗相关元素
    const floatingLogWindow = document.getElementById('floatingLogWindow');
    const floatingLogDisplay = document.getElementById('floatingLogDisplay');
    const dockLogBtn = document.getElementById('dockLogBtn');
    const minimizeLogBtn = document.getElementById('minimizeLogBtn');
    const closeFloatingLogBtn = document.getElementById('closeFloatingLogBtn');
    const floatingClearLogBtn = document.getElementById('floatingClearLogBtn');
    const floatingPauseLogBtn = document.getElementById('floatingPauseLogBtn');
    const floatingDownloadLogBtn = document.getElementById('floatingDownloadLogBtn');

    // 日志控制状态
    let logPaused = false;
    let isFloatingMode = false;
    let isMinimized = false;

    // 悬浮窗拖拽和调整大小相关变量
    let isDragging = false;
    let isResizing = false;
    let dragStartX, dragStartY, windowStartX, windowStartY;
    let resizeStartX, resizeStartY, windowStartWidth, windowStartHeight;

    // 配置相关DOM元素
    const configForm = document.getElementById('configForm');
    const qpsLimitInput = document.getElementById('qpsLimitInput');
    const chunkSizeInput = document.getElementById('chunkSizeInput');
    const maxWorkersInput = document.getElementById('maxWorkersInput');
    const storageTypeInput = document.getElementById('storageTypeInput');
    const clientIdInput = document.getElementById('clientIdInput');
    const clientSecretInput = document.getElementById('clientSecretInput');
    const pan115CookieInput = document.getElementById('pan115CookieInput');
    const pan123Config = document.getElementById('pan123Config');
    const pan115Config = document.getElementById('pan115Config');
    const currentStorageType = document.getElementById('currentStorageType');

    const tmdbApiKeyInput = document.getElementById('tmdbApiKeyInput');
    const aiApiKeyInput = document.getElementById('aiApiKeyInput');
    const aiApiUrlInput = document.getElementById('aiApiUrlInput');
    const modelInput = document.getElementById('modelInput');
    const groupingModelInput = document.getElementById('groupingModelInput');
    const languageInput = document.getElementById('languageInput');

    // 重试配置DOM元素
    const apiMaxRetriesInput = document.getElementById('apiMaxRetriesInput');
    const apiRetryDelayInput = document.getElementById('apiRetryDelayInput');
    const aiApiTimeoutInput = document.getElementById('aiApiTimeoutInput');
    const aiMaxRetriesInput = document.getElementById('aiMaxRetriesInput');
    const aiRetryDelayInput = document.getElementById('aiRetryDelayInput');
    const tmdbApiTimeoutInput = document.getElementById('tmdbApiTimeoutInput');
    const tmdbMaxRetriesInput = document.getElementById('tmdbMaxRetriesInput');
    const tmdbRetryDelayInput = document.getElementById('tmdbRetryDelayInput');
    const cloudApiMaxRetriesInput = document.getElementById('cloudApiMaxRetriesInput');
    const cloudApiRetryDelayInput = document.getElementById('cloudApiRetryDelayInput');
    const groupingMaxRetriesInput = document.getElementById('groupingMaxRetriesInput');
    const groupingRetryDelayInput = document.getElementById('groupingRetryDelayInput');
    const taskQueueTimeoutInput = document.getElementById('taskQueueTimeoutInput');

    const configStatus = document.getElementById('configStatus');

    // 模态框相关DOM元素
    const configModal = document.getElementById('configModal');
    const openConfigModalBtn = document.getElementById('openConfigModalBtn');
    const restartAppBtn = document.getElementById('restartAppBtn');
    const closeButton = configModal.querySelector('.close-button');

    // 新增的DOM元素和变量
    const currentPathDiv = document.getElementById('currentPath');
    const pathLinksSpan = document.getElementById('pathLinks');
    let currentFolderId = '0';
    let parentFolderId = '0';
    let currentPath = '/';
    let pathHistory = [{ name: '根目录', fileId: '0' }];

    // 右键菜单相关DOM元素
    const contextMenu = document.getElementById('contextMenu');
    const contextMenuSuggestRename = document.getElementById('contextMenuSuggestRename');
    contextMenuOrganizeFiles = document.getElementById('contextMenuOrganizeFiles'); // 全局变量赋值
    const contextMenuDeleteEmpty = document.getElementById('contextMenuDeleteEmpty');
    let activeFolderId = null; // 存储当前右键点击的文件夹ID
    let currentOperatingFolderId = null; // 存储当前正在操作的文件夹ID（用于模态框操作）

    // 文件夹信息面板相关DOM元素
    const folderInfoPanel = document.getElementById('folderInfoPanel');
    const folderInfoDetails = document.getElementById('folderInfoDetails');
    const closeFolderInfo = document.getElementById('closeFolderInfo');

    // 取消任务按钮
    const cancelTaskBtn = document.getElementById('cancelTaskBtn');
    const cancelRenameTaskBtn = document.getElementById('cancelRenameTaskBtn');
    const cancelScrapePreviewBtn = document.getElementById('cancelScrapePreviewBtn');

    // 取消当前任务的函数
    async function cancelCurrentTask() {
        try {
            const response = await fetch('/cancel_task', {
                method: 'POST'
            });
            const data = await response.json();

            if (data.success) {
                console.log('任务取消请求已发送');
                return true;
            } else {
                console.error('取消任务失败:', data.error);
                return false;
            }
        } catch (error) {
            console.error('取消任务请求失败:', error);
            return false;
        }
    }

    // 智能重命名相关元素
    const smartRenameModal = document.getElementById('smartRenameModal');
    const smartRenameModalClose = document.getElementById('smartRenameModalClose');
    const currentFolderName = document.getElementById('currentFolderName');
    const suggestedFolderName = document.getElementById('suggestedFolderName');
    const customFolderName = document.getElementById('customFolderName');
    const smartRenameStatus = document.getElementById('smartRenameStatus');
    const cancelSmartRenameBtn = document.getElementById('cancelSmartRenameBtn');
    const confirmSmartRenameBtn = document.getElementById('confirmSmartRenameBtn');

    // 智能文件分组相关元素
    const organizeFilesModal = document.getElementById('organizeFilesModal');
    const organizeFilesModalClose = document.getElementById('organizeFilesModalClose');
    const toggleFullscreenBtn = document.getElementById('toggleFullscreenBtn');
    const organizeFolderName = document.getElementById('organizeFolderName');
    const organizeFolderInfo = document.getElementById('organizeFolderInfo');
    const suggestedGroups = document.getElementById('suggestedGroups');
    const createSubfolders = document.getElementById('createSubfolders');
    const cancelOrganizeBtn = document.getElementById('cancelOrganizeBtn');
    const confirmOrganizeBtn = document.getElementById('confirmOrganizeBtn');

    // 🌐 初始化全局DOM元素引用
    organizeFilesStatus = document.getElementById('organizeFilesStatus');

    let currentFiles = [];
    let currentScrapedResults = [];
    let isUserScrolling = false;

    let lastCheckedFileCheckbox = null;
    let lastCheckedPreviewCheckbox = null;

    // 显示重命名结果弹出框
    function showRenameResultModal(results, isSuccess, errorMessage = '') {
        const renameResultModal = document.getElementById('renameResultModal');
        const renameResultSummary = document.getElementById('renameResultSummary');
        const renameResultDetails = document.getElementById('renameResultDetails');

        if (!renameResultModal || !renameResultSummary || !renameResultDetails) {
            console.error('重命名结果弹出框元素未找到');
            return;
        }

        const successCount = results.filter(r => r.status === 'success').length;
        const failedCount = results.filter(r => r.status === 'failed').length;

        // 创建结果统计
        let summaryHtml = '';
        if (isSuccess) {
            summaryHtml = `<div class="alert alert-success">
                <h5><i class="fas fa-check-circle"></i> 重命名操作完成</h5>
                <p><strong>成功:</strong> ${successCount} 个文件，<strong>失败:</strong> ${failedCount} 个文件</p>
            </div>`;
        } else {
            summaryHtml = `<div class="alert alert-warning">
                <h5><i class="fas fa-exclamation-triangle"></i> 重命名操作部分失败</h5>
                <p><strong>成功:</strong> ${successCount} 个文件，<strong>失败:</strong> ${failedCount} 个文件</p>
                ${errorMessage ? `<p><strong>错误:</strong> ${errorMessage}</p>` : ''}
            </div>`;
        }

        // 创建详细结果表格
        let detailsHtml = `
            <table class="table table-sm table-striped">
                <thead class="table-light sticky-top">
                    <tr>
                        <th style="width: 80px;">状态</th>
                        <th style="width: 40%;">原始文件名</th>
                        <th style="width: 40%;">新文件名</th>
                        <th style="width: 20%;">错误信息</th>
                    </tr>
                </thead>
                <tbody>`;

        results.forEach(result => {
            const statusIcon = result.status === 'success' ?
                '<i class="fas fa-check-circle text-success"></i>' :
                '<i class="fas fa-times-circle text-danger"></i>';
            const statusClass = result.status === 'success' ? 'table-success' : 'table-danger';

            detailsHtml += `<tr class="${statusClass}">
                <td>${statusIcon}</td>
                <td><small title="${result.original_name || '未知'}">${result.original_name || '未知'}</small></td>
                <td><small title="${result.new_name || '未知'}">${result.new_name || '未知'}</small></td>
                <td><small title="${result.error || ''}">${result.error || ''}</small></td>
            </tr>`;
        });

        detailsHtml += `</tbody></table>`;

        // 设置内容
        renameResultSummary.innerHTML = summaryHtml;
        renameResultDetails.innerHTML = detailsHtml;

        // 显示弹出框
        renameResultModal.style.display = 'block';
    }

    // 注意：showStatus 和 hideStatus 函数已移至全局作用域

    // 获取并显示实时日志
    async function fetchLogs() {
        // 如果日志被暂停，则不更新
        if (logPaused) {
            return;
        }

        try {
            const response = await fetch('/logs');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const logs = await response.json();

            const MAX_DISPLAY_LOGS = 1000;
            const startIndex = Math.max(0, logs.length - MAX_DISPLAY_LOGS);
            const logsToDisplay = logs.slice(startIndex);

            const fragment = document.createDocumentFragment();
            logsToDisplay.forEach(logEntryText => {
                const logEntry = document.createTextNode(logEntryText + '\n');
                fragment.appendChild(logEntry);
            });

            // 更新主面板日志
            if (logDisplay) {
                logDisplay.innerHTML = '';
                logDisplay.appendChild(fragment.cloneNode(true));

                // 自动滚动到底部（如果用户没有手动滚动）
                if (!isUserScrolling && logContainer) {
                    // 使用 setTimeout 确保DOM更新完成后再滚动
                    setTimeout(() => {
                        logContainer.scrollTop = logContainer.scrollHeight;
                    }, 10);
                }
            }

            // 更新悬浮窗日志
            if (floatingLogDisplay && isFloatingMode) {
                floatingLogDisplay.innerHTML = '';
                floatingLogDisplay.appendChild(fragment.cloneNode(true));

                // 自动滚动到底部
                floatingLogDisplay.scrollTop = floatingLogDisplay.scrollHeight;
            }
        } catch (error) {
            console.error('获取日志失败:', error);
        }
    }

    // 每隔一段时间获取一次日志
    setInterval(fetchLogs, 1000);
    fetchLogs();

    // 监听日志容器的滚动事件
    if (logContainer) {
        logContainer.addEventListener('scroll', () => {
            // 检查用户是否手动滚动离开底部
            const isAtBottom = logContainer.scrollTop + logContainer.clientHeight >= logContainer.scrollHeight - 10;
            isUserScrolling = !isAtBottom;
        });
    }

    // 获取并显示文件夹内容
    async function fetchFolderContent(folderId) {
        showStatus(fileListStatus, '正在获取目录内容...', 'info');
        fileTableBody.innerHTML = '';
        fileCountSpan.textContent = '0';
        scrapePreviewBtn.disabled = true;
        hideScrapePreviewModal();
        operationResultsDiv.innerHTML = '';
        selectAllFilesCheckbox.checked = false;

        // 调整容器高度
        setTimeout(adjustFileListContainerHeight, 100);

        try {
            const formData = new FormData();
            formData.append('folder_id', folderId);
            formData.append('limit', limitInput ? limitInput.value : 100);

            const response = await fetch('/get_folder_content', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                currentFolderId = data.current_folder_id;
                parentFolderId = data.parent_folder_id;
                currentPath = data.current_path;


                console.log('fetchFolderContent - currentFolderId:', currentFolderId, 'parentFolderId:', parentFolderId, 'currentPath:', currentPath);

                // 更新路径历史和面包屑导航
                updatePathLinks(data.path_parts);

                currentFiles = data.files_and_folders;
                fileCountSpan.textContent = currentFiles.length;
                renderFolderContent(currentFiles);

                // 清除状态信息，避免与标题重复
                fileListStatus.innerHTML = '';
                fileListStatus.className = '';
                fileListContainer.style.display = 'block';
                updateScrapeButtonState();

                // 内容渲染完成后调整高度
                setTimeout(adjustFileListContainerHeight, 200);
            } else {
                showStatus(fileListStatus, `获取目录内容失败: ${data.error}`, 'error');
                currentFiles = [];
                fileListContainer.style.display = 'none';
            }
        } catch (error) {
            showStatus(fileListStatus, `请求失败: ${error.message}`, 'error');
            currentFiles = [];
            fileListContainer.style.display = 'none';
        }
    }

    // 获取文件列表（递归）
    getFilesForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const folderId = folderIdInput.value || null;
        const limit = limitInput.value || 100;

        showStatus(fileListStatus, '正在获取文件列表...', 'info');
        fileTableBody.innerHTML = '';
        fileCountSpan.textContent = '0';
        scrapePreviewBtn.disabled = true;
        hideScrapePreviewModal();
        operationResultsDiv.innerHTML = '';
        selectAllFilesCheckbox.checked = false;

        try {
            const formData = new FormData();
            if (folderId) formData.append('folder_id', folderId);
            formData.append('limit', limit);

            const response = await fetch('/get_file_list', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                currentFiles = data.files;
                fileCountSpan.textContent = currentFiles.length;
                renderFileList(currentFiles);
                showStatus(fileListStatus, `成功获取 ${currentFiles.length} 个视频文件。`, 'success');
                fileListContainer.style.display = 'block';
                updateScrapeButtonState();
            } else {
                showStatus(fileListStatus, `获取文件列表失败: ${data.error}`, 'error');
                currentFiles = [];
                fileListContainer.style.display = 'none';
            }
        } catch (error) {
            showStatus(fileListStatus, `请求失败: ${error.message}`, 'error');
            currentFiles = [];
            fileListContainer.style.display = 'none';
        }
    });

    // 渲染文件夹内容
    function renderFolderContent(items) {
        fileTableBody.innerHTML = '';
        if (items.length === 0) {
            fileTableBody.innerHTML = '<tr><td colspan="3">此文件夹为空。</td></tr>';
            return;
        }

        // 按类型排序：文件夹在前，文件在后
        const sortedItems = items.sort((a, b) => {
            if (a.is_dir && !b.is_dir) return -1;
            if (!a.is_dir && b.is_dir) return 1;
            return a.name.localeCompare(b.name);
        });

        sortedItems.forEach(item => {
            const row = fileTableBody.insertRow();
            row.dataset.id = item.fileId;
            row.dataset.type = item.is_dir ? 'folder' : 'file';
            row.dataset.name = item.name;

            let iconClass = item.is_dir ? 'fas fa-folder' : 'fas fa-file-video';
            let nameHtml = item.name;
            let checkboxId = `${item.is_dir ? 'folder' : 'file'}Checkbox_${item.fileId}`;

            if (item.is_dir) {
                row.classList.add('folder-row');
                nameHtml = `
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <a href="javascript:;" class="folder-link" data-file-id="${item.fileId}">${item.name}</a>
                        <button class="btn btn-sm btn-outline-info folder-info-btn"
                                data-file-id="${item.fileId}"
                                title="点击查看文件夹信息"
                                style="padding: 2px 6px; font-size: 12px; margin-left: 8px;">
                            <i class="fas fa-info-circle"></i>
                        </button>
                    </div>
                `;

                row.innerHTML = `
                    <td><i class="${iconClass}" style="color: #1890ff;"></i></td>
                    <td>${nameHtml}</td>
                    <td>
                        <div class="form-check">
                            <input class="form-check-input selectable-item-checkbox" type="checkbox" id="${checkboxId}">
                            <label class="form-check-label" for="${checkboxId}"></label>
                        </div>
                    </td>
                `;

                // 在设置innerHTML之后设置dataset，这样不会被覆盖
                row.dataset.fileId = item.fileId;
            } else {
                const statusText = item.has_tmdb ? '已有TMDB' : (item.has_gb ? '已有大小' : '待处理');
                const statusClass = item.has_tmdb ? 'text-success' : (item.has_gb ? 'text-warning' : 'text-muted');

                row.innerHTML = `
                    <td><i class="${iconClass}" style="color: #52c41a;"></i></td>
                    <td>
                        ${item.name}
                        <br><small class="${statusClass}">${statusText} ${item.size || ''}</small>
                    </td>
                    <td>
                        <div class="form-check">
                            <input class="form-check-input selectable-item-checkbox" type="checkbox" id="${checkboxId}">
                            <label class="form-check-label" for="${checkboxId}"></label>
                        </div>
                    </td>
                `;
            }
        });

        // 为文件夹链接添加点击事件
        document.querySelectorAll('.folder-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const fileId = e.target.dataset.fileId;

                // 检查是否按住了Ctrl键或Cmd键（Mac）
                if (e.ctrlKey || e.metaKey) {
                    // 显示文件夹信息面板
                    showFolderInfoPanel(fileId);
                } else {
                    // 正常进入文件夹
                    fetchFolderContent(fileId);
                }
            });
        });

        // 为文件夹信息按钮添加点击事件
        document.querySelectorAll('.folder-info-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation(); // 阻止事件冒泡，避免触发文件夹链接的点击事件
                const fileId = btn.dataset.fileId;
                showFolderInfoPanel(fileId);
            });
        });

        // 为文件夹行添加右键菜单事件
        document.querySelectorAll('.folder-row').forEach(row => {
            row.addEventListener('contextmenu', (e) => {
                e.preventDefault(); // 阻止默认右键菜单
                activeFolderId = row.dataset.fileId; // 存储当前点击的文件夹ID
                console.log('右键菜单设置 activeFolderId:', activeFolderId);

                // 验证 activeFolderId 是否有效
                if (!activeFolderId || activeFolderId === 'undefined') {
                    console.error('无效的文件夹ID，无法显示右键菜单');
                    return;
                }

                showContextMenu(e.pageX, e.pageY);
            });
        });

        // 为所有可选择的复选框添加事件监听器
        document.querySelectorAll('.selectable-item-checkbox').forEach(checkbox => {
            checkbox.addEventListener('click', handleFileCheckboxClick);
        });

        updateScrapeButtonState();
    }

    // 渲染文件列表（递归模式）
    function renderFileList(files) {
        fileTableBody.innerHTML = '';
        if (files.length === 0) {
            fileTableBody.innerHTML = '<tr><td colspan="3">没有找到视频文件。</td></tr>';
            return;
        }

        files.forEach(file => {
            const row = fileTableBody.insertRow();
            row.dataset.id = file.fileId;
            row.dataset.type = 'file';
            row.dataset.name = file.filename;
            row.dataset.size = file.size || '';  // 添加文件大小到DOM

            const statusText = file.has_tmdb ? '已有TMDB' : (file.has_gb ? '已有大小' : '待处理');
            const statusClass = file.has_tmdb ? 'text-success' : (file.has_gb ? 'text-warning' : 'text-muted');

            row.innerHTML = `
                <td><i class="fas fa-file-video" style="color: #52c41a;"></i></td>
                <td>
                    ${file.filename}
                    <br><small class="${statusClass}">${statusText} ${file.size || ''}</small>
                </td>
                <td>
                    <div class="form-check">
                        <input class="form-check-input selectable-item-checkbox" type="checkbox" id="fileCheckbox_${file.fileId}">
                        <label class="form-check-label" for="fileCheckbox_${file.fileId}"></label>
                    </div>
                </td>
            `;
        });

        // 为所有可选择的复选框添加事件监听器
        document.querySelectorAll('.selectable-item-checkbox').forEach(checkbox => {
            checkbox.addEventListener('click', handleFileCheckboxClick);
        });

        updateScrapeButtonState();
    }

    // 更新路径导航
    function updatePathLinks(pathParts) {
        pathLinksSpan.innerHTML = '';
        pathHistory = [];

        // 构建路径历史
        pathParts.forEach((part) => {
            let displayName = part.name;
            if (part.fileId === '0') {
                displayName = '根目录';
            }
            pathHistory.push({ name: displayName, fileId: part.fileId });
        });

        // 渲染面包屑导航
        pathHistory.forEach((pathItem, index) => {
            const link = document.createElement('a');
            link.href = 'javascript:;';
            link.dataset.fileId = pathItem.fileId;
            link.classList.add('folder');
            link.setAttribute('rel', 'item');
            link.setAttribute('cate_name', pathItem.name);
            link.setAttribute('file_type', '0');
            link.setAttribute('type', 'show_title');
            link.setAttribute('aid', '1');
            link.setAttribute('titletext', pathItem.name);

            let linkContent = `<span>${pathItem.name}</span>`;
            if (pathItem.fileId === '0') {
                linkContent = `<span><s class="icon-home"></s>${pathItem.name}</span>`;
            }
            link.innerHTML = linkContent;

            link.addEventListener('click', (e) => {
                e.preventDefault();
                fetchFolderContent(pathItem.fileId);
            });

            pathLinksSpan.appendChild(link);

            if (index < pathHistory.length - 1) {
                const arrowIcon = document.createElement('i');
                arrowIcon.style.cursor = 'pointer';
                arrowIcon.style.display = 'inline-block';
                arrowIcon.setAttribute('btn', 'arrow_btn');
                arrowIcon.textContent = '›';
                pathLinksSpan.appendChild(arrowIcon);
            }
        });
    }

    // 更新刮削按钮状态
    function updateScrapeButtonState() {
        const allCheckboxes = document.querySelectorAll('.selectable-item-checkbox');
        const anyItemSelected = Array.from(allCheckboxes).some(cb => cb.checked);
        scrapePreviewBtn.disabled = !anyItemSelected || allCheckboxes.length === 0;
        moveSelectedBtn.disabled = !anyItemSelected || allCheckboxes.length === 0;
        renameSelectedBtn.disabled = !anyItemSelected || allCheckboxes.length === 0;
        deleteSelectedBtn.disabled = !anyItemSelected || allCheckboxes.length === 0;

        console.log('updateScrapeButtonState:', {
            checkboxCount: allCheckboxes.length,
            anyItemSelected: anyItemSelected,
            buttonDisabled: scrapePreviewBtn.disabled
        }); // 调试信息

        const allItemsSelected = Array.from(allCheckboxes).every(cb => cb.checked);
        selectAllFilesCheckbox.checked = allItemsSelected && allCheckboxes.length > 0;
    }

    // 处理文件和文件夹复选框的点击事件，实现 Shift 多选
    function handleFileCheckboxClick(e) {
        const currentCheckbox = e.target;
        if (e.shiftKey && lastCheckedFileCheckbox) {
            const checkboxes = Array.from(document.querySelectorAll('.selectable-item-checkbox'));
            const currentIndex = checkboxes.indexOf(currentCheckbox);
            const lastIndex = checkboxes.indexOf(lastCheckedFileCheckbox);

            const start = Math.min(currentIndex, lastIndex);
            const end = Math.max(currentIndex, lastIndex);

            for (let i = start; i <= end; i++) {
                checkboxes[i].checked = currentCheckbox.checked;
            }
        }
        lastCheckedFileCheckbox = currentCheckbox;
        updateScrapeButtonState();
    }

    // 全选/取消全选所有可选择的项目
    selectAllFilesCheckbox.addEventListener('change', (e) => {
        const isChecked = e.target.checked;
        document.querySelectorAll('.selectable-item-checkbox').forEach(checkbox => {
            checkbox.checked = isChecked;
        });
        scrapePreviewBtn.disabled = !isChecked;
        moveSelectedBtn.disabled = !isChecked;
        renameSelectedBtn.disabled = !isChecked;
        deleteSelectedBtn.disabled = !isChecked;
    });

    // 打开配置模态框
    openConfigModalBtn.addEventListener('click', () => {
        configModal.style.display = 'block';
        fetchConfig();
    });

    // 重启应用按钮事件
    restartAppBtn.addEventListener('click', async () => {
        // 首先检查重启功能状态
        try {
            const statusResponse = await fetch('/restart_status');
            const statusData = await statusResponse.json();

            if (!statusData.restart_available) {
                showOperationResultModal(`
                    <div class="alert alert-warning">
                        <i class="fas fa-exclamation-triangle"></i>
                        重启功能不可用: ${statusData.error || '未知原因'}
                        <br><br>
                        <strong>环境信息:</strong><br>
                        - 运行环境: ${statusData.environment || '未知'}<br>
                        - 平台: ${statusData.platform || '未知'}<br>
                        <br>
                        <strong>解决方案:</strong><br>
                        请手动重启应用程序
                    </div>
                `);
                return;
            }
        } catch (error) {
            console.warn('无法检查重启状态:', error);
        }

        if (confirm('确定要重启应用程序吗？这会中断当前操作。')) {
            try {
                // 显示重启进度
                showOperationResultModal(`
                    <div class="alert alert-info">
                        <i class="fas fa-spinner fa-spin"></i>
                        应用程序正在重启，请稍候...
                        <br><br>
                        <div class="progress" style="margin-top: 10px;">
                            <div class="progress-bar progress-bar-striped progress-bar-animated"
                                 style="width: 100%"></div>
                        </div>
                    </div>
                `);

                const response = await fetch('/restart', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                const data = await response.json();
                if (data.success) {
                    // 等待重启完成并尝试重新连接
                    let attempts = 0;
                    const maxAttempts = 20;

                    const checkConnection = async () => {
                        attempts++;
                        try {
                            const testResponse = await fetch('/config', {
                                method: 'GET',
                                timeout: 2000
                            });
                            if (testResponse.ok) {
                                showOperationResultModal(`
                                    <div class="alert alert-success">
                                        <i class="fas fa-check-circle"></i>
                                        应用程序重启成功！页面即将刷新...
                                    </div>
                                `);
                                setTimeout(() => {
                                    location.reload();
                                }, 1000);
                                return;
                            }
                        } catch (e) {
                            // 连接失败，继续尝试
                        }

                        if (attempts < maxAttempts) {
                            setTimeout(checkConnection, 1000);
                        } else {
                            showOperationResultModal(`
                                <div class="alert alert-warning">
                                    <i class="fas fa-exclamation-triangle"></i>
                                    重启可能已完成，但无法自动检测。
                                    <br><br>
                                    请手动刷新页面或检查应用状态。
                                    <br><br>
                                    <button class="btn btn-primary" onclick="location.reload()">
                                        <i class="fas fa-refresh"></i> 刷新页面
                                    </button>
                                </div>
                            `);
                        }
                    };

                    // 等待3秒后开始检查连接
                    setTimeout(checkConnection, 3000);

                } else {
                    showOperationResultModal(`
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-triangle"></i>
                            重启失败: ${data.error}
                            <br><br>
                            请尝试手动重启应用程序。
                        </div>
                    `);
                }
            } catch (error) {
                showOperationResultModal(`
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle"></i>
                        请求重启失败: ${error.message}
                        <br><br>
                        请尝试手动重启应用程序。
                    </div>
                `);
            }
        }
    });

    // 关闭模态框事件
    closeButton.addEventListener('click', () => {
        configModal.style.display = 'none';
    });

    // 点击模态框外部区域关闭模态框
    window.addEventListener('click', (event) => {
        if (event.target === configModal) {
            configModal.style.display = 'none';
        }
    });

    // 获取并显示配置
    async function fetchConfig() {
        try {
            const response = await fetch('/config');
            const config = await response.json();
            if (response.ok) {
                qpsLimitInput.value = config.QPS_LIMIT;
                chunkSizeInput.value = config.CHUNK_SIZE;
                maxWorkersInput.value = config.MAX_WORKERS;
                clientIdInput.value = config.CLIENT_ID;
                clientSecretInput.value = config.CLIENT_SECRET;

                if (tmdbApiKeyInput) tmdbApiKeyInput.value = config.TMDB_API_KEY || '';
                if (aiApiKeyInput) aiApiKeyInput.value = config.AI_API_KEY === '********' ? '' : config.AI_API_KEY || '';
                if (aiApiUrlInput) aiApiUrlInput.value = config.AI_API_URL || '';
                if (modelInput) modelInput.value = config.MODEL || '';
                if (groupingModelInput) groupingModelInput.value = config.GROUPING_MODEL || '';
                if (languageInput) languageInput.value = config.LANGUAGE || '';

                // 加载重试配置
                if (apiMaxRetriesInput) apiMaxRetriesInput.value = config.API_MAX_RETRIES || 3;
                if (apiRetryDelayInput) apiRetryDelayInput.value = config.API_RETRY_DELAY || 2;
                if (aiApiTimeoutInput) aiApiTimeoutInput.value = config.AI_API_TIMEOUT || 60;
                if (aiMaxRetriesInput) aiMaxRetriesInput.value = config.AI_MAX_RETRIES || 3;
                if (aiRetryDelayInput) aiRetryDelayInput.value = config.AI_RETRY_DELAY || 2;
                if (tmdbApiTimeoutInput) tmdbApiTimeoutInput.value = config.TMDB_API_TIMEOUT || 60;
                if (tmdbMaxRetriesInput) tmdbMaxRetriesInput.value = config.TMDB_MAX_RETRIES || 3;
                if (tmdbRetryDelayInput) tmdbRetryDelayInput.value = config.TMDB_RETRY_DELAY || 2;
                if (cloudApiMaxRetriesInput) cloudApiMaxRetriesInput.value = config.CLOUD_API_MAX_RETRIES || 3;
                if (cloudApiRetryDelayInput) cloudApiRetryDelayInput.value = config.CLOUD_API_RETRY_DELAY || 2;
                if (groupingMaxRetriesInput) groupingMaxRetriesInput.value = config.GROUPING_MAX_RETRIES || 3;
                if (groupingRetryDelayInput) groupingRetryDelayInput.value = config.GROUPING_RETRY_DELAY || 2;
                if (taskQueueTimeoutInput) taskQueueTimeoutInput.value = config.TASK_QUEUE_GET_TIMEOUT || 1.0;
                hideStatus(configStatus);
            } else {
                showStatus(configStatus, `获取配置失败: ${config.error || '未知错误'}`, 'error');
            }
        } catch (error) {
            showStatus(configStatus, `请求获取配置失败: ${error.message}`, 'error');
        }
    }

    // 保存配置
    configForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        showStatus(configStatus, '正在保存配置...', 'info');

        const configData = {
            QPS_LIMIT: parseInt(qpsLimitInput.value),
            CHUNK_SIZE: parseInt(chunkSizeInput.value),
            MAX_WORKERS: parseInt(maxWorkersInput.value),
            CLIENT_ID: clientIdInput.value,
            CLIENT_SECRET: clientSecretInput.value,

        };

        // 添加可选的配置项
        if (tmdbApiKeyInput && tmdbApiKeyInput.value) configData.TMDB_API_KEY = tmdbApiKeyInput.value;
        if (aiApiKeyInput && aiApiKeyInput.value) configData.AI_API_KEY = aiApiKeyInput.value;
        if (aiApiUrlInput && aiApiUrlInput.value) configData.AI_API_URL = aiApiUrlInput.value;
        if (modelInput && modelInput.value) configData.MODEL = modelInput.value;
        if (groupingModelInput && groupingModelInput.value) configData.GROUPING_MODEL = groupingModelInput.value;
        if (languageInput && languageInput.value) configData.LANGUAGE = languageInput.value;

        // 添加重试配置项
        if (apiMaxRetriesInput && apiMaxRetriesInput.value) configData.API_MAX_RETRIES = parseInt(apiMaxRetriesInput.value);
        if (apiRetryDelayInput && apiRetryDelayInput.value) configData.API_RETRY_DELAY = parseFloat(apiRetryDelayInput.value);
        if (aiApiTimeoutInput && aiApiTimeoutInput.value) configData.AI_API_TIMEOUT = parseInt(aiApiTimeoutInput.value);
        if (aiMaxRetriesInput && aiMaxRetriesInput.value) configData.AI_MAX_RETRIES = parseInt(aiMaxRetriesInput.value);
        if (aiRetryDelayInput && aiRetryDelayInput.value) configData.AI_RETRY_DELAY = parseFloat(aiRetryDelayInput.value);
        if (tmdbApiTimeoutInput && tmdbApiTimeoutInput.value) configData.TMDB_API_TIMEOUT = parseInt(tmdbApiTimeoutInput.value);
        if (tmdbMaxRetriesInput && tmdbMaxRetriesInput.value) configData.TMDB_MAX_RETRIES = parseInt(tmdbMaxRetriesInput.value);
        if (tmdbRetryDelayInput && tmdbRetryDelayInput.value) configData.TMDB_RETRY_DELAY = parseFloat(tmdbRetryDelayInput.value);
        if (cloudApiMaxRetriesInput && cloudApiMaxRetriesInput.value) configData.CLOUD_API_MAX_RETRIES = parseInt(cloudApiMaxRetriesInput.value);
        if (cloudApiRetryDelayInput && cloudApiRetryDelayInput.value) configData.CLOUD_API_RETRY_DELAY = parseFloat(cloudApiRetryDelayInput.value);
        if (groupingMaxRetriesInput && groupingMaxRetriesInput.value) configData.GROUPING_MAX_RETRIES = parseInt(groupingMaxRetriesInput.value);
        if (groupingRetryDelayInput && groupingRetryDelayInput.value) configData.GROUPING_RETRY_DELAY = parseFloat(groupingRetryDelayInput.value);
        if (taskQueueTimeoutInput && taskQueueTimeoutInput.value) configData.TASK_QUEUE_GET_TIMEOUT = parseFloat(taskQueueTimeoutInput.value);

        try {
            const response = await fetch('/save_config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(configData)
            });
            const data = await response.json();

            if (data.success) {
                showStatus(configStatus, data.message, 'success');
                fetchConfig();
                configModal.style.display = 'none';
            } else {
                showStatus(configStatus, `保存配置失败: ${data.error}`, 'error');
            }
        } catch (error) {
            showStatus(configStatus, `请求保存配置失败: ${error.message}`, 'error');
        }
    });

    // 预览刮削结果
    scrapePreviewBtn.addEventListener('click', async () => {
        console.log('scrapePreviewBtn clicked!'); // 调试信息

        const selectedItemElements = Array.from(document.querySelectorAll('.selectable-item-checkbox:checked'))
                                        .map(cb => cb.closest('tr'));

        console.log('selectedItemElements:', selectedItemElements); // 调试信息

        if (selectedItemElements.length === 0) {
            showStatus(scrapePreviewStatus, '请选择至少一个文件或文件夹进行刮削预览。', 'error');
            return;
        }

        // 收集所有选中的项目，包括文件和文件夹
        const itemsToScrape = selectedItemElements.map(row => {
            const id = row.dataset.id;
            const type = row.dataset.type;
            const name = row.dataset.name;

            console.log('Processing row:', { id, type, name }); // 调试信息 - 版本20250621

            // 从currentFiles中查找完整的文件信息，包括file_name字段
            // 确保类型匹配：id可能是字符串，fileId可能是数字
            const fileInfo = currentFiles.find(file =>
                file.fileId === id || file.fileId === parseInt(id) || file.fileId.toString() === id
            );

            console.log('查找文件信息:', { id, fileInfo, currentFilesLength: currentFiles.length }); // 调试信息 - 版本20250621

            if (fileInfo) {
                // 使用完整的文件信息
                console.log('使用完整文件信息:', fileInfo.file_name); // 调试信息
                return {
                    fileId: id,
                    name: name,  // 显示名称（只是文件名）
                    file_name: fileInfo.file_name,  // 完整路径
                    size: fileInfo.size || '',  // 文件大小
                    is_dir: type === 'folder',
                    parentFileId: row.dataset.parentFileId || currentFolderId
                };
            } else {
                // 如果在currentFiles中找不到，使用DOM数据（向后兼容）
                console.log('未找到文件信息，使用DOM数据'); // 调试信息
                return {
                    fileId: id,
                    name: name,
                    size: row.dataset.size || '',  // 尝试从DOM获取大小
                    is_dir: type === 'folder',
                    parentFileId: row.dataset.parentFileId || currentFolderId
                };
            }
        }).filter(Boolean);

        console.log('itemsToScrape:', itemsToScrape); // 调试信息

        if (itemsToScrape.length === 0) {
            showStatus(scrapePreviewStatus, '没有有效项目可供刮削。', 'error');
            return;
        }

        showStatus(scrapePreviewStatus, `🚀 开始刮削 ${itemsToScrape.length} 个项目，正在优化处理...`, 'info');
        previewTableBody.innerHTML = '';
        previewCountSpan.textContent = '0';
        applyRenameBtn.disabled = true;
        operationResultsDiv.innerHTML = '';

        // 🚀 添加进度显示
        const progressContainer = document.createElement('div');
        progressContainer.id = 'scrapeProgressContainer';
        progressContainer.innerHTML = `
            <div class="progress-info">
                <div class="progress-text">正在处理中...</div>
                <div class="progress-details">
                    <span id="progressFiles">0</span> / <span id="totalFiles">${itemsToScrape.length}</span> 个文件
                </div>
            </div>
        `;
        scrapePreviewStatus.appendChild(progressContainer);

        // 显示取消按钮，隐藏预览按钮
        scrapePreviewBtn.style.display = 'none';
        cancelScrapePreviewBtn.style.display = 'inline-block';

        try {
            const formData = new FormData();
            formData.append('files', JSON.stringify(itemsToScrape));

            const response = await fetch('/scrape_preview', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            // 恢复按钮状态
            scrapePreviewBtn.style.display = 'inline-block';
            cancelScrapePreviewBtn.style.display = 'none';

            // 🧹 清理进度显示
            const progressContainer = document.getElementById('scrapeProgressContainer');
            if (progressContainer) {
                progressContainer.remove();
            }

            if (data.success) {
                currentScrapedResults = data.results;
                previewCountSpan.textContent = currentScrapedResults.length;
                renderScrapePreview(currentScrapedResults);
                showStatus(scrapePreviewStatus, `成功获取 ${currentScrapedResults.length} 个刮削结果。`, 'success');
                showScrapePreviewModal();

                // 调试：确保工具栏可见性
                setTimeout(() => {
                    const toolbar = document.querySelector('#scrapePreviewContainer .toolbar-115');
                    const applyBtn = document.getElementById('applyRenameBtn');

                    if (toolbar && applyBtn) {
                        console.log('🔧 工具栏调试信息:', {
                            toolbarVisible: toolbar.offsetHeight > 0,
                            toolbarPosition: toolbar.getBoundingClientRect(),
                            buttonVisible: applyBtn.offsetHeight > 0,
                            buttonPosition: applyBtn.getBoundingClientRect(),
                            containerHeight: scrapePreviewContainer.offsetHeight
                        });

                        // 如果按钮不可见，强制修复
                        if (applyBtn.offsetHeight === 0) {
                            console.warn('⚠️ 应用重命名按钮不可见，尝试修复...');
                            toolbar.style.position = 'relative';
                            toolbar.style.zIndex = '50';
                            toolbar.style.visibility = 'visible';
                            toolbar.style.display = 'flex';
                            applyBtn.style.display = 'inline-flex';
                        }
                    }
                }, 100);
                applyRenameBtn.disabled = currentScrapedResults.filter(r => r.suggested_name).length === 0;
            } else {
                if (data.error && data.error.includes('取消')) {
                    showStatus(scrapePreviewStatus, '刮削预览已被用户取消', 'warning');
                } else {
                    showStatus(scrapePreviewStatus, `刮削预览失败: ${data.error}`, 'error');
                }
                currentScrapedResults = [];
                hideScrapePreviewModal();
            }
        } catch (error) {
            // 恢复按钮状态
            scrapePreviewBtn.style.display = 'inline-block';
            cancelScrapePreviewBtn.style.display = 'none';

            // 🧹 清理进度显示
            const progressContainer = document.getElementById('scrapeProgressContainer');
            if (progressContainer) {
                progressContainer.remove();
            }

            showStatus(scrapePreviewStatus, `请求失败: ${error.message}`, 'error');
            currentScrapedResults = [];
            hideScrapePreviewModal();
        }
    });

    // 刮削结果排序函数
    function sortScrapeResults(results, sortType) {
        const sortedResults = [...results];

        switch (sortType) {
            case 'name-asc':
                sortedResults.sort((a, b) => {
                    const nameA = (a.original_name || '').toLowerCase();
                    const nameB = (b.original_name || '').toLowerCase();
                    return nameA.localeCompare(nameB, 'zh-CN');
                });
                break;
            case 'name-desc':
                sortedResults.sort((a, b) => {
                    const nameA = (a.original_name || '').toLowerCase();
                    const nameB = (b.original_name || '').toLowerCase();
                    return nameB.localeCompare(nameA, 'zh-CN');
                });
                break;
            case 'suggested-asc':
                sortedResults.sort((a, b) => {
                    const nameA = (a.suggested_name || '').toLowerCase();
                    const nameB = (b.suggested_name || '').toLowerCase();
                    return nameA.localeCompare(nameB, 'zh-CN');
                });
                break;
            case 'suggested-desc':
                sortedResults.sort((a, b) => {
                    const nameA = (a.suggested_name || '').toLowerCase();
                    const nameB = (b.suggested_name || '').toLowerCase();
                    return nameB.localeCompare(nameA, 'zh-CN');
                });
                break;
            case 'size-desc':
                sortedResults.sort((a, b) => {
                    const sizeA = parseSizeToBytes(a.size || '0B');
                    const sizeB = parseSizeToBytes(b.size || '0B');
                    return sizeB - sizeA;
                });
                break;
            case 'size-asc':
                sortedResults.sort((a, b) => {
                    const sizeA = parseSizeToBytes(a.size || '0B');
                    const sizeB = parseSizeToBytes(b.size || '0B');
                    return sizeA - sizeB;
                });
                break;
            case 'status':
                sortedResults.sort((a, b) => {
                    // 有建议名称的排在前面，没有的排在后面
                    const hasA = a.suggested_name ? 1 : 0;
                    const hasB = b.suggested_name ? 1 : 0;
                    if (hasA !== hasB) {
                        return hasB - hasA;
                    }
                    // 状态相同时按原始名称排序
                    const nameA = (a.original_name || '').toLowerCase();
                    const nameB = (b.original_name || '').toLowerCase();
                    return nameA.localeCompare(nameB, 'zh-CN');
                });
                break;
            default:
                // 默认顺序，不排序
                break;
        }

        return sortedResults;
    }

    // 解析文件大小为字节数
    function parseSizeToBytes(sizeStr) {
        if (!sizeStr || typeof sizeStr !== 'string') return 0;

        const match = sizeStr.match(/^([\d.]+)\s*([KMGT]?B)$/i);
        if (!match) return 0;

        const value = parseFloat(match[1]);
        const unit = match[2].toUpperCase();

        switch (unit) {
            case 'TB': return value * 1024 * 1024 * 1024 * 1024;
            case 'GB': return value * 1024 * 1024 * 1024;
            case 'MB': return value * 1024 * 1024;
            case 'KB': return value * 1024;
            case 'B': return value;
            default: return 0;
        }
    }

    // 渲染刮削预览结果
    function renderScrapePreview(results) {
        // 获取当前排序方式
        const sortType = scrapeSortSelect ? scrapeSortSelect.value : 'default';
        const sortedResults = sortScrapeResults(results, sortType);

        previewTableBody.innerHTML = '';
        if (sortedResults.length === 0) {
            previewTableBody.innerHTML = '<tr><td colspan="6">没有刮削结果。</td></tr>';
            return;
        }
        sortedResults.forEach(result => {
            const row = previewTableBody.insertRow();
            row.dataset.fileId = result.fileId;
            row.dataset.originalName = result.original_name;
            row.dataset.suggestedName = result.suggested_name;

            // 格式化TMDB信息
            let tmdbInfoHtml = '<span style="color: #999; font-size: 9px;">无 TMDB 信息</span>';
            if (result.tmdb_info) {
                const title = result.tmdb_info.title || result.tmdb_info.name || '未知标题';
                const year = result.tmdb_info.release_date ? result.tmdb_info.release_date.substring(0, 4) :
                           (result.tmdb_info.first_air_date ? result.tmdb_info.first_air_date.substring(0, 4) : 'N/A');
                const mediaType = result.file_info && result.file_info.media_type === 'movie' ? '电影' : '剧集';
                const tmdbId = result.tmdb_info.id;

                // 截断过长的标题（字体增大后可以显示更多字符）
                const displayTitle = title.length > 24 ? title.substring(0, 24) + '...' : title;

                tmdbInfoHtml = `
                    <div class="tmdb-info">
                        <div class="tmdb-title" title="${title} (${year})">${displayTitle} (${year})</div>
                        <div class="tmdb-details">
                            ${mediaType} • ID: <span class="tmdb-id">${tmdbId}</span>
                        </div>
                    </div>
                `;
            }

            // 格式化状态
            let statusHtml = '';
            if (result.status === 'success') {
                statusHtml = '<span class="status-badge status-success">成功</span>';
            } else if (result.status === 'no_match') {
                statusHtml = '<span class="status-badge status-warning">无匹配</span>';
            } else {
                statusHtml = '<span class="status-badge status-error">错误</span>';
            }

            // 格式化文件大小（字体增大后可以显示更多字符）
            const sizeText = result.size || '未知';
            const formattedSize = sizeText.length > 10 ? sizeText.substring(0, 10) + '...' : sizeText;

            row.innerHTML = `
                <td>
                    <input class="preview-checkbox" type="checkbox" id="previewCheckbox_${result.fileId}" ${result.suggested_name ? 'checked' : 'disabled'}>
                </td>
                <td class="filename-cell">
                    <div class="filename-original" title="${result.original_name}">${result.original_name}</div>
                </td>
                <td class="filename-cell">
                    <div class="filename-suggested" title="${result.suggested_name || '无建议名称'}">${result.suggested_name || '<span style="color: #ff4d4f;">无建议名称</span>'}</div>
                </td>
                <td title="${sizeText}">${formattedSize}</td>
                <td>${tmdbInfoHtml}</td>
                <td>${statusHtml}</td>
            `;
        });

        // 为所有预览复选框添加事件监听器
        document.querySelectorAll('.preview-checkbox').forEach(checkbox => {
            checkbox.addEventListener('click', handlePreviewCheckboxClick);
        });
        updatePreviewSelectAllState();
    }

    // 处理预览复选框的点击事件，实现 Shift 多选
    function handlePreviewCheckboxClick(e) {
        const currentCheckbox = e.target;
        if (e.shiftKey && lastCheckedPreviewCheckbox) {
            const checkboxes = Array.from(document.querySelectorAll('.preview-checkbox:not([disabled])'));
            const currentIndex = checkboxes.indexOf(currentCheckbox);
            const lastIndex = checkboxes.indexOf(lastCheckedPreviewCheckbox);

            const start = Math.min(currentIndex, lastIndex);
            const end = Math.max(currentIndex, lastIndex);

            for (let i = start; i <= end; i++) {
                checkboxes[i].checked = currentCheckbox.checked;
            }
        }
        lastCheckedPreviewCheckbox = currentCheckbox;
        updatePreviewSelectAllState();
    }

    // 更新预览全选复选框状态
    function updatePreviewSelectAllState() {
        const allPreviewCheckboxes = document.querySelectorAll('.preview-checkbox:not([disabled])');
        const allPreviewsSelected = Array.from(allPreviewCheckboxes).every(cb => cb.checked);
        selectAllPreviewsCheckbox.checked = allPreviewsSelected && allPreviewCheckboxes.length > 0;

        // 更新底部按钮状态和信息
        updateScrapePreviewFooter();
    }

    // 更新刮削预览底部按钮状态和信息
    function updateScrapePreviewFooter() {
        const selectedCheckboxes = document.querySelectorAll('.preview-checkbox:checked');
        const totalCheckboxes = document.querySelectorAll('.preview-checkbox:not([disabled])');
        const selectedCount = selectedCheckboxes.length;
        const totalCount = totalCheckboxes.length;

        // 更新左侧信息
        const selectedFilesInfo = document.getElementById('selectedFilesInfo');
        const selectedCountSpan = document.getElementById('selectedCount');
        const applyBtn = document.getElementById('applyRenameBtn');

        if (selectedFilesInfo) {
            if (selectedCount === 0) {
                selectedFilesInfo.innerHTML = '<i class="fas fa-info-circle" style="color: var(--ant-primary-color); margin-right: 8px;"></i>请选择要重命名的文件';
            } else if (selectedCount === totalCount) {
                selectedFilesInfo.innerHTML = '<i class="fas fa-check-circle" style="color: #52c41a; margin-right: 8px;"></i>已选择全部文件';
            } else {
                selectedFilesInfo.innerHTML = `<i class="fas fa-check-circle" style="color: #52c41a; margin-right: 8px;"></i>已选择 ${selectedCount} 个文件`;
            }
        }

        // 更新按钮状态和计数
        if (applyBtn) {
            applyBtn.disabled = selectedCount === 0;

            if (selectedCountSpan) {
                if (selectedCount > 0) {
                    selectedCountSpan.textContent = selectedCount;
                    selectedCountSpan.style.display = 'inline-block';
                } else {
                    selectedCountSpan.style.display = 'none';
                }
            }
        }
    }

    // 全选/取消全选预览结果
    selectAllPreviewsCheckbox.addEventListener('change', (e) => {
        const isChecked = e.target.checked;
        document.querySelectorAll('.preview-checkbox').forEach(checkbox => {
            if (!checkbox.disabled) {
                checkbox.checked = isChecked;
            }
        });
        // 更新底部按钮状态
        updateScrapePreviewFooter();
    });

    // 刮削结果排序选择器事件监听
    if (scrapeSortSelect) {
        scrapeSortSelect.addEventListener('change', () => {
            if (currentScrapedResults && currentScrapedResults.length > 0) {
                renderScrapePreview(currentScrapedResults);
            }
        });
    }

    // 应用重命名
    applyRenameBtn.addEventListener('click', async () => {
        const selectedPreviewElements = Array.from(document.querySelectorAll('.preview-checkbox:checked'))
                                            .map(cb => cb.closest('tr'));

        if (selectedPreviewElements.length === 0) {
            showOperationResultModal('<div class="alert alert-danger"><i class="fas fa-exclamation-triangle"></i> 请选择至少一个文件进行重命名。</div>');
            return;
        }

        const renameData = selectedPreviewElements.map(row => {
            const fileId = row.dataset.fileId;
            const originalName = row.dataset.originalName;
            const suggestedName = row.dataset.suggestedName;

            return {
                fileId: fileId,
                original_name: originalName,
                suggested_name: suggestedName
            };
        });

        showOperationResultModal(`<div class="alert alert-info"><i class="fas fa-spinner fa-spin"></i> 正在批量重命名 ${renameData.length} 个文件（每批最多30个，QPS=1）...</div>`);

        try {
            const formData = new FormData();
            formData.append('rename_data', JSON.stringify(renameData));

            const response = await fetch('/apply_rename', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                // 处理新的格式返回结果
                if (data.results && Array.isArray(data.results)) {
                    // 关闭操作结果模态框
                    const operationResultModal = document.getElementById('operationResultModal');
                    if (operationResultModal) {
                        operationResultModal.style.display = 'none';
                    }
                    // 显示详细的重命名结果
                    showRenameResultModal(data.results, true);
                } else {
                    // 兼容旧格式
                    showOperationResultModal(`<div class="alert alert-success"><i class="fas fa-check-circle"></i> ${data.message || '重命名操作完成'}</div>`);
                }

                fetchLogs();

                // 延迟调用几次 fetchLogs，确保获取最新日志
                setTimeout(() => fetchLogs(), 1000);
                setTimeout(() => fetchLogs(), 3000);
            } else {
                // 处理失败情况，也可能包含部分结果
                if (data.results && Array.isArray(data.results)) {
                    // 关闭操作结果模态框
                    const operationResultModal = document.getElementById('operationResultModal');
                    if (operationResultModal) {
                        operationResultModal.style.display = 'none';
                    }
                    // 显示详细的重命名结果（包含失败信息）
                    showRenameResultModal(data.results, false, data.error);
                } else {
                    showOperationResultModal(`<div class="alert alert-danger"><i class="fas fa-exclamation-triangle"></i> 批量重命名失败: ${data.error}</div>`);
                }
            }
        } catch (error) {
            showOperationResultModal(`<div class="alert alert-danger"><i class="fas fa-exclamation-triangle"></i> 请求失败: ${error.message}</div>`);
        }
    });





    // 递归获取所有视频文件
    recursiveGetFilesBtn.addEventListener('click', async () => {
        showStatus(fileListStatus, '正在递归获取所有视频文件...', 'info');
        fileTableBody.innerHTML = '';
        fileCountSpan.textContent = '0';
        scrapePreviewBtn.disabled = true;
        hideScrapePreviewModal();
        operationResultsDiv.innerHTML = '';
        selectAllFilesCheckbox.checked = false;

        try {
            const formData = new FormData();
            formData.append('folder_id', currentFolderId);
            formData.append('limit', 100);

            const response = await fetch('/get_file_list', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                currentFiles = data.files;
                fileCountSpan.textContent = currentFiles.length;
                renderFileList(currentFiles);
                showStatus(fileListStatus, `成功获取 ${currentFiles.length} 个视频文件。`, 'success');
                fileListContainer.style.display = 'block';
                updateScrapeButtonState();
            } else {
                showStatus(fileListStatus, `获取文件列表失败: ${data.error}`, 'error');
                currentFiles = [];
                fileListContainer.style.display = 'none';
            }
        } catch (error) {
            showStatus(fileListStatus, `请求失败: ${error.message}`, 'error');
            currentFiles = [];
            fileListContainer.style.display = 'none';
        }
    });

    // 重命名结果弹出框事件处理
    const renameResultModal = document.getElementById('renameResultModal');
    const renameResultModalClose = document.getElementById('renameResultModalClose');
    const closeRenameResultBtn = document.getElementById('closeRenameResultBtn');
    const refreshFileListBtn = document.getElementById('refreshFileListBtn');

    if (renameResultModalClose) {
        renameResultModalClose.addEventListener('click', () => {
            renameResultModal.style.display = 'none';
        });
    }

    if (closeRenameResultBtn) {
        closeRenameResultBtn.addEventListener('click', () => {
            renameResultModal.style.display = 'none';
        });
    }

    if (refreshFileListBtn) {
        refreshFileListBtn.addEventListener('click', () => {
            renameResultModal.style.display = 'none';

            // 刷新文件列表
            if (currentFiles.length > 0 && currentFiles[0].filename) {
                // 如果当前显示的是递归获取的视频文件列表，重新获取视频文件
                recursiveGetFilesBtn.click();
            } else {
                // 否则刷新文件夹内容
                fetchFolderContent(currentFolderId);
            }
        });
    }

    // 点击弹出框外部关闭
    window.addEventListener('click', (event) => {
        if (event.target === renameResultModal) {
            renameResultModal.style.display = 'none';
        }
    });

    // 页面加载时获取根目录内容
    fetchFolderContent(currentFolderId);

    // 调试：检查按钮是否正确绑定
    console.log('scrapePreviewBtn element:', scrapePreviewBtn);
    console.log('scrapePreviewBtn disabled:', scrapePreviewBtn.disabled);

    // 显示右键菜单
    function showContextMenu(x, y) {
        contextMenu.style.left = `${x}px`;
        contextMenu.style.top = `${y}px`;
        contextMenu.style.display = 'block';

        // 不再自动获取文件夹属性，只在用户明确需要时获取
        // 移除自动调用 getFolderPropertiesAndDisplay，避免不必要的API请求
    }

    // 已移除 getFolderPropertiesAndDisplay 函数
    // 因为右键菜单不再包含"获取文件夹属性"选项，此函数不再需要

    // 隐藏右键菜单
    function hideContextMenu() {
        contextMenu.style.display = 'none';
        activeFolderId = null; // 清除激活的文件夹ID
    }

    // 显示文件夹信息面板
    async function showFolderInfoPanel(folderId) {
        // 显示面板
        folderInfoPanel.style.display = 'block';

        // 显示加载状态
        folderInfoDetails.innerHTML = '<div class="loading">正在加载文件夹信息...</div>';

        try {
            const response = await fetch(`/get_folder_info?folder_id=${folderId}`);
            const data = await response.json();

            if (data.success) {
                // 构建路径显示
                let pathDisplay = '';
                if (data.folder_path === '' || data.folder_path === null) {
                    pathDisplay = '根目录';
                } else {
                    pathDisplay = `根目录/${data.folder_path}`;
                }

                // 构建信息显示内容
                const infoHtml = `
                    <div class="folder-info-item">
                        <span class="folder-info-label">📁 文件夹路径</span>
                    </div>
                    <div class="folder-info-path">${pathDisplay}</div>

                    <div class="folder-info-item">
                        <span class="folder-info-label">📊 总项目数</span>
                        <span class="folder-info-value">${data.total_items}</span>
                    </div>

                    <div class="folder-info-item">
                        <span class="folder-info-label">📂 文件夹数</span>
                        <span class="folder-info-value">${data.folder_count}</span>
                    </div>

                    <div class="folder-info-item">
                        <span class="folder-info-label">📄 文件数</span>
                        <span class="folder-info-value">${data.file_count}</span>
                    </div>

                    <div class="folder-info-item">
                        <span class="folder-info-label">🎬 视频文件</span>
                        <span class="folder-info-value">${data.video_count}</span>
                    </div>

                    <div class="folder-info-item">
                        <span class="folder-info-label">💾 总大小</span>
                        <span class="folder-info-value">${data.size}</span>
                    </div>
                `;

                folderInfoDetails.innerHTML = infoHtml;
            } else {
                folderInfoDetails.innerHTML = `<div class="loading" style="color: var(--ant-error-color);">获取失败: ${data.error}</div>`;
            }
        } catch (error) {
            console.error('获取文件夹信息失败:', error);
            folderInfoDetails.innerHTML = '<div class="loading" style="color: var(--ant-error-color);">请求失败</div>';
        }
    }

    // 隐藏文件夹信息面板
    function hideFolderInfoPanel() {
        folderInfoPanel.style.display = 'none';
    }

    // 关闭按钮事件
    closeFolderInfo.addEventListener('click', hideFolderInfoPanel);

    // 隐藏右键菜单和文件夹信息面板 - 但不在菜单本身上点击时隐藏
    document.addEventListener('click', (e) => {
        // 如果点击的是右键菜单或其子元素，不隐藏菜单
        if (!contextMenu.contains(e.target)) {
            hideContextMenu();
        }

        // 如果点击的是文件夹信息面板或其子元素，不隐藏面板
        if (!folderInfoPanel.contains(e.target) && !e.target.classList.contains('folder-info-btn')) {
            hideFolderInfoPanel();
        }
    });

    // 移动选中文件按钮事件 - 直接打开文件夹浏览器
    moveSelectedBtn.addEventListener('click', () => {
        const selectedCheckboxes = document.querySelectorAll('.selectable-item-checkbox:checked');
        if (selectedCheckboxes.length === 0) {
            alert('请先选择要移动的文件');
            return;
        }

        // 直接显示文件夹浏览模态框
        // 重置选择状态
        selectedFolderName.textContent = '未选择';
        selectedFolderPath.textContent = '请选择一个文件夹作为移动目标';
        confirmFolderSelectionBtn.disabled = true;
        hideStatus(folderBrowserStatus);

        // 显示文件夹浏览模态框
        folderBrowserModal.style.display = 'block';

        // 加载根目录
        loadFolderBrowser(0);
    });

    // 关闭移动模态框
    moveModalClose.addEventListener('click', () => {
        moveModal.style.display = 'none';
    });

    cancelMoveBtn.addEventListener('click', () => {
        moveModal.style.display = 'none';
    });

    // 点击模态框外部关闭
    window.addEventListener('click', (event) => {
        if (event.target === moveModal) {
            moveModal.style.display = 'none';
        }
    });

    // 目标文件夹ID输入变化时更新确认按钮状态
    targetFolderIdInput.addEventListener('input', () => {
        const folderId = targetFolderIdInput.value.trim();
        confirmMoveBtn.disabled = !folderId || isNaN(parseInt(folderId));
    });

    // 浏览文件夹按钮事件
    browseFolderBtn.addEventListener('click', () => {
        // 重置选择状态
        selectedFolderName.textContent = '未选择';
        selectedFolderPath.textContent = '请选择一个文件夹作为移动目标';
        confirmFolderSelectionBtn.disabled = true;
        hideStatus(folderBrowserStatus);

        // 显示文件夹浏览模态框
        folderBrowserModal.style.display = 'block';

        // 加载根目录
        loadFolderBrowser(0);
    });

    // 关闭文件夹浏览模态框
    folderBrowserModalClose.addEventListener('click', () => {
        folderBrowserModal.style.display = 'none';
    });

    cancelFolderBrowserBtn.addEventListener('click', () => {
        folderBrowserModal.style.display = 'none';
    });

    // 点击模态框外部关闭
    window.addEventListener('click', (event) => {
        if (event.target === folderBrowserModal) {
            folderBrowserModal.style.display = 'none';
        }
    });

    // 确认文件夹选择并直接移动
    confirmFolderSelectionBtn.addEventListener('click', async () => {
        const selectedFolderId = confirmFolderSelectionBtn.dataset.folderId;
        const selectedPath = confirmFolderSelectionBtn.dataset.folderPath;

        if (!selectedFolderId) {
            alert('请选择一个目标文件夹');
            return;
        }

        // 获取选中的文件
        const selectedCheckboxes = document.querySelectorAll('.selectable-item-checkbox:checked');
        if (selectedCheckboxes.length === 0) {
            alert('没有选中的文件需要移动');
            folderBrowserModal.style.display = 'none';
            return;
        }

        const selectedItems = Array.from(selectedCheckboxes).map(cb => {
            const row = cb.closest('tr');
            const id = row.dataset.id;
            const name = row.dataset.name;
            const type = row.dataset.type;

            // 从currentFiles中查找完整的文件信息
            const fileInfo = currentFiles.find(file =>
                file.fileId === id || file.fileId === parseInt(id) || file.fileId.toString() === id
            );

            return {
                fileId: id,
                name: name,
                file_name: fileInfo ? fileInfo.file_name : name,
                is_dir: type === 'folder',
                parentFileId: row.dataset.parentFileId || currentFolderId
            };
        });

        // 显示移动状态
        showStatus(folderBrowserStatus, `正在移动 ${selectedItems.length} 个文件到 ${selectedPath}...`, 'info');
        confirmFolderSelectionBtn.disabled = true;

        try {
            const formData = new FormData();
            formData.append('move_data', JSON.stringify(selectedItems));
            formData.append('target_folder_id', selectedFolderId);

            const response = await fetch('/move_files_direct', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                showStatus(folderBrowserStatus, `成功移动 ${selectedItems.length} 个文件到 ${selectedPath}！`, 'success');
                showOperationResultModal(`<div class="alert alert-success"><i class="fas fa-check-circle"></i> 成功移动 ${selectedItems.length} 个文件到 ${selectedPath}</div>`);

                // 关闭文件夹浏览模态框并刷新文件列表
                setTimeout(() => {
                    folderBrowserModal.style.display = 'none';

                    // 如果当前显示的是递归获取的视频文件列表，重新获取视频文件
                    if (currentFiles.length > 0 && currentFiles[0].filename) {
                        // 重新获取视频文件列表
                        recursiveGetFilesBtn.click();
                    } else {
                        // 否则刷新文件夹内容
                        fetchFolderContent(currentFolderId);
                    }
                }, 1500);
            } else {
                showStatus(folderBrowserStatus, `移动失败: ${data.error}`, 'error');
                confirmFolderSelectionBtn.disabled = false;
            }
        } catch (error) {
            showStatus(folderBrowserStatus, `请求失败: ${error.message}`, 'error');
            confirmFolderSelectionBtn.disabled = false;
        }
    });

    // 加载文件夹浏览器内容
    window.loadFolderBrowser = async function(folderId) {
        try {
            const response = await fetch(`/get_folder_content/${folderId}`);
            const data = await response.json();

            if (data.success) {
                renderFolderBrowser(data.folders, data.path_info, folderId);
            } else {
                console.error('加载文件夹失败:', data.error);
            }
        } catch (error) {
            console.error('请求失败:', error);
        }
    };

    // 渲染文件夹浏览器
    function renderFolderBrowser(folders, pathInfo, currentFolderId) {
        // 清空表格
        folderBrowserTableBody.innerHTML = '';

        // 渲染路径导航
        renderBrowserPath(pathInfo, currentFolderId);

        // 添加选择当前文件夹的选项
        const currentFolderName = currentFolderId === 0 ? '根目录' :
            (pathInfo.path_parts && pathInfo.path_parts.length > 0 ?
             pathInfo.path_parts[pathInfo.path_parts.length - 1].name : '当前文件夹');
        const currentFolderPath = pathInfo.path_parts ?
            pathInfo.path_parts.map(p => p.name).join('/') : '根目录';

        const currentRow = folderBrowserTableBody.insertRow();
        currentRow.innerHTML = `
            <td><i class="fas fa-folder-open text-primary"></i></td>
            <td><strong>${currentFolderName} (当前位置)</strong></td>
            <td>
                <input type="radio" name="selectedFolder" value="${currentFolderId}"
                       onchange="selectFolder(${currentFolderId}, '${currentFolderName}', '${currentFolderPath}')"
                       class="form-check-input">
            </td>
        `;

        // 添加返回上级目录选项（如果不是根目录）
        if (currentFolderId !== 0) {
            const backRow = folderBrowserTableBody.insertRow();
            backRow.innerHTML = `
                <td><i class="fas fa-level-up-alt text-secondary"></i></td>
                <td><a href="#" onclick="loadFolderBrowser(${pathInfo.parent_id || 0})" class="text-decoration-none"><strong>.. (返回上级)</strong></a></td>
                <td></td>
            `;
        }

        // 渲染文件夹列表
        folders.forEach(folder => {
            const row = folderBrowserTableBody.insertRow();
            row.innerHTML = `
                <td><i class="fas fa-folder text-warning"></i></td>
                <td>
                    <a href="#" onclick="loadFolderBrowser(${folder.fileId})" class="text-decoration-none text-primary">
                        ${folder.filename}
                    </a>
                </td>
                <td>
                    <input type="radio" name="selectedFolder" value="${folder.fileId}"
                           onchange="selectFolder(${folder.fileId}, '${folder.filename}', '${folder.file_name || folder.filename}')"
                           class="form-check-input">
                </td>
            `;
        });
    }

    // 渲染路径导航
    function renderBrowserPath(pathInfo, currentFolderId) {
        let pathHtml = '';

        if (pathInfo && pathInfo.path_parts && pathInfo.path_parts.length > 0) {
            // 直接使用后端返回的 path_parts，不重复添加根目录
            pathInfo.path_parts.forEach((part, index) => {
                if (index > 0) {
                    pathHtml += ' / ';
                }
                pathHtml += `<a href="#" onclick="loadFolderBrowser(${part.id})" class="text-decoration-none">${part.name}</a>`;
            });
        } else {
            // 如果没有路径信息，默认显示根目录
            pathHtml = '<a href="#" onclick="loadFolderBrowser(0)" class="text-decoration-none">根目录</a>';
        }

        browserPathLinks.innerHTML = pathHtml;
    }

    // 选择文件夹
    window.selectFolder = function(folderId, folderName, folderPath) {
        selectedFolderName.textContent = folderName;
        selectedFolderPath.textContent = folderPath || folderName;
        confirmFolderSelectionBtn.disabled = false;
        confirmFolderSelectionBtn.dataset.folderId = folderId;
        confirmFolderSelectionBtn.dataset.folderPath = folderPath || folderName;

        // 高亮选中的行
        document.querySelectorAll('#folderBrowserTableBody tr').forEach(row => {
            row.classList.remove('table-active');
        });

        // 找到选中的单选按钮对应的行并高亮
        const selectedRadio = document.querySelector(`input[name="selectedFolder"][value="${folderId}"]`);
        if (selectedRadio) {
            const selectedRow = selectedRadio.closest('tr');
            if (selectedRow) {
                selectedRow.classList.add('table-active');
            }
        }
    };

    // 确认移动按钮事件
    confirmMoveBtn.addEventListener('click', async () => {
        const targetFolderId = parseInt(targetFolderIdInput.value.trim());
        if (!targetFolderId || isNaN(targetFolderId)) {
            showStatus(moveStatus, '请输入有效的目标文件夹ID。', 'error');
            return;
        }

        const selectedCheckboxes = document.querySelectorAll('.selectable-item-checkbox:checked');
        const selectedItems = Array.from(selectedCheckboxes).map(cb => {
            const row = cb.closest('tr');
            const id = row.dataset.id;
            const name = row.dataset.name;
            const type = row.dataset.type;

            // 从currentFiles中查找完整的文件信息
            const fileInfo = currentFiles.find(file =>
                file.fileId === id || file.fileId === parseInt(id) || file.fileId.toString() === id
            );

            return {
                fileId: id,
                name: name,
                file_name: fileInfo ? fileInfo.file_name : name,
                is_dir: type === 'folder',
                parentFileId: row.dataset.parentFileId || currentFolderId
            };
        });

        showStatus(moveStatus, `正在移动 ${selectedItems.length} 个文件到文件夹 ${targetFolderId}...`, 'info');
        confirmMoveBtn.disabled = true;

        try {
            const formData = new FormData();
            formData.append('move_data', JSON.stringify(selectedItems));
            formData.append('target_folder_id', targetFolderId.toString());

            const response = await fetch('/move_files_direct', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                showStatus(moveStatus, `成功移动 ${selectedItems.length} 个文件！`, 'success');
                showOperationResultModal(`<div class="alert alert-success"><i class="fas fa-check-circle"></i> 成功移动 ${selectedItems.length} 个文件到文件夹 ${targetFolderId}</div>`);

                // 关闭模态框并刷新文件列表
                setTimeout(() => {
                    moveModal.style.display = 'none';
                    // 如果当前显示的是递归获取的视频文件列表，重新获取视频文件
                    if (currentFiles.length > 0 && currentFiles[0].filename) {
                        // 重新获取视频文件列表
                        recursiveGetFilesBtn.click();
                    } else {
                        // 否则刷新文件夹内容
                        fetchFolderContent(currentFolderId);
                    }
                }, 1500);
            } else {
                showStatus(moveStatus, `移动失败: ${data.error}`, 'error');
                confirmMoveBtn.disabled = false;
            }
        } catch (error) {
            showStatus(moveStatus, `请求失败: ${error.message}`, 'error');
            confirmMoveBtn.disabled = false;
        }
    });

    // 存储当前重命名的文件数据
    let currentRenameFiles = [];

    // 重命名选中文件
    renameSelectedBtn.addEventListener('click', () => {
        const selectedCheckboxes = document.querySelectorAll('.selectable-item-checkbox:checked');
        if (selectedCheckboxes.length === 0) {
            alert('请选择至少一个文件进行重命名。');
            return;
        }

        // 收集选中的文件信息
        currentRenameFiles = [];
        selectedCheckboxes.forEach(checkbox => {
            const row = checkbox.closest('tr');
            const fileId = row.dataset.id;
            const fileName = row.dataset.name;
            const fileSize = row.dataset.size || '';
            const isDir = row.dataset.type === 'folder';

            currentRenameFiles.push({
                fileId: fileId,
                originalName: fileName,
                newName: fileName,
                fileSize: fileSize,
                isDir: isDir,
                selected: true
            });
        });

        // 初始化重命名界面
        initializeRenameModal();

        // 显示重命名模态框
        renameModal.style.display = 'block';
    });

    // 初始化重命名模态框
    function initializeRenameModal() {
        // 更新文件计数
        updateRenameFileCount();

        // 填充重命名表格
        renderRenameTable();

        // 重置状态
        renameStatus.innerHTML = '';
        confirmRenameBtn.disabled = false;
        batchOperations.style.display = 'none';

        // 清空批量操作输入框
        prefixInput.value = '';
        suffixInput.value = '';
        findInput.value = '';
        replaceInput.value = '';


    }





    // 渲染重命名表格
    function renderRenameTable() {
        renameTableBody.innerHTML = '';

        currentRenameFiles.forEach((file, index) => {
            const row = renameTableBody.insertRow();
            row.className = 'rename-file-row';
            if (file.selected) row.classList.add('selected');

            // 格式化文件大小
            const sizeDisplay = file.fileSize ? `<span class="file-size-badge">${file.fileSize}</span>` : '';

            row.innerHTML = `
                <td>
                    <div class="form-check">
                        <input class="form-check-input rename-file-checkbox" type="checkbox"
                               ${file.selected ? 'checked' : ''} data-index="${index}">
                    </div>
                </td>
                <td>
                    <div class="original-filename" title="${file.originalName}">
                        ${file.isDir ? '📁' : '📄'} ${file.originalName}
                    </div>
                </td>
                <td>
                    <input type="text" class="rename-input"
                           value="${file.newName}"
                           data-index="${index}"
                           data-original="${file.originalName}">
                </td>
                <td>${sizeDisplay}</td>
                <td>
                    <button class="btn btn-sm btn-outline-secondary rename-action-btn reset-btn"
                            data-index="${index}" title="重置">
                        <i class="fas fa-undo"></i>
                    </button>
                </td>
            `;
        });

        // 更新全选复选框状态
        updateSelectAllCheckbox();

        // 绑定事件
        bindRenameTableEvents();
    }

    // 绑定重命名表格事件
    function bindRenameTableEvents() {
        // 文件复选框事件
        document.querySelectorAll('.rename-file-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const index = parseInt(e.target.dataset.index);
                currentRenameFiles[index].selected = e.target.checked;

                // 更新行样式
                const row = e.target.closest('tr');
                if (e.target.checked) {
                    row.classList.add('selected');
                } else {
                    row.classList.remove('selected');
                }

                updateRenameFileCount();
                updateSelectAllCheckbox();
            });
        });

        // 重命名输入框事件
        document.querySelectorAll('.rename-input').forEach(input => {
            input.addEventListener('input', (e) => {
                const index = parseInt(e.target.dataset.index);
                const originalName = e.target.dataset.original;
                currentRenameFiles[index].newName = e.target.value;

                // 更新输入框样式
                if (e.target.value !== originalName) {
                    e.target.classList.add('changed');
                } else {
                    e.target.classList.remove('changed');
                }

                updateRenameFileCount();
            });
        });

        // 重置按钮事件
        document.querySelectorAll('.reset-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const index = parseInt(e.target.closest('button').dataset.index);
                const file = currentRenameFiles[index];
                file.newName = file.originalName;

                // 更新输入框
                const input = document.querySelector(`.rename-input[data-index="${index}"]`);
                input.value = file.originalName;
                input.classList.remove('changed');

                updateRenameFileCount();
            });
        });
    }

    // 更新文件计数
    function updateRenameFileCount() {
        const selectedCount = currentRenameFiles.filter(f => f.selected).length;
        const changedCount = currentRenameFiles.filter(f => f.selected && f.newName !== f.originalName).length;

        if (renameSelectedFileCount) {
            renameSelectedFileCount.textContent = selectedCount;
        }
        if (confirmCount) {
            confirmCount.textContent = changedCount;
        }

        // 更新确认按钮状态
        confirmRenameBtn.disabled = changedCount === 0;
    }

    // 更新全选复选框状态
    function updateSelectAllCheckbox() {
        const checkboxes = document.querySelectorAll('.rename-file-checkbox');
        const checkedCount = document.querySelectorAll('.rename-file-checkbox:checked').length;

        if (selectAllRenameCheckbox) {
            selectAllRenameCheckbox.checked = checkboxes.length > 0 && checkedCount === checkboxes.length;
            selectAllRenameCheckbox.indeterminate = checkedCount > 0 && checkedCount < checkboxes.length;
        }
    }

    // 确认重命名
    confirmRenameBtn.addEventListener('click', async () => {
        const selectedFiles = currentRenameFiles.filter(f => f.selected && f.newName !== f.originalName);

        if (selectedFiles.length === 0) {
            showStatus(renameStatus, '没有需要重命名的文件。', 'warning');
            return;
        }

        const renameData = selectedFiles.map(file => ({
            fileId: file.fileId,
            newName: file.newName.trim(),
            isDir: file.isDir
        }));

        confirmRenameBtn.disabled = true;
        showStatus(renameStatus, `正在重命名 ${renameData.length} 个文件...`, 'info');

        try {
            const formData = new FormData();
            formData.append('rename_data', JSON.stringify(renameData));

            const response = await fetch('/rename_files', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                showStatus(renameStatus, data.message, 'success');

                // 显示重命名结果详情
                if (data.results && data.results.length > 0) {
                    showRenameResultModal(data);
                }

                // 关闭重命名模态框，但不刷新文件列表
                setTimeout(() => {
                    renameModal.style.display = 'none';
                    confirmRenameBtn.disabled = true;
                    // 不再自动刷新文件列表，保持用户当前的浏览状态
                }, 1500);
            } else {
                showStatus(renameStatus, `重命名失败: ${data.error}`, 'error');
                confirmRenameBtn.disabled = false;
            }
        } catch (error) {
            showStatus(renameStatus, `请求失败: ${error.message}`, 'error');
            confirmRenameBtn.disabled = false;
        }
    });

    // 删除选中文件
    deleteSelectedBtn.addEventListener('click', async () => {
        const selectedCheckboxes = document.querySelectorAll('.selectable-item-checkbox:checked');
        if (selectedCheckboxes.length === 0) {
            alert('请选择至少一个文件进行删除。');
            return;
        }

        // 收集选中的文件信息
        const selectedFiles = [];
        selectedCheckboxes.forEach(checkbox => {
            const row = checkbox.closest('tr');
            const fileId = row.dataset.id;
            const fileName = row.dataset.name;
            const isDir = row.dataset.type === 'folder';

            selectedFiles.push({
                fileId: fileId,
                fileName: fileName,
                isDir: isDir
            });
        });

        // 确认删除
        const fileNames = selectedFiles.map(f => f.fileName).join('\n');
        const confirmMessage = `确定要删除以下 ${selectedFiles.length} 个项目吗？\n\n${fileNames}\n\n此操作不可撤销！`;

        if (!confirm(confirmMessage)) {
            return;
        }

        deleteSelectedBtn.disabled = true;
        showOperationResultModal(`<div class="alert alert-info"><i class="fas fa-spinner fa-spin"></i> 正在删除 ${selectedFiles.length} 个项目...</div>`);

        try {
            const formData = new FormData();
            formData.append('delete_data', JSON.stringify(selectedFiles));

            const response = await fetch('/delete_files', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                showOperationResultModal(`<div class="alert alert-success"><i class="fas fa-check-circle"></i> ${data.message}</div>`);

                // 刷新文件列表
                setTimeout(() => {
                    if (currentFiles.length > 0 && currentFiles[0].filename) {
                        recursiveGetFilesBtn.click();
                    } else {
                        fetchFolderContent(currentFolderId);
                    }
                }, 1500);
            } else {
                showOperationResultModal(`<div class="alert alert-danger"><i class="fas fa-exclamation-triangle"></i> 删除失败: ${data.error}</div>`);
            }
        } catch (error) {
            showOperationResultModal(`<div class="alert alert-danger"><i class="fas fa-exclamation-triangle"></i> 请求失败: ${error.message}</div>`);
        } finally {
            deleteSelectedBtn.disabled = false;
        }
    });

    // 全选/取消全选功能
    if (selectAllRenameBtn) {
        selectAllRenameBtn.addEventListener('click', () => {
            currentRenameFiles.forEach(file => file.selected = true);
            renderRenameTable();
        });
    }

    if (deselectAllRenameBtn) {
        deselectAllRenameBtn.addEventListener('click', () => {
            currentRenameFiles.forEach(file => file.selected = false);
            renderRenameTable();
        });
    }

    if (selectAllRenameCheckbox) {
        selectAllRenameCheckbox.addEventListener('change', (e) => {
            currentRenameFiles.forEach(file => file.selected = e.target.checked);
            renderRenameTable();
        });
    }

    // 批量操作切换
    if (toggleBatchOpsBtn) {
        toggleBatchOpsBtn.addEventListener('click', () => {
            const isVisible = batchOperations.style.display !== 'none';
            batchOperations.style.display = isVisible ? 'none' : 'block';
            toggleBatchOpsBtn.innerHTML = isVisible ?
                '<i class="fas fa-tools"></i> 批量操作' :
                '<i class="fas fa-times"></i> 隐藏批量操作';
        });
    }

    // 批量操作：添加前缀
    if (applyPrefixBtn) {
        applyPrefixBtn.addEventListener('click', () => {
            const prefix = prefixInput.value;
            if (!prefix) return;

            currentRenameFiles.forEach(file => {
                if (file.selected) {
                    file.newName = prefix + file.newName;
                }
            });
            renderRenameTable();
        });
    }

    // 批量操作：添加后缀
    if (applySuffixBtn) {
        applySuffixBtn.addEventListener('click', () => {
            const suffix = suffixInput.value;
            if (!suffix) return;

            currentRenameFiles.forEach(file => {
                if (file.selected) {
                    const ext = file.originalName.lastIndexOf('.');
                    if (ext > 0) {
                        const name = file.newName.substring(0, file.newName.lastIndexOf('.'));
                        const extension = file.newName.substring(file.newName.lastIndexOf('.'));
                        file.newName = name + suffix + extension;
                    } else {
                        file.newName = file.newName + suffix;
                    }
                }
            });
            renderRenameTable();
        });
    }

    // 批量操作：查找替换
    if (applyReplaceBtn) {
        applyReplaceBtn.addEventListener('click', () => {
            const findText = findInput.value;
            const replaceText = replaceInput.value;
            if (!findText) return;

            currentRenameFiles.forEach(file => {
                if (file.selected) {
                    file.newName = file.newName.replace(new RegExp(findText, 'g'), replaceText);
                }
            });
            renderRenameTable();
        });
    }

    // 批量操作：大小写转换
    if (upperCaseBtn) {
        upperCaseBtn.addEventListener('click', () => {
            currentRenameFiles.forEach(file => {
                if (file.selected) {
                    file.newName = file.newName.toUpperCase();
                }
            });
            renderRenameTable();
        });
    }

    if (lowerCaseBtn) {
        lowerCaseBtn.addEventListener('click', () => {
            currentRenameFiles.forEach(file => {
                if (file.selected) {
                    file.newName = file.newName.toLowerCase();
                }
            });
            renderRenameTable();
        });
    }

    if (titleCaseBtn) {
        titleCaseBtn.addEventListener('click', () => {
            currentRenameFiles.forEach(file => {
                if (file.selected) {
                    file.newName = file.newName.replace(/\w\S*/g, (txt) =>
                        txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase()
                    );
                }
            });
            renderRenameTable();
        });
    }

    // 重置名称
    if (resetNamesBtn) {
        resetNamesBtn.addEventListener('click', () => {
            currentRenameFiles.forEach(file => {
                if (file.selected) {
                    file.newName = file.originalName;
                }
            });
            renderRenameTable();
        });
    }



    // 预览更改
    if (previewChangesBtn) {
        previewChangesBtn.addEventListener('click', () => {
            const changedFiles = currentRenameFiles.filter(f => f.selected && f.newName !== f.originalName);

            if (changedFiles.length === 0) {
                showStatus(renameStatus, '没有需要预览的更改。', 'info');
                return;
            }

            let previewHtml = '<div class="preview-changes"><h6>预览更改:</h6>';
            changedFiles.forEach(file => {
                previewHtml += `
                    <div class="preview-item">
                        <span class="preview-old">${file.originalName}</span>
                        <span>→</span>
                        <span class="preview-new">${file.newName}</span>
                    </div>
                `;
            });
            previewHtml += '</div>';

            showStatus(renameStatus, previewHtml, 'info');
        });
    }

    // 重命名模态框关闭事件
    renameModalClose.addEventListener('click', () => {
        renameModal.style.display = 'none';
        confirmRenameBtn.disabled = true;
    });

    cancelRenameBtn.addEventListener('click', () => {
        renameModal.style.display = 'none';
        confirmRenameBtn.disabled = true;
    });

    // 点击模态框外部关闭
    window.addEventListener('click', (event) => {
        if (event.target === renameModal) {
            renameModal.style.display = 'none';
            confirmRenameBtn.disabled = true; // 重置按钮状态
        }
        if (event.target === createFolderModal) {
            createFolderModal.style.display = 'none';
            confirmCreateFolderBtn.disabled = true; // 重置按钮状态
        }
    });

    // 新建文件夹功能
    createFolderBtn.addEventListener('click', () => {
        // 更新当前位置信息
        updateCurrentLocationInfo();

        // 清空输入框和状态
        folderNameInput.value = '';
        createFolderStatus.innerHTML = '';
        confirmCreateFolderBtn.disabled = true;

        // 显示模态框
        createFolderModal.style.display = 'block';

        // 聚焦到输入框
        setTimeout(() => {
            folderNameInput.focus();
        }, 100);
    });

    // 文件夹名称输入监听
    folderNameInput.addEventListener('input', () => {
        const folderName = folderNameInput.value.trim();
        confirmCreateFolderBtn.disabled = folderName.length === 0;
    });

    // 确认创建文件夹
    confirmCreateFolderBtn.addEventListener('click', async () => {
        const folderName = folderNameInput.value.trim();

        if (!folderName) {
            showStatus(createFolderStatus, '请输入文件夹名称。', 'error');
            return;
        }

        confirmCreateFolderBtn.disabled = true;
        showStatus(createFolderStatus, '正在创建文件夹...', 'info');

        try {
            const formData = new FormData();
            formData.append('folder_name', folderName);
            formData.append('parent_id', currentFolderId);

            const response = await fetch('/create_folder', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                showStatus(createFolderStatus, data.message, 'success');

                // 关闭模态框并刷新文件列表
                setTimeout(() => {
                    createFolderModal.style.display = 'none';
                    confirmCreateFolderBtn.disabled = true;
                    // 刷新当前文件列表
                    fetchFolderContent(currentFolderId);
                }, 1500);
            } else {
                showStatus(createFolderStatus, `创建失败: ${data.error}`, 'error');
                confirmCreateFolderBtn.disabled = false;
            }
        } catch (error) {
            showStatus(createFolderStatus, `请求失败: ${error.message}`, 'error');
            confirmCreateFolderBtn.disabled = false;
        }
    });

    // 新建文件夹模态框关闭事件
    createFolderModalClose.addEventListener('click', () => {
        createFolderModal.style.display = 'none';
        confirmCreateFolderBtn.disabled = true;
    });

    cancelCreateFolderBtn.addEventListener('click', () => {
        createFolderModal.style.display = 'none';
        confirmCreateFolderBtn.disabled = true;
    });

    // 更新当前位置信息
    function updateCurrentLocationInfo() {
        // 获取当前路径信息
        const pathLinksElement = document.getElementById('pathLinks');
        if (pathLinksElement && pathLinksElement.textContent) {
            currentLocationPath.textContent = pathLinksElement.textContent;
            // 获取最后一个文件夹名称作为当前位置
            const pathParts = pathLinksElement.textContent.split(' / ');
            currentLocationName.textContent = pathParts[pathParts.length - 1] || '根目录';
        } else {
            currentLocationName.textContent = '根目录';
            currentLocationPath.textContent = '/';
        }
    }

    // 智能重命名文件夹功能
    contextMenuSuggestRename.addEventListener('click', async () => {
        console.log('智能重命名点击，当前 activeFolderId:', activeFolderId);
        console.log('activeFolderId 类型:', typeof activeFolderId);

        if (!activeFolderId || activeFolderId === 'null' || activeFolderId === null || activeFolderId === undefined) {
            console.error('无效的文件夹ID:', activeFolderId);
            alert('请先右键点击一个文件夹');
            hideContextMenu();
            return;
        }

        // 保存当前的 activeFolderId，因为 hideContextMenu 可能会影响它
        const currentActiveFolderId = activeFolderId;
        currentOperatingFolderId = currentActiveFolderId; // 保存到全局变量供后续操作使用
        hideContextMenu();

        // 获取当前文件夹名称
        const folderRow = document.querySelector(`.folder-row[data-file-id="${currentActiveFolderId}"]`);
        const folderName = folderRow ? folderRow.querySelector('a').textContent : '未知文件夹';

        currentFolderName.textContent = folderName;
        suggestedFolderName.value = '';
        customFolderName.value = '';
        smartRenameStatus.innerHTML = '';
        confirmSmartRenameBtn.disabled = true;

        // 显示取消按钮，隐藏其他按钮
        cancelRenameTaskBtn.style.display = 'inline-block';
        cancelSmartRenameBtn.style.display = 'none';
        confirmSmartRenameBtn.style.display = 'none';

        // 显示模态框
        smartRenameModal.style.display = 'block';

        // 获取智能建议
        try {
            suggestedFolderName.value = '正在分析文件夹内容...';
            console.log('发送智能重命名请求，文件夹ID:', currentActiveFolderId);

            const formData = new FormData();
            formData.append('folder_id', currentActiveFolderId);

            const response = await fetch('/suggest_folder_name', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            // 恢复按钮状态
            cancelRenameTaskBtn.style.display = 'none';
            cancelSmartRenameBtn.style.display = 'inline-block';
            confirmSmartRenameBtn.style.display = 'inline-block';

            if (data.success) {
                suggestedFolderName.value = data.suggested_name;
                customFolderName.value = data.suggested_name;
                confirmSmartRenameBtn.disabled = false;
                showStatus(smartRenameStatus, `基于 ${data.file_count} 个视频文件生成建议`, 'success');
            } else {
                suggestedFolderName.value = '';
                showStatus(smartRenameStatus, `生成建议失败: ${data.error}`, 'error');

                // 检查是否是取消错误
                if (data.cancelled) {
                    showStatus(smartRenameStatus, '任务已被用户取消', 'warning');
                }
            }
        } catch (error) {
            // 恢复按钮状态
            cancelRenameTaskBtn.style.display = 'none';
            cancelSmartRenameBtn.style.display = 'inline-block';
            confirmSmartRenameBtn.style.display = 'inline-block';

            suggestedFolderName.value = '';
            showStatus(smartRenameStatus, `请求失败: ${error.message}`, 'error');
        }
    });

    // 智能文件分组功能
    if (contextMenuOrganizeFiles) {
        contextMenuOrganizeFiles.addEventListener('click', async () => {
        console.log('🎯 智能分组点击 - activeFolderId:', activeFolderId, '类型:', typeof activeFolderId);
        console.log('🔒 当前状态 - isGroupingInProgress:', isGroupingInProgress, 'currentGroupingFolderId:', currentGroupingFolderId);

        if (!activeFolderId || activeFolderId === 'null' || activeFolderId === null || activeFolderId === undefined) {
            console.error('无效的文件夹ID:', activeFolderId);
            hideContextMenu();
            return;
        }

        // 🔒 防重复提交检查
        if (isGroupingInProgress) {
            // 检查是否是同一文件夹的重复请求
            if (currentGroupingFolderId === activeFolderId) {
                console.log('🚫 同一文件夹重复请求被阻止');
                showStatus(operationResultsDiv, '⚠️ 该文件夹正在处理中，请避免重复操作', 'warning');
                contextMenu.style.display = 'none';
                return;
            } else {
                // 如果是不同文件夹，显示通用提示
                console.log('🚫 不同文件夹请求被阻止，当前正在处理:', currentGroupingFolderId);
                showStatus(operationResultsDiv, '⚠️ 智能分组正在进行中，请稍候...', 'warning');
                contextMenu.style.display = 'none';
                return;
            }
        }

        // 🔒 设置防重复提交状态
        isGroupingInProgress = true;
        currentGroupingFolderId = activeFolderId;

        // 🎨 添加任务进行中的视觉提示
        organizeFilesModal.classList.add('task-in-progress');

        // 保存当前的 activeFolderId
        const currentActiveFolderId = activeFolderId;
        currentOperatingFolderId = currentActiveFolderId; // 保存到全局变量供后续操作使用

        // 隐藏右键菜单但不清除 activeFolderId（在分组完成后再清除）
        contextMenu.style.display = 'none';

        console.log('🎯 开始智能文件分组，文件夹ID:', currentActiveFolderId);
        console.log('🔒 设置状态 - isGroupingInProgress:', isGroupingInProgress, 'currentGroupingFolderId:', currentGroupingFolderId);

        // 获取当前文件夹名称
        const folderRow = document.querySelector(`.folder-row[data-file-id="${currentActiveFolderId}"]`);
        const folderName = folderRow ? folderRow.querySelector('a').textContent : '未知文件夹';

        organizeFolderName.textContent = folderName;
        organizeFolderInfo.textContent = '正在分析文件夹内容...';

        // 显示现代化的进度指示器
        suggestedGroups.innerHTML = `
            <div class="grouping-progress">
                <div class="progress-spinner"></div>
                <div class="progress-text">🤖 AI正在分析文件内容</div>
                <div class="progress-detail">正在识别文件类型和分组模式...</div>
            </div>
        `;

        organizeFilesStatus.innerHTML = '';
        confirmOrganizeBtn.disabled = true;

        // 显示取消按钮，隐藏其他按钮
        cancelTaskBtn.style.display = 'inline-block';
        cancelOrganizeBtn.style.display = 'none';
        confirmOrganizeBtn.style.display = 'none';

        // 显示模态框
        organizeFilesModal.style.display = 'block';

        // 获取文件夹属性和分组信息
        try {
            const formData = new FormData();
            formData.append('folder_id', currentActiveFolderId);
            formData.append('folder_name', folderName);
            formData.append('include_grouping', 'true'); // 启用智能分组分析

            const response = await fetch('/get_folder_properties', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            // 恢复按钮状态
            cancelTaskBtn.style.display = 'none';
            cancelOrganizeBtn.style.display = 'inline-block';
            confirmOrganizeBtn.style.display = 'inline-block';

            if (data.success) {
                // 🚀 检查是否使用了新的任务队列系统
                if (data.use_task_queue && data.task_id) {
                    // 使用任务队列系统，开始轮询任务状态
                    organizeFolderInfo.textContent = `正在分析文件夹...`;
                    showStatus(organizeFilesStatus, `✅ ${data.message}`, 'success');

                    // 开始轮询任务状态
                    startTaskStatusPolling(data.task_id);
                    return;
                }

                // 传统模式：直接显示结果
                organizeFolderInfo.textContent = `包含 ${data.count} 个视频文件，总大小 ${data.size}`;

                if (data.movie_info && data.movie_info.length > 0) {
                    // 计算统计信息
                    const totalGroups = data.movie_info.length;
                    const totalFiles = data.count;
                    let groupedFiles = 0;

                    data.movie_info.forEach(group => {
                        const fileIds = group.fileIds || group.files || [];
                        groupedFiles += fileIds.length;
                    });

                    const ungroupedFiles = totalFiles - groupedFiles;

                    // 显示统计信息面板
                    let groupsHtml = `
                        <div class="grouping-stats">
                            <div class="stat-item">
                                <div class="stat-number">${totalGroups}</div>
                                <div class="stat-label">🎯 分组数量</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-number">${groupedFiles}</div>
                                <div class="stat-label">📁 已分组文件</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-number">${ungroupedFiles}</div>
                                <div class="stat-label">📄 独立文件</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-number">${Math.round((groupedFiles / totalFiles) * 100)}%</div>
                                <div class="stat-label">✅ 分组覆盖率</div>
                            </div>
                        </div>
                    `;

                    // 添加批量操作控制面板
                    groupsHtml += `
                        <div class="batch-controls">
                            <div class="batch-controls-left">
                                <div class="selection-info">
                                    <i class="fas fa-info-circle"></i>
                                    <span id="selectionCount">已选择 ${totalGroups} 个分组</span>
                                </div>
                            </div>
                            <div class="batch-controls-right">
                                <button type="button" class="btn btn-sm btn-outline-primary" id="selectAllGroups">
                                    <i class="fas fa-check-square"></i> 全选
                                </button>
                                <button type="button" class="btn btn-sm btn-outline-secondary" id="deselectAllGroups">
                                    <i class="fas fa-square"></i> 取消全选
                                </button>
                            </div>
                        </div>
                    `;

                    // 调试日志
                    console.log('收到的分组数据:', data.movie_info);

                    data.movie_info.forEach((group, index) => {
                        const groupName = group.group_name || `分组 ${index + 1}`;
                        // 兼容不同的字段名称
                        const fileIds = group.fileIds || group.files || [];
                        const fileNames = group.file_names || [];
                        const fileCount = fileIds.length;

                        // 调试日志
                        console.log(`分组 ${index}: ${groupName}, fileIds: ${fileIds.length}, fileNames: ${fileNames.length}`, fileNames);

                        // 根据实际的video_files数据计算匹配的文件数量
                        let actualFileCount = 0;
                        if (data.video_files && fileIds.length > 0) {
                            // 通过文件名匹配来计算实际的文件数量
                            const videoFileIds = data.video_files.map(f => f.fileId);
                            actualFileCount = fileIds.filter(id => videoFileIds.includes(id)).length;
                        }

                        const safeFileCount = fileCount || 0;
                        const displayCount = actualFileCount > 0 ? `${actualFileCount} 个文件` : `${safeFileCount} 个文件`;
                        console.log(`🔢 分组 ${index} 文件数量: actualFileCount=${actualFileCount}, fileCount=${fileCount}, displayCount="${displayCount}"`);

                        // 生成现代化的文件列表
                        let fileListHtml = '';
                        if (fileNames && fileNames.length > 0) {
                            // 使用智能排序（按集数或字母顺序）
                            const sortedFileNames = smartSortFiles(fileNames, groupName);

                            fileListHtml = '<div class="group-files">';
                            sortedFileNames.forEach(fileName => {
                                fileListHtml += `
                                    <div class="file-item">
                                        <i class="fas fa-play-circle file-icon"></i>
                                        <span class="file-name" title="${fileName}">${fileName}</span>
                                    </div>
                                `;
                            });
                            fileListHtml += '</div>';
                        }

                        // 现代化分组卡片
                        groupsHtml += `
                            <div class="group-item" data-group-index="${index}">
                                <div class="group-header">
                                    <input class="group-checkbox" type="checkbox" value="${index}" id="group_${index}" checked>
                                    <div class="group-title">${groupName}</div>
                                    <div class="group-count">${displayCount}</div>
                                </div>
                                ${fileListHtml}
                            </div>
                        `;
                    });

                    suggestedGroups.innerHTML = groupsHtml;

                    // 存储分组数据供后续使用
                    window.currentGroupsData = data.movie_info;

                    // 显示排序控件
                    const groupSortControls = document.querySelector('.group-sort-controls');
                    if (groupSortControls) {
                        groupSortControls.style.display = 'flex';
                    }

                    // 添加事件监听器
                    setupGroupingEventListeners();
                    setupGroupSortingEventListeners();

                    // 🎯 自动应用默认排序（名称A-Z）
                    const groupSortSelect = document.getElementById('groupSortSelect');
                    if (groupSortSelect) {
                        groupSortSelect.value = 'name-asc';
                        sortGroups('name-asc');
                    }

                    confirmOrganizeBtn.disabled = false;
                    showStatus(organizeFilesStatus, `✅ 成功生成 ${data.movie_info.length} 个智能分组`, 'success');

                    // 🔒 重置防重复提交状态
                    resetGroupingState();
                } else {
                    // 显示空状态
                    suggestedGroups.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-state-icon">
                                <i class="fas fa-folder-open"></i>
                            </div>
                            <div class="empty-state-title">未发现可分组的内容</div>
                            <div class="empty-state-description">
                                当前文件夹中的文件无法识别出明确的分组模式。<br>
                                这可能是因为文件名格式不规范或文件类型不支持智能分组。
                            </div>
                        </div>
                    `;
                    showStatus(organizeFilesStatus, '⚠️ 无法生成有效的文件分组建议', 'warning');

                    // 🔒 重置防重复提交状态
                    resetGroupingState();
                }
            } else {
                suggestedGroups.innerHTML = '<div class="text-center text-muted">获取文件信息失败</div>';
                showStatus(organizeFilesStatus, `获取失败: ${data.error}`, 'error');

                // 检查是否是取消错误
                if (data.cancelled) {
                    showStatus(organizeFilesStatus, '任务已被用户取消', 'warning');
                }

                // 检查是否是任务队列错误
                if (data.task_queue_error) {
                    showStatus(organizeFilesStatus, `🚦 ${data.error}`, 'warning');
                }

                // 检查是否是限流错误
                if (data.rate_limited) {
                    const remainingTime = data.remaining_time || 60;
                    showStatus(organizeFilesStatus, `🚦 ${data.error}`, 'warning');

                    // 显示倒计时
                    startRateLimitCountdown(remainingTime);
                }

                // 🔒 重置防重复提交状态
                resetGroupingState();
            }
        } catch (error) {
            // 恢复按钮状态
            cancelTaskBtn.style.display = 'none';
            cancelOrganizeBtn.style.display = 'inline-block';
            confirmOrganizeBtn.style.display = 'inline-block';

            suggestedGroups.innerHTML = '<div class="text-center text-muted">请求失败</div>';

            // 检查是否是网络错误或其他特殊错误
            let errorMessage = `请求失败: ${error.message}`;
            if (error.message.includes('Failed to fetch')) {
                errorMessage = '🌐 网络连接失败，请检查网络连接后重试';
            }

            showStatus(organizeFilesStatus, errorMessage, 'error');

            // 🔒 重置防重复提交状态
            resetGroupingState();
        }
        });
    } else {
        console.error('contextMenuOrganizeFiles 元素未找到，无法绑定智能分组事件');
    }

    // 自定义文件夹名称输入监听
    customFolderName.addEventListener('input', () => {
        const customName = customFolderName.value.trim();
        confirmSmartRenameBtn.disabled = customName.length === 0;
    });

    // 确认智能重命名
    confirmSmartRenameBtn.addEventListener('click', async () => {
        const newName = customFolderName.value.trim();

        if (!newName || !currentOperatingFolderId) {
            showStatus(smartRenameStatus, '请输入有效的文件夹名称', 'error');
            return;
        }

        confirmSmartRenameBtn.disabled = true;
        showStatus(smartRenameStatus, '正在重命名文件夹...', 'info');

        try {
            const formData = new FormData();
            formData.append('rename_data', JSON.stringify([{
                fileId: currentOperatingFolderId,
                new_name: newName,
                type: 'folder'
            }]));

            const response = await fetch('/rename_files', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                showStatus(smartRenameStatus, '文件夹重命名成功！', 'success');

                // 关闭模态框并刷新文件列表
                setTimeout(() => {
                    smartRenameModal.style.display = 'none';
                    confirmSmartRenameBtn.disabled = true;
                    // 刷新当前文件列表
                    fetchFolderContent(currentFolderId);
                }, 1500);
            } else {
                showStatus(smartRenameStatus, `重命名失败: ${data.error}`, 'error');
                confirmSmartRenameBtn.disabled = false;
            }
        } catch (error) {
            showStatus(smartRenameStatus, `请求失败: ${error.message}`, 'error');
            confirmSmartRenameBtn.disabled = false;
        }
    });

    // 确认智能文件分组
    confirmOrganizeBtn.addEventListener('click', async () => {
        if (!currentOperatingFolderId) {
            console.error('没有设置操作的文件夹ID');
            return;
        }

        // 获取选中的分组
        const selectedGroups = [];
        const checkboxes = document.querySelectorAll('.group-checkbox:checked');

        if (checkboxes.length === 0) {
            showStatus(organizeFilesStatus, '请至少选择一个分组进行整理', 'warning');
            return;
        }

        checkboxes.forEach(checkbox => {
            const groupIndex = parseInt(checkbox.value);
            if (window.currentGroupsData && window.currentGroupsData[groupIndex]) {
                selectedGroups.push(window.currentGroupsData[groupIndex]);
            }
        });

        if (selectedGroups.length === 0) {
            showStatus(organizeFilesStatus, '没有有效的分组数据', 'error');
            return;
        }

        confirmOrganizeBtn.disabled = true;
        showStatus(organizeFilesStatus, `正在整理 ${selectedGroups.length} 个选中的分组...`, 'info');

        try {
            const formData = new FormData();
            formData.append('folder_id', currentOperatingFolderId);
            formData.append('selected_groups', JSON.stringify(selectedGroups));

            const response = await fetch('/execute_selected_groups', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                showStatus(organizeFilesStatus, data.message, 'success');

                // 关闭模态框并刷新文件列表
                setTimeout(() => {
                    organizeFilesModal.style.display = 'none';
                    confirmOrganizeBtn.disabled = true;
                    hideGroupSortControls();
                    resetGroupingState(); // 🔒 重置分组状态
                    // 刷新当前文件列表
                    fetchFolderContent(currentFolderId);
                }, 2000);
            } else {
                showStatus(organizeFilesStatus, `整理失败: ${data.error}`, 'error');
                confirmOrganizeBtn.disabled = false;
                resetGroupingState(); // 🔒 重置分组状态
            }
        } catch (error) {
            showStatus(organizeFilesStatus, `请求失败: ${error.message}`, 'error');
            confirmOrganizeBtn.disabled = false;
            resetGroupingState(); // 🔒 重置分组状态
        }
    });

    // 智能重命名模态框关闭事件
    smartRenameModalClose.addEventListener('click', () => {
        smartRenameModal.style.display = 'none';
        confirmSmartRenameBtn.disabled = true;
    });

    cancelSmartRenameBtn.addEventListener('click', () => {
        smartRenameModal.style.display = 'none';
        confirmSmartRenameBtn.disabled = true;
    });

    // 智能文件分组模态框关闭事件
    organizeFilesModalClose.addEventListener('click', () => {
        // 🚨 如果有正在进行的分组任务，直接取消任务
        if (isGroupingInProgress && currentTaskId) {
            cancelCurrentTask().then((cancelled) => {
                if (cancelled) {
                    console.log('✅ 后台任务已取消');
                    showStatus(organizeFilesStatus, '任务已取消', 'warning');
                }
            });
        }

        organizeFilesModal.style.display = 'none';
        confirmOrganizeBtn.disabled = true;
        hideGroupSortControls();
        resetGroupingState(); // 🔒 重置分组状态

        // 🖥️ 重置全屏状态
        if (organizeFilesModal.classList.contains('fullscreen')) {
            organizeFilesModal.classList.remove('fullscreen');
            if (toggleFullscreenBtn) {
                toggleFullscreenBtn.innerHTML = '<i class="fas fa-expand"></i>';
                toggleFullscreenBtn.title = '切换到全屏模式';
            }
        }
    });

    // 全屏切换功能
    if (toggleFullscreenBtn) {
        toggleFullscreenBtn.addEventListener('click', () => {
            const isFullscreen = organizeFilesModal.classList.contains('fullscreen');

            if (isFullscreen) {
                // 退出全屏
                organizeFilesModal.classList.remove('fullscreen');
                toggleFullscreenBtn.innerHTML = '<i class="fas fa-expand"></i>';
                toggleFullscreenBtn.title = '切换到全屏模式';
            } else {
                // 进入全屏
                organizeFilesModal.classList.add('fullscreen');
                toggleFullscreenBtn.innerHTML = '<i class="fas fa-compress"></i>';
                toggleFullscreenBtn.title = '退出全屏模式';
            }
        });
    }

    cancelOrganizeBtn.addEventListener('click', () => {
        // 🚨 如果有正在进行的分组任务，直接取消任务
        if (isGroupingInProgress && currentTaskId) {
            cancelCurrentTask().then((cancelled) => {
                if (cancelled) {
                    console.log('✅ 后台任务已取消');
                    showStatus(organizeFilesStatus, '任务已取消', 'warning');
                }
            });
        }

        organizeFilesModal.style.display = 'none';
        confirmOrganizeBtn.disabled = true;
        hideGroupSortControls();
        resetGroupingState(); // 🔒 重置分组状态

        // 🖥️ 重置全屏状态
        if (organizeFilesModal.classList.contains('fullscreen')) {
            organizeFilesModal.classList.remove('fullscreen');
            if (toggleFullscreenBtn) {
                toggleFullscreenBtn.innerHTML = '<i class="fas fa-expand"></i>';
                toggleFullscreenBtn.title = '切换到全屏模式';
            }
        }
    });

    // 取消任务按钮事件监听器
    cancelTaskBtn.addEventListener('click', async () => {
        const cancelled = await cancelCurrentTask();
        if (cancelled) {
            showStatus(organizeFilesStatus, '正在取消任务...', 'warning');
        }
    });

    cancelRenameTaskBtn.addEventListener('click', async () => {
        const cancelled = await cancelCurrentTask();
        if (cancelled) {
            showStatus(smartRenameStatus, '正在取消任务...', 'warning');
        }
    });

    // 取消预览刮削按钮事件监听器
    cancelScrapePreviewBtn.addEventListener('click', async () => {
        const cancelled = await cancelCurrentTask();
        if (cancelled) {
            showStatus(scrapePreviewStatus, '正在取消刮削预览...', 'warning');
            // 立即恢复按钮状态
            scrapePreviewBtn.style.display = 'inline-block';
            cancelScrapePreviewBtn.style.display = 'none';
        }
    });

    // 删除空文件夹功能
    contextMenuDeleteEmpty.addEventListener('click', async () => {
        if (!activeFolderId || activeFolderId === 'null' || activeFolderId === null || activeFolderId === undefined) {
            console.error('无效的文件夹ID:', activeFolderId);
            hideContextMenu();
            return;
        }

        const folderId = activeFolderId;
        hideContextMenu();

        // 确认对话框
        if (!confirm('确定要删除此文件夹下的所有空文件夹或不包含视频文件的文件夹吗？此操作不可撤销。')) {
            return;
        }

        try {
            showOperationResultModal('<div class="alert alert-info"><i class="fas fa-spinner fa-spin"></i> 正在扫描和删除空文件夹或无视频文件夹...</div>');

            const formData = new FormData();
            formData.append('folder_id', folderId);

            const response = await fetch('/delete_empty_folders', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                showOperationResultModal(`<div class="alert alert-success"><i class="fas fa-check-circle"></i> 删除完成: 共删除 ${data.deleted_count} 个空文件夹或无视频文件夹</div>`);
                // 刷新当前文件列表
                setTimeout(() => {
                    fetchFolderContent(currentFolderId);
                }, 1000);
            } else {
                showOperationResultModal(`<div class="alert alert-danger"><i class="fas fa-exclamation-triangle"></i> 删除失败: ${data.error}</div>`);
            }
        } catch (error) {
            showOperationResultModal(`<div class="alert alert-danger"><i class="fas fa-exclamation-triangle"></i> 请求失败: ${error.message}</div>`);
        }
    });

    // 点击模态框外部关闭
    window.addEventListener('click', (event) => {
        if (event.target === renameModal) {
            renameModal.style.display = 'none';
            confirmRenameBtn.disabled = true; // 重置按钮状态
        }
        if (event.target === createFolderModal) {
            createFolderModal.style.display = 'none';
            confirmCreateFolderBtn.disabled = true; // 重置按钮状态
        }
        if (event.target === smartRenameModal) {
            smartRenameModal.style.display = 'none';
            confirmSmartRenameBtn.disabled = true;
        }
        // 注释掉智能分组模态框的点击外部关闭功能
        // 用户反馈：不希望点击空白地方关闭窗口和取消任务
        /*
        if (event.target === organizeFilesModal) {
            // 🚨 如果有正在进行的分组任务，直接取消任务
            if (isGroupingInProgress && currentTaskId) {
                cancelCurrentTask().then((cancelled) => {
                    if (cancelled) {
                        console.log('✅ 后台任务已取消');
                        showStatus(organizeFilesStatus, '任务已取消', 'warning');
                    }
                });
            }

            organizeFilesModal.style.display = 'none';
            confirmOrganizeBtn.disabled = true;
            hideGroupSortControls();
            resetGroupingState(); // 🔒 重置分组状态

            // 🖥️ 重置全屏状态
            if (organizeFilesModal.classList.contains('fullscreen')) {
                organizeFilesModal.classList.remove('fullscreen');
                if (toggleFullscreenBtn) {
                    toggleFullscreenBtn.innerHTML = '<i class="fas fa-expand"></i>';
                    toggleFullscreenBtn.title = '切换到全屏模式';
                }
            }
        }
        */
    });

    // 悬浮窗功能实现

    // 从localStorage加载悬浮窗设置
    function loadFloatingWindowSettings() {
        const settings = localStorage.getItem('floatingLogSettings');
        if (settings) {
            try {
                return JSON.parse(settings);
            } catch (e) {
                console.warn('Failed to parse floating window settings:', e);
            }
        }
        return {
            x: 80,
            y: 80,
            width: 420,
            height: 260,
            isFloating: false,
            isMinimized: false
        };
    }

    // 保存悬浮窗设置到localStorage
    function saveFloatingWindowSettings() {
        if (!floatingLogWindow) return;
        const rect = floatingLogWindow.getBoundingClientRect();
        const settings = {
            x: rect.left,
            y: rect.top,
            width: rect.width,
            height: rect.height,
            isFloating: isFloatingMode,
            isMinimized: isMinimized
        };
        localStorage.setItem('floatingLogSettings', JSON.stringify(settings));
    }

    // 应用悬浮窗设置
    function applyFloatingWindowSettings(settings) {
        if (!floatingLogWindow) return;
        floatingLogWindow.style.left = settings.x + 'px';
        floatingLogWindow.style.top = settings.y + 'px';
        floatingLogWindow.style.width = settings.width + 'px';
        floatingLogWindow.style.height = settings.height + 'px';

        if (settings.isMinimized) {
            floatingLogWindow.classList.add('minimized');
            isMinimized = true;
            const icon = minimizeLogBtn?.querySelector('i');
            if (icon) {
                icon.className = 'fas fa-window-restore';
                minimizeLogBtn.title = '还原';
            }
        }
    }

    // 切换到悬浮窗模式
    function switchToFloatingMode() {
        isFloatingMode = true;

        // 隐藏原始日志卡片
        const logCard = document.querySelector('.card.mb-3:has(#logContainer)');
        if (logCard) {
            logCard.style.display = 'none';
        }

        // 显示悬浮窗
        if (floatingLogWindow) {
            floatingLogWindow.style.display = 'flex';
        }

        // 同步日志内容
        syncLogContent();

        // 应用保存的设置
        const settings = loadFloatingWindowSettings();
        applyFloatingWindowSettings(settings);

        // 更新按钮状态
        if (floatLogBtn) {
            floatLogBtn.innerHTML = '<i class="fas fa-compress-arrows-alt"></i> 还原';
            floatLogBtn.title = '还原到卡片';
        }

        saveFloatingWindowSettings();
    }

    // 切换到卡片模式
    function switchToCardMode() {
        isFloatingMode = false;
        isMinimized = false;

        // 显示原始日志卡片
        const logCard = document.querySelector('.card.mb-3:has(#logContainer)');
        if (logCard) {
            logCard.style.display = 'block';
        }

        // 隐藏悬浮窗
        if (floatingLogWindow) {
            floatingLogWindow.style.display = 'none';
            floatingLogWindow.classList.remove('minimized');
        }

        // 同步日志内容
        syncLogContent();

        // 更新按钮状态
        if (floatLogBtn) {
            floatLogBtn.innerHTML = '<i class="fas fa-external-link-alt"></i> 悬浮窗';
            floatLogBtn.title = '悬浮窗模式';
        }

        // 重置最小化按钮
        const icon = minimizeLogBtn?.querySelector('i');
        if (icon) {
            icon.className = 'fas fa-minus';
            minimizeLogBtn.title = '最小化';
        }

        saveFloatingWindowSettings();
    }

    // 同步日志内容
    function syncLogContent() {
        if (isFloatingMode && floatingLogDisplay && logDisplay) {
            floatingLogDisplay.textContent = logDisplay.textContent;
        } else if (!isFloatingMode && logDisplay && floatingLogDisplay) {
            logDisplay.textContent = floatingLogDisplay.textContent;
        }
    }

    // 日志控制功能
    if (clearLogBtn) {
        clearLogBtn.addEventListener('click', () => {
            if (logDisplay) logDisplay.textContent = '';
            if (floatingLogDisplay) floatingLogDisplay.textContent = '';
        });
    }

    if (pauseLogBtn) {
        pauseLogBtn.addEventListener('click', () => {
            logPaused = !logPaused;
            const icon = pauseLogBtn.querySelector('i');
            if (logPaused) {
                icon.className = 'fas fa-play';
                pauseLogBtn.title = '恢复日志';
            } else {
                icon.className = 'fas fa-pause';
                pauseLogBtn.title = '暂停日志';
            }

            // 同步悬浮窗按钮状态
            if (floatingPauseLogBtn) {
                const floatingIcon = floatingPauseLogBtn.querySelector('i');
                floatingIcon.className = icon.className;
                floatingPauseLogBtn.title = pauseLogBtn.title;
            }
        });
    }

    if (downloadLogBtn) {
        downloadLogBtn.addEventListener('click', () => {
            const logContent = isFloatingMode ?
                (floatingLogDisplay?.textContent || '') :
                (logDisplay?.textContent || '');
            const blob = new Blob([logContent], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `pan23_log_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        });
    }

    // 悬浮窗按钮事件
    if (floatLogBtn) {
        floatLogBtn.addEventListener('click', () => {
            if (isFloatingMode) {
                switchToCardMode();
            } else {
                switchToFloatingMode();
            }
        });
    }

    // 悬浮窗控制按钮事件
    if (dockLogBtn) {
        dockLogBtn.addEventListener('click', () => {
            switchToCardMode();
        });
    }

    if (minimizeLogBtn) {
        minimizeLogBtn.addEventListener('click', () => {
            isMinimized = !isMinimized;
            if (isMinimized) {
                floatingLogWindow.classList.add('minimized');
                const icon = minimizeLogBtn.querySelector('i');
                icon.className = 'fas fa-window-restore';
                minimizeLogBtn.title = '还原';
            } else {
                floatingLogWindow.classList.remove('minimized');
                const icon = minimizeLogBtn.querySelector('i');
                icon.className = 'fas fa-minus';
                minimizeLogBtn.title = '最小化';
            }
            saveFloatingWindowSettings();
        });
    }

    if (closeFloatingLogBtn) {
        closeFloatingLogBtn.addEventListener('click', () => {
            switchToCardMode();
        });
    }

    // 悬浮窗日志控制按钮事件
    if (floatingClearLogBtn) {
        floatingClearLogBtn.addEventListener('click', () => {
            if (logDisplay) logDisplay.textContent = '';
            if (floatingLogDisplay) floatingLogDisplay.textContent = '';
        });
    }

    if (floatingPauseLogBtn) {
        floatingPauseLogBtn.addEventListener('click', () => {
            logPaused = !logPaused;
            const icon = floatingPauseLogBtn.querySelector('i');
            if (logPaused) {
                icon.className = 'fas fa-play';
                floatingPauseLogBtn.title = '恢复日志';
            } else {
                icon.className = 'fas fa-pause';
                floatingPauseLogBtn.title = '暂停日志';
            }

            // 同步主面板按钮状态
            if (pauseLogBtn) {
                const mainIcon = pauseLogBtn.querySelector('i');
                mainIcon.className = icon.className;
                pauseLogBtn.title = floatingPauseLogBtn.title;
            }
        });
    }

    if (floatingDownloadLogBtn) {
        floatingDownloadLogBtn.addEventListener('click', () => {
            const logContent = floatingLogDisplay?.textContent || '';
            const blob = new Blob([logContent], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `pan23_log_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        });
    }

    // 悬浮窗拖拽功能
    if (floatingLogWindow) {
        const header = floatingLogWindow.querySelector('.floating-log-header');
        const resizeHandle = floatingLogWindow.querySelector('.floating-log-resize-handle');

        // 拖拽功能
        if (header) {
            header.addEventListener('mousedown', (e) => {
                if (e.target.tagName === 'BUTTON' || e.target.tagName === 'I') return;

                isDragging = true;
                dragStartX = e.clientX;
                dragStartY = e.clientY;
                const rect = floatingLogWindow.getBoundingClientRect();
                windowStartX = rect.left;
                windowStartY = rect.top;

                document.addEventListener('mousemove', handleDrag);
                document.addEventListener('mouseup', stopDrag);
                e.preventDefault();
            });
        }

        // 调整大小功能
        if (resizeHandle) {
            resizeHandle.addEventListener('mousedown', (e) => {
                isResizing = true;
                resizeStartX = e.clientX;
                resizeStartY = e.clientY;
                const rect = floatingLogWindow.getBoundingClientRect();
                windowStartWidth = rect.width;
                windowStartHeight = rect.height;

                document.addEventListener('mousemove', handleResize);
                document.addEventListener('mouseup', stopResize);
                e.preventDefault();
            });
        }

        function handleDrag(e) {
            if (!isDragging) return;

            const deltaX = e.clientX - dragStartX;
            const deltaY = e.clientY - dragStartY;

            const newX = Math.max(0, Math.min(window.innerWidth - 280, windowStartX + deltaX));
            const newY = Math.max(0, Math.min(window.innerHeight - 60, windowStartY + deltaY));

            floatingLogWindow.style.left = newX + 'px';
            floatingLogWindow.style.top = newY + 'px';
        }

        function stopDrag() {
            isDragging = false;
            document.removeEventListener('mousemove', handleDrag);
            document.removeEventListener('mouseup', stopDrag);
            saveFloatingWindowSettings();
        }

        function handleResize(e) {
            if (!isResizing) return;

            const deltaX = e.clientX - resizeStartX;
            const deltaY = e.clientY - resizeStartY;

            const newWidth = Math.max(280, Math.min(window.innerWidth - 40, windowStartWidth + deltaX));
            const newHeight = Math.max(140, Math.min(window.innerHeight - 40, windowStartHeight + deltaY));

            floatingLogWindow.style.width = newWidth + 'px';
            floatingLogWindow.style.height = newHeight + 'px';
        }

        function stopResize() {
            isResizing = false;
            document.removeEventListener('mousemove', handleResize);
            document.removeEventListener('mouseup', stopResize);
            saveFloatingWindowSettings();
        }
    }



    // 页面加载时恢复悬浮窗状态
    const settings = loadFloatingWindowSettings();
    if (settings.isFloating) {
        setTimeout(() => {
            switchToFloatingMode();
        }, 100);
    }

    // 初始化可调整宽度的分割条
    initializeResizeHandle();
});

// 初始化可调整宽度的分割条
function initializeResizeHandle() {
    const resizeHandle = document.getElementById('resizeHandle');
    const leftColumn = document.querySelector('.left-column');
    const rightColumn = document.querySelector('.right-column');
    const mainContent = document.querySelector('.main-content');

    if (!resizeHandle || !leftColumn || !rightColumn || !mainContent) {
        return;
    }

    let isResizing = false;
    let startX = 0;
    let startLeftWidth = 0;

    // 鼠标按下开始拖拽
    resizeHandle.addEventListener('mousedown', function(e) {
        isResizing = true;
        startX = e.clientX;
        startLeftWidth = leftColumn.offsetWidth;

        // 添加全局样式防止选择文本
        document.body.style.userSelect = 'none';
        document.body.style.cursor = 'col-resize';

        // 阻止默认行为
        e.preventDefault();
    });

    // 鼠标移动时调整宽度
    document.addEventListener('mousemove', function(e) {
        if (!isResizing) return;

        const deltaX = e.clientX - startX;
        const mainContentWidth = mainContent.offsetWidth;
        const newLeftWidth = startLeftWidth + deltaX;

        // 计算百分比
        const leftPercentage = (newLeftWidth / mainContentWidth) * 100;

        // 限制最小和最大宽度
        if (leftPercentage >= 20 && leftPercentage <= 80) {
            leftColumn.style.width = leftPercentage + '%';

            // 保存用户偏好到localStorage
            localStorage.setItem('leftColumnWidth', leftPercentage);
        }
    });

    // 鼠标释放结束拖拽
    document.addEventListener('mouseup', function() {
        if (isResizing) {
            isResizing = false;

            // 恢复样式
            document.body.style.userSelect = '';
            document.body.style.cursor = '';
        }
    });

    // 加载用户偏好的宽度
    const savedWidth = localStorage.getItem('leftColumnWidth');
    if (savedWidth) {
        leftColumn.style.width = savedWidth + '%';
    }

    // 初始化动态高度调整
    initDynamicHeight();
}

// 动态调整fileListContainer高度
function adjustFileListContainerHeight() {
    const fileListContainer = document.getElementById('fileListContainer');
    if (!fileListContainer) return;

    // 获取视口高度
    const viewportHeight = window.innerHeight;

    // 获取底部日志区域的实际高度
    const bottomSection = document.querySelector('.bottom-section');
    const bottomSectionHeight = bottomSection ? bottomSection.offsetHeight : 180;

    // 获取容器相对于视口的位置
    const containerRect = fileListContainer.getBoundingClientRect();
    const containerTop = containerRect.top;

    // 计算安全的底部边距（日志区域高度 + 额外边距）
    const safeBottomMargin = bottomSectionHeight + 20; // 20px额外边距

    // 计算可用高度，确保不超过视口
    const availableHeight = Math.max(0, viewportHeight - containerTop - safeBottomMargin);

    // 设置最小高度限制
    let minHeight;
    if (window.innerWidth <= 375) {
        minHeight = 120; // 小屏设备
    } else if (window.innerWidth <= 768) {
        minHeight = 150; // 移动设备
    } else if (window.innerWidth <= 1024) {
        minHeight = 180; // 平板设备
    } else {
        minHeight = 200; // 桌面设备
    }

    // 根据设备类型设置最大高度比例
    let maxHeightRatio;
    if (window.innerWidth <= 375) {
        maxHeightRatio = 0.75; // 小屏设备最大75%
    } else if (window.innerWidth <= 768) {
        maxHeightRatio = 0.70; // 移动设备最大70%
    } else if (window.innerWidth <= 1024) {
        maxHeightRatio = 0.65; // 平板设备最大65%
    } else {
        maxHeightRatio = 0.60; // 桌面设备最大60%
    }

    // 计算最终高度，确保在合理范围内
    const maxAllowedHeight = viewportHeight * maxHeightRatio;
    const finalHeight = Math.max(minHeight, Math.min(availableHeight, maxAllowedHeight));

    // 确保高度不会导致页面溢出
    const safeHeight = Math.min(finalHeight, viewportHeight - containerTop - bottomSectionHeight - 40); // 40px额外安全边距

    // 应用高度
    fileListContainer.style.height = `${safeHeight}px`;
    fileListContainer.style.maxHeight = `${safeHeight}px`;

    console.log(`📐 动态调整fileListContainer高度: ${safeHeight}px (视口: ${viewportHeight}px, 容器顶部: ${containerTop}px, 底部区域: ${bottomSectionHeight}px, 可用: ${availableHeight}px, 最大允许: ${maxAllowedHeight}px)`);
}

// 页面加载完成后调整高度
function initDynamicHeight() {
    // 初始调整
    setTimeout(adjustFileListContainerHeight, 100);

    // 监听窗口大小变化
    window.addEventListener('resize', () => {
        setTimeout(adjustFileListContainerHeight, 100);
    });

    // 监听页面可见性变化（如从其他标签页切换回来）
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            setTimeout(adjustFileListContainerHeight, 200);
        }
    });

    // 监听方向变化（移动设备）
    window.addEventListener('orientationchange', () => {
        setTimeout(adjustFileListContainerHeight, 300);
    });

    // 监听DOM变化（如工具栏展开/收起）
    const observer = new MutationObserver(() => {
        setTimeout(adjustFileListContainerHeight, 100);
    });

    // 观察主要容器的变化
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        observer.observe(mainContent, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['style', 'class']
        });
    }

    // 观察容器自身的变化
    const fileListContainer = document.getElementById('fileListContainer');
    if (fileListContainer) {
        observer.observe(fileListContainer.parentElement, {
            childList: true,
            attributes: true,
            attributeFilter: ['style', 'class']
        });
    }
}

// AI测试函数
async function testAIConnection() {
    const testButton = document.querySelector('button[onclick="testAIConnection()"]');
    const resultDiv = document.getElementById('aiTestResult');

    if (!testButton || !resultDiv) return;

    // 显示加载状态
    testButton.disabled = true;
    testButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 测试中...';
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<div class="alert alert-info"><i class="fas fa-spinner fa-spin"></i> 正在测试AI连接...</div>';

    try {
        const response = await fetch('/test_ai_api', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        const result = await response.json();

        if (result.success) {
            resultDiv.innerHTML = `
                <div class="alert alert-success">
                    <h6><i class="fas fa-check-circle"></i> AI连接测试成功</h6>
                    <p><strong>API地址:</strong> ${result.details.api_url}</p>
                    <p><strong>模型:</strong> ${result.details.model}</p>
                    <p><strong>基础响应:</strong> ${result.details.basic_response}</p>
                    <details>
                        <summary>分组测试响应</summary>
                        <pre style="font-size: 12px; max-height: 200px; overflow-y: auto;">${result.details.grouping_response}</pre>
                    </details>
                </div>
            `;
        } else {
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <h6><i class="fas fa-exclamation-triangle"></i> AI连接测试失败</h6>
                    <p><strong>错误:</strong> ${result.error}</p>
                    <p><strong>API地址:</strong> ${result.details.api_url}</p>
                    <p><strong>模型:</strong> ${result.details.model}</p>
                    <p><strong>API密钥状态:</strong> ${result.details.api_key_status}</p>
                    <div class="mt-2">
                        <strong>可能的解决方案:</strong>
                        <ul>
                            <li>检查AI_API_KEY是否正确配置</li>
                            <li>检查AI_API_URL是否可访问</li>
                            <li>检查GROUPING_MODEL模型名称是否正确</li>
                            <li>检查网络连接是否正常</li>
                        </ul>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="alert alert-danger">
                <h6><i class="fas fa-exclamation-triangle"></i> 测试请求失败</h6>
                <p><strong>错误:</strong> ${error.message}</p>
                <p>请检查网络连接和服务器状态</p>
            </div>
        `;
    } finally {
        // 恢复按钮状态
        testButton.disabled = false;
        testButton.innerHTML = '<i class="fas fa-stethoscope"></i> 测试AI';
    }
}

// 🎯 智能分组事件监听器设置函数
function setupGroupingEventListeners() {
    // 全选按钮
    const selectAllBtn = document.getElementById('selectAllGroups');
    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', () => {
            const checkboxes = document.querySelectorAll('.group-checkbox');
            checkboxes.forEach(checkbox => {
                checkbox.checked = true;
            });
            updateSelectionInfo();
            updateGroupItemStyles();
        });
    }

    // 取消全选按钮
    const deselectAllBtn = document.getElementById('deselectAllGroups');
    if (deselectAllBtn) {
        deselectAllBtn.addEventListener('click', () => {
            const checkboxes = document.querySelectorAll('.group-checkbox');
            checkboxes.forEach(checkbox => {
                checkbox.checked = false;
            });
            updateSelectionInfo();
            updateGroupItemStyles();
        });
    }

    // 预览按钮已删除

    // 分组复选框变化监听
    const checkboxes = document.querySelectorAll('.group-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', () => {
            updateSelectionInfo();
            updateGroupItemStyles();
        });
    });

    // 分组卡片点击监听（除了复选框区域）
    const groupItems = document.querySelectorAll('.group-item');
    groupItems.forEach(item => {
        item.addEventListener('click', (e) => {
            // 如果点击的不是复选框，则切换选择状态
            if (!e.target.classList.contains('group-checkbox')) {
                const checkbox = item.querySelector('.group-checkbox');
                if (checkbox) {
                    checkbox.checked = !checkbox.checked;
                    updateSelectionInfo();
                    updateGroupItemStyles();
                }
            }
        });
    });

    // 初始化状态
    updateSelectionInfo();
    updateGroupItemStyles();
}

// 更新选择信息显示
function updateSelectionInfo() {
    const selectionCountElement = document.getElementById('selectionCount');
    if (selectionCountElement) {
        const checkedBoxes = document.querySelectorAll('.group-checkbox:checked');
        const totalBoxes = document.querySelectorAll('.group-checkbox');
        selectionCountElement.textContent = `已选择 ${checkedBoxes.length} / ${totalBoxes.length} 个分组`;
    }
}

// 更新分组卡片样式
function updateGroupItemStyles() {
    const groupItems = document.querySelectorAll('.group-item');
    groupItems.forEach(item => {
        const checkbox = item.querySelector('.group-checkbox');
        if (checkbox && checkbox.checked) {
            item.classList.add('selected');
        } else {
            item.classList.remove('selected');
        }
    });
}

// 智能分组预览功能已删除

// 🔄 智能分组排序功能
function setupGroupSortingEventListeners() {
    const groupSortSelect = document.getElementById('groupSortSelect');
    if (groupSortSelect) {
        groupSortSelect.addEventListener('change', () => {
            sortGroups(groupSortSelect.value);
        });
    }
}

// 排序分组
function sortGroups(sortType) {
    const suggestedGroups = document.getElementById('suggestedGroups');
    if (!suggestedGroups || !window.currentGroupsData) {
        return;
    }

    // 获取当前选中状态
    const selectedGroups = new Set();
    const checkboxes = document.querySelectorAll('.group-checkbox:checked');
    checkboxes.forEach(checkbox => {
        selectedGroups.add(parseInt(checkbox.value));
    });

    // 创建排序后的数据副本
    let sortedData = [...window.currentGroupsData];

    switch (sortType) {
        case 'name-asc':
            sortedData.sort((a, b) => {
                const nameA = (a.group_name || a.title || '').toLowerCase();
                const nameB = (b.group_name || b.title || '').toLowerCase();
                return nameA.localeCompare(nameB, 'zh-CN');
            });
            break;
        case 'name-desc':
            sortedData.sort((a, b) => {
                const nameA = (a.group_name || a.title || '').toLowerCase();
                const nameB = (b.group_name || b.title || '').toLowerCase();
                return nameB.localeCompare(nameA, 'zh-CN');
            });
            break;
        case 'count-desc':
            sortedData.sort((a, b) => {
                const countA = (a.file_names && a.file_names.length) || a.file_count || 0;
                const countB = (b.file_names && b.file_names.length) || b.file_count || 0;
                return countB - countA;
            });
            break;
        case 'count-asc':
            sortedData.sort((a, b) => {
                const countA = (a.file_names && a.file_names.length) || a.file_count || 0;
                const countB = (b.file_names && b.file_names.length) || b.file_count || 0;
                return countA - countB;
            });
            break;
        default:
            // 默认顺序，不排序
            break;
    }

    // 重新生成HTML
    renderSortedGroups(sortedData, selectedGroups);
}

// 渲染排序后的分组
function renderSortedGroups(sortedData, selectedGroups) {
    const suggestedGroups = document.getElementById('suggestedGroups');
    let groupsHtml = '';

    sortedData.forEach((group, index) => {
        const groupName = group.group_name || group.title || `分组 ${index + 1}`;
        const fileNames = group.file_names || [];
        const fileCount = group.file_count || fileNames.length || 0;
        const fileIds = group.fileIds || group.file_ids || [];

        // 计算实际文件数量
        let actualFileCount = 0;
        if (window.videoFileIds && fileIds.length > 0) {
            actualFileCount = fileIds.filter(id => window.videoFileIds.includes(id)).length;
        }

        // 如果没有匹配到文件，使用文件名数量作为备选
        if (actualFileCount === 0 && fileNames.length > 0) {
            actualFileCount = fileNames.length;
        }

        const safeFileCount = fileCount || fileNames.length || 0;
        const displayCount = actualFileCount > 0 ? `${actualFileCount} 个文件` : `${safeFileCount} 个文件`;
        console.log(`🔢 分组文件数量: actualFileCount=${actualFileCount}, fileCount=${fileCount}, fileNames.length=${fileNames.length}, displayCount="${displayCount}"`);

        // 生成文件列表HTML
        let fileListHtml = '';
        if (fileNames && fileNames.length > 0) {
            // 使用智能排序（按集数或字母顺序）
            const sortedFileNames = smartSortFiles(fileNames, groupName);

            fileListHtml = '<div class="group-files">';
            sortedFileNames.forEach(fileName => {
                fileListHtml += `
                    <div class="file-item">
                        <i class="fas fa-play-circle file-icon"></i>
                        <span class="file-name" title="${fileName}">${fileName}</span>
                    </div>
                `;
            });
            fileListHtml += '</div>';
        }

        // 检查是否应该选中
        const isChecked = selectedGroups.has(index);

        // 生成分组卡片
        groupsHtml += `
            <div class="group-item" data-group-index="${index}">
                <div class="group-header">
                    <input class="group-checkbox" type="checkbox" value="${index}" id="group_${index}" ${isChecked ? 'checked' : ''}>
                    <div class="group-title">${groupName}</div>
                    <div class="group-count">${displayCount}</div>
                </div>
                ${fileListHtml}
            </div>
        `;
    });

    suggestedGroups.innerHTML = groupsHtml;

    // 更新全局数据以反映新的排序
    window.currentGroupsData = sortedData;

    // 重新设置事件监听器
    setupGroupingEventListeners();
}

// 隐藏分组排序控件
function hideGroupSortControls() {
    const groupSortControls = document.querySelector('.group-sort-controls');
    if (groupSortControls) {
        groupSortControls.style.display = 'none';
    }

    // 重置排序选择为默认的"名称A-Z"
    const groupSortSelect = document.getElementById('groupSortSelect');
    if (groupSortSelect) {
        groupSortSelect.value = 'name-asc';
    }
}

// 🎬 按集数排序文件名（专用于电视剧文件）
function sortFilesByEpisode(fileNames) {
    return [...fileNames].sort((a, b) => {
        // 提取集数信息的正则表达式
        const episodeRegex = /S(\d+)E(\d+)/i;

        const matchA = a.match(episodeRegex);
        const matchB = b.match(episodeRegex);

        // 如果两个文件都有集数信息
        if (matchA && matchB) {
            const seasonA = parseInt(matchA[1]);
            const seasonB = parseInt(matchB[1]);
            const episodeA = parseInt(matchA[2]);
            const episodeB = parseInt(matchB[2]);

            // 先按季数排序，再按集数排序
            if (seasonA !== seasonB) {
                return seasonA - seasonB;
            }
            return episodeA - episodeB;
        }

        // 如果只有一个有集数信息，有集数的排在前面
        if (matchA && !matchB) return -1;
        if (!matchA && matchB) return 1;

        // 如果都没有集数信息，按字母顺序排序
        return a.localeCompare(b, 'zh-CN');
    });
}

// 🎬 按电影系列数字排序文件名（专用于电影系列）
function sortFilesByMovieSequence(fileNames) {
    return [...fileNames].sort((a, b) => {
        // 提取电影系列数字的正则表达式
        // 匹配模式：电锯惊魂2、电锯惊魂10、蜡笔小新：新次元！超能力大决战等
        const movieSequenceRegex = /^(.+?)(\d+)(?:\D|$)/;

        const matchA = a.match(movieSequenceRegex);
        const matchB = b.match(movieSequenceRegex);

        // 如果两个文件都有序列号
        if (matchA && matchB) {
            const baseNameA = matchA[1].trim();
            const baseNameB = matchB[1].trim();
            const sequenceA = parseInt(matchA[2]);
            const sequenceB = parseInt(matchB[2]);

            // 先按基础名称排序
            const baseComparison = baseNameA.localeCompare(baseNameB, 'zh-CN');
            if (baseComparison !== 0) {
                return baseComparison;
            }

            // 基础名称相同时，按序列号数字排序
            return sequenceA - sequenceB;
        }

        // 如果只有一个有序列号，有序列号的排在后面
        if (matchA && !matchB) return 1;
        if (!matchA && matchB) return -1;

        // 如果都没有序列号，按字母顺序排序
        return a.localeCompare(b, 'zh-CN');
    });
}

// 🎯 智能文件排序（根据分组类型选择排序方式）
function smartSortFiles(fileNames, groupName) {
    // 检查是否为电视剧分组（包含季数信息）
    const isTVSeries = /S\d+/i.test(groupName) || fileNames.some(name => /S\d+E\d+/i.test(name));

    if (isTVSeries) {
        // 电视剧文件按集数排序
        return sortFilesByEpisode(fileNames);
    } else {
        // 检查是否为电影系列（包含数字序列）
        const hasMovieSequence = fileNames.some(name => /^(.+?)(\d+)(?:\D|$)/.test(name));

        if (hasMovieSequence) {
            // 电影系列按数字序列排序
            return sortFilesByMovieSequence(fileNames);
        } else {
            // 其他文件按字母顺序排序
            return [...fileNames].sort((a, b) => a.localeCompare(b, 'zh-CN'));
        }
    }
}

// 🔒 重置分组状态函数
function resetGroupingState() {
    const previousState = {
        isGroupingInProgress: isGroupingInProgress,
        currentGroupingFolderId: currentGroupingFolderId
    };

    isGroupingInProgress = false;
    currentGroupingFolderId = null;

    // 🛑 停止任务状态轮询
    stopTaskStatusPolling();

    // 🎨 移除任务进行中的视觉提示
    const organizeFilesModal = document.getElementById('organizeFilesModal');
    if (organizeFilesModal) {
        organizeFilesModal.classList.remove('task-in-progress');
    }

    // 清除 activeFolderId（需要在 DOMContentLoaded 内部访问）
    // 这里我们不直接清除，让下次右键点击时重新设置

    // 恢复右键菜单项状态
    if (contextMenuOrganizeFiles) {
        contextMenuOrganizeFiles.style.pointerEvents = 'auto';
        contextMenuOrganizeFiles.style.opacity = '1';
        contextMenuOrganizeFiles.innerHTML = '智能文件分组';
    }

    console.log('🔓 分组状态已重置 - 之前状态:', previousState, '当前状态:', {
        isGroupingInProgress: isGroupingInProgress,
        currentGroupingFolderId: currentGroupingFolderId
    });
}

// 🚦 限流倒计时功能
function startRateLimitCountdown(remainingSeconds) {
    let seconds = remainingSeconds;

    // 禁用智能分组菜单项
    if (contextMenuOrganizeFiles) {
        contextMenuOrganizeFiles.style.pointerEvents = 'none';
        contextMenuOrganizeFiles.style.opacity = '0.6';
    }

    const updateCountdown = () => {
        if (seconds <= 0) {
            // 倒计时结束，恢复菜单项
            if (contextMenuOrganizeFiles) {
                contextMenuOrganizeFiles.style.pointerEvents = 'auto';
                contextMenuOrganizeFiles.style.opacity = '1';
                contextMenuOrganizeFiles.innerHTML = '智能文件分组';
            }

            showStatus(operationResultsDiv, '✅ 限流时间已结束，可以重新进行智能分组', 'success');
            return;
        }

        // 更新菜单项显示
        if (contextMenuOrganizeFiles) {
            contextMenuOrganizeFiles.innerHTML = `🚦 请等待 ${seconds}秒`;
        }

        seconds--;
        setTimeout(updateCountdown, 1000);
    };

    updateCountdown();
}

// ================================
// 任务队列管理和状态轮询
// ================================

let currentTaskId = null;
let taskPollingInterval = null;

function startTaskStatusPolling(taskId) {
    // 开始轮询任务状态
    currentTaskId = taskId;

    // 清除之前的轮询
    if (taskPollingInterval) {
        clearInterval(taskPollingInterval);
    }

    // 立即检查一次状态
    checkTaskStatus(taskId);

    // 每2秒轮询一次
    taskPollingInterval = setInterval(() => {
        checkTaskStatus(taskId);
    }, 2000);

    console.log(`🔄 开始轮询任务状态: ${taskId}`);
}

async function checkTaskStatus(taskId) {
    // 检查任务状态
    try {
        const response = await fetch(`/api/grouping_task/status/${taskId}`);
        const data = await response.json();

        if (data.success && data.task) {
            console.log(`📊 前端收到任务状态: ${data.task.status}, 进度: ${data.task.progress}%`);
            updateTaskUI(data.task);

            // 如果任务完成，停止轮询
            if (['completed', 'failed', 'cancelled', 'timeout'].includes(data.task.status)) {
                console.log(`🎯 检测到任务完成状态: ${data.task.status}, 准备停止轮询`);
                stopTaskStatusPolling();
                handleTaskCompletion(data.task);
            }
        } else {
            console.error('获取任务状态失败:', data.error);
            showStatus(organizeFilesStatus, `❌ 获取任务状态失败: ${data.error}`, 'error');
            stopTaskStatusPolling();
            resetGroupingState();
        }
    } catch (error) {
        console.error('轮询任务状态时发生错误:', error);
        showStatus(organizeFilesStatus, `❌ 网络错误: ${error.message}`, 'error');
        stopTaskStatusPolling();
        resetGroupingState();
    }
}

function updateTaskUI(task) {
    // 更新任务相关的UI
    const organizeFolderInfo = document.getElementById('organizeFolderInfo');

    // 更新状态显示
    let statusMessage = '';
    let statusClass = 'info';

    switch (task.status) {
        case 'pending':
            statusMessage = `⏳ 任务排队中... (进度: ${task.progress.toFixed(1)}%)`;
            statusClass = 'info';
            break;
        case 'running':
            statusMessage = `🔄 正在分析文件夹... (进度: ${task.progress.toFixed(1)}%)`;
            statusClass = 'info';
            break;
        case 'completed':
            statusMessage = `✅ 分析完成！`;
            statusClass = 'success';
            break;
        case 'failed':
            statusMessage = `❌ 分析失败: ${task.error}`;
            statusClass = 'error';
            break;
        case 'cancelled':
            statusMessage = `🛑 任务已取消`;
            statusClass = 'warning';
            break;
        case 'timeout':
            statusMessage = `⏰ 任务超时`;
            statusClass = 'error';
            break;
    }

    showStatus(organizeFilesStatus, statusMessage, statusClass);

    // 更新文件夹信息
    if (task.status === 'running' || task.status === 'pending') {
        organizeFolderInfo.textContent = `正在分析文件夹 "${task.folder_name}"...`;
    }

    // 更新进度条（如果有的话）
    updateProgressBar(task.progress);
}

function updateProgressBar(progress) {
    // 更新进度条
    // 这里可以添加进度条的更新逻辑
    // 暂时使用控制台输出
    console.log(`📊 任务进度: ${progress.toFixed(1)}%`);
}

function stopTaskStatusPolling() {
    // 停止任务状态轮询
    if (taskPollingInterval) {
        clearInterval(taskPollingInterval);
        taskPollingInterval = null;
    }
    currentTaskId = null;
    console.log('🛑 停止任务状态轮询');
}

function handleTaskCompletion(task) {
    // 处理任务完成
    console.log('🎯 处理任务完成:', task);

    const suggestedGroups = document.getElementById('suggestedGroups');
    const confirmOrganizeBtn = document.getElementById('confirmOrganizeBtn');
    const organizeFolderInfo = document.getElementById('organizeFolderInfo');

    // 调试信息
    console.log('🔍 DOM元素检查:', {
        suggestedGroups: !!suggestedGroups,
        confirmOrganizeBtn: !!confirmOrganizeBtn,
        organizeFilesStatus: !!organizeFilesStatus,
        organizeFolderInfo: !!organizeFolderInfo
    });

    if (task.status === 'completed' && task.result && task.result.success) {
        const result = task.result;

        console.log('✅ 任务成功完成，结果:', result);

        // 更新文件夹信息
        if (organizeFolderInfo) {
            organizeFolderInfo.textContent = `包含 ${result.count} 个视频文件，总大小 ${result.size}`;
        }

        if (result.movie_info && result.movie_info.length > 0) {
            console.log(`📊 显示 ${result.movie_info.length} 个分组结果`);

            // 显示分组结果（复用现有的显示逻辑）
            displayGroupingResults(result);

            if (confirmOrganizeBtn) {
                confirmOrganizeBtn.disabled = false;
            }

            showStatus(organizeFilesStatus, `✅ 成功生成 ${result.movie_info.length} 个智能分组`, 'success');
        } else {
            console.log('⚠️ 没有分组结果');

            // 显示空状态
            if (suggestedGroups) {
                suggestedGroups.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">
                            <i class="fas fa-folder-open"></i>
                        </div>
                        <div class="empty-state-text">
                            <h4>未找到可分组的文件</h4>
                            <p>该文件夹中的文件无法进行智能分组</p>
                        </div>
                    </div>
                `;
            }
            showStatus(organizeFilesStatus, '⚠️ 无法生成有效的文件分组建议', 'warning');
        }
    } else {
        console.log('❌ 任务失败或被取消:', task.status, task.error);

        // 任务失败或被取消
        if (suggestedGroups) {
            suggestedGroups.innerHTML = '<div class="text-center text-muted">分组分析失败</div>';
        }
        showStatus(organizeFilesStatus, task.error || '分组分析失败', 'error');
    }

    // 重置分组状态
    resetGroupingState();
}

function displayGroupingResults(result) {
    // 显示分组结果的函数
    console.log('🎨 开始显示分组结果:', result);

    const suggestedGroups = document.getElementById('suggestedGroups');

    if (!suggestedGroups) {
        console.error('❌ 找不到 suggestedGroups 元素');
        return;
    }

    // 计算统计信息
    const totalGroups = result.movie_info.length;
    const totalFiles = result.count;
    let groupedFiles = 0;

    result.movie_info.forEach(group => {
        const fileIds = group.fileIds || group.files || [];
        groupedFiles += fileIds.length;
    });

    const ungroupedFiles = totalFiles - groupedFiles;

    // 显示统计信息面板
    let groupsHtml = `
        <div class="grouping-stats">
            <div class="stat-item">
                <span class="stat-label">建议分组:</span>
                <span class="stat-value">${totalGroups} 个</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">可分组文件:</span>
                <span class="stat-value">${groupedFiles} 个</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">未分组文件:</span>
                <span class="stat-value">${ungroupedFiles} 个</span>
            </div>
        </div>
    `;

    // 显示分组列表
    result.movie_info.forEach((group, index) => {
        const groupName = group.group_name || `分组 ${index + 1}`;
        // 兼容不同的字段名称
        const fileIds = group.fileIds || group.files || [];
        const fileNames = group.file_names || [];
        const fileCount = fileIds.length;

        // 调试日志
        console.log(`分组 ${index}: ${groupName}, fileIds: ${fileIds.length}, fileNames: ${fileNames.length}`, fileNames);

        // 根据实际的video_files数据计算匹配的文件数量
        let actualFileCount = 0;
        if (result.video_files && fileIds.length > 0) {
            // 通过文件名匹配来计算实际的文件数量
            const videoFileIds = result.video_files.map(f => f.fileId);
            actualFileCount = fileIds.filter(id => videoFileIds.includes(id)).length;
        }

        const safeFileCount = fileCount || 0;
        const displayCount = actualFileCount > 0 ? `${actualFileCount} 个文件` : `${safeFileCount} 个文件`;
        console.log(`🔢 分组文件数量: actualFileCount=${actualFileCount}, fileCount=${fileCount}, displayCount="${displayCount}"`);

        // 生成文件列表HTML
        let fileListHtml = '';
        if (fileNames.length > 0) {
            fileListHtml = `
                <div class="group-files">
                    ${fileNames.map(fileName => `<div class="file-item">${fileName}</div>`).join('')}
                </div>
            `;
        }

        // 现代化分组卡片
        groupsHtml += `
            <div class="group-item" data-group-index="${index}">
                <div class="group-header">
                    <input class="group-checkbox" type="checkbox" value="${index}" id="group_${index}" checked>
                    <div class="group-title">${groupName}</div>
                    <div class="group-count">${displayCount}</div>
                </div>
                ${fileListHtml}
            </div>
        `;
    });

    suggestedGroups.innerHTML = groupsHtml;

    console.log('✅ HTML已设置到suggestedGroups，内容长度:', groupsHtml.length);
    console.log('📊 suggestedGroups当前内容:', suggestedGroups.innerHTML.substring(0, 200) + '...');

    // 存储分组数据供后续使用
    window.currentGroupsData = result.movie_info;

    // 显示排序控件
    const groupSortControls = document.querySelector('.group-sort-controls');
    if (groupSortControls) {
        groupSortControls.style.display = 'flex';
        console.log('🔧 排序控件已显示');
    } else {
        console.warn('⚠️ 找不到排序控件元素');
    }

    // 添加事件监听器
    try {
        setupGroupingEventListeners();
        setupGroupSortingEventListeners();
        console.log('🎧 事件监听器已设置');

        // 🎯 自动应用默认排序（名称A-Z）
        const groupSortSelect = document.getElementById('groupSortSelect');
        if (groupSortSelect) {
            groupSortSelect.value = 'name-asc';
            sortGroups('name-asc');
            console.log('🔤 已应用默认排序：名称A-Z');
        }
    } catch (error) {
        console.error('❌ 设置事件监听器失败:', error);
    }
}
