/**
 * 深蹲闯关游戏 - 前端主应用
 * 负责页面交互、WebSocket通信和游戏逻辑
 */

// ============================================
// 全局配置和状态
// ============================================
const CONFIG = {
    API_BASE_URL: 'http://localhost:5000/api/v1',
    WS_URL: 'http://localhost:5000',
    TARGET_SQUAT_COUNT: 5
};

const AppState = {
    currentScreen: 'loading',
    socket: null,
    localStream: null,  // 本地摄像头流
    isChallengeActive: false,
    currentCount: 0,
    targetCount: 5,
    systemStatus: {
        detectorReady: false
    }
};

// ============================================
// 工具函数
// ============================================
const Utils = {
    // 显示Toast提示
    showToast(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <span class="toast-message">${message}</span>
        `;

        document.body.appendChild(toast);

        requestAnimationFrame(() => {
            toast.classList.add('show');
        });

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
};

// ============================================
// WebSocket 管理
// ============================================
const SocketManager = {
    init() {
        return new Promise((resolve, reject) => {
            try {
                AppState.socket = io(CONFIG.WS_URL);

                AppState.socket.on('connect', () => {
                    console.log('WebSocket已连接');
                    this.setupEventListeners();
                    resolve();
                });

                AppState.socket.on('connect_error', (error) => {
                    console.error('WebSocket连接失败:', error);
                    reject(error);
                });

            } catch (error) {
                reject(error);
            }
        });
    },

    setupEventListeners() {
        // 连接成功
        AppState.socket.on('connected', (data) => {
            console.log('服务器连接确认:', data);
        });

        // 深蹲挑战开始确认
        AppState.socket.on('squat_challenge_started', (data) => {
            console.log('深蹲挑战开始:', data);
            AppState.targetCount = data.target_count || 5;
            AppState.isChallengeActive = true;
            Utils.showToast(data.message, 'success');
        });

        // 深蹲更新
        AppState.socket.on('squat_update', (data) => {
            AppState.currentCount = data.count;
            SquatUI.updateDisplay(data);
        });

        // 深蹲挑战完成
        AppState.socket.on('squat_completed', (data) => {
            console.log('深蹲挑战完成:', data);
            AppState.isChallengeActive = false;
            AppState.currentCount = data.final_count;

            // 停止摄像头
            SquatUI.stopCamera();

            // 显示成功页面
            setTimeout(() => {
                SquatUI.showSuccessScreen(data.final_count);
            }, 500);
        });

        // 深蹲停止确认
        AppState.socket.on('squat_stopped', (data) => {
            console.log('深蹲挑战已停止:', data);
            AppState.isChallengeActive = false;
        });

        // 错误
        AppState.socket.on('squat_error', (data) => {
            console.error('深蹲检测错误:', data);
            Utils.showToast(data.message || '发生错误', 'error');
        });
    },

    // 发送事件
    startSquatChallenge(targetCount = 5) {
        AppState.socket.emit('start_squat_challenge', {
            target_count: targetCount
        });
    },

    stopSquatChallenge() {
        AppState.socket.emit('stop_squat_challenge', {});
    },

    sendVideoFrame(base64Image) {
        AppState.socket.emit('video_frame', {
            image: base64Image
        });
    }
};

// ============================================
// 页面切换管理
// ============================================
const ScreenManager = {
    screens: {},

    init() {
        document.querySelectorAll('.screen').forEach(screen => {
            this.screens[screen.id] = screen;
        });
    },

    show(screenId) {
        Object.values(this.screens).forEach(screen => {
            screen.classList.remove('active');
        });

        const targetScreen = this.screens[screenId];
        if (targetScreen) {
            targetScreen.classList.add('active');
            AppState.currentScreen = screenId;
        }
    },

    getCurrent() {
        return AppState.currentScreen;
    }
};

// ============================================
// 深蹲挑战UI控制器
// ============================================
const SquatUI = {
    videoElement: null,
    processedFrameElement: null,
    cameraPlaceholder: null,
    frameInterval: null,

    init() {
        this.videoElement = document.getElementById('local-video');
        this.processedFrameElement = document.getElementById('processed-frame');
        this.cameraPlaceholder = document.getElementById('camera-placeholder');

        this.bindEvents();
    },

    bindEvents() {
        // 开始挑战按钮
        document.getElementById('btn-start-challenge').addEventListener('click', () => {
            this.startChallenge();
        });

        // 启用摄像头按钮
        document.getElementById('btn-enable-camera').addEventListener('click', () => {
            this.startCamera();
        });

        // 停止挑战按钮
        document.getElementById('btn-stop-squat').addEventListener('click', () => {
            this.stopChallenge();
        });

        // 确认成功按钮
        document.getElementById('btn-confirm-success').addEventListener('click', () => {
            this.returnToStart();
        });
    },

    startChallenge() {
        console.log('开始挑战按钮被点击');
        console.log('当前检测器状态:', AppState.systemStatus.detectorReady);

        // 检查检测器是否就绪
        if (!AppState.systemStatus.detectorReady) {
            Utils.showToast('深蹲检测器正在初始化，请稍候...', 'warning');
            console.warn('检测器未就绪，无法开始挑战');
            return;
        }

        console.log('检测器已就绪，开始挑战流程');

        // 切换到深蹲页面
        ScreenManager.show('squat-screen');
        console.log('已切换到深蹲页面');

        // 启动摄像头
        this.startCamera();

        // 通知服务器开始深蹲挑战
        SocketManager.startSquatChallenge(5);
    },

    async startCamera() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: 'user'
                },
                audio: false
            });

            AppState.localStream = stream;
            this.videoElement.srcObject = stream;

            // 隐藏占位符，显示视频
            this.cameraPlaceholder.style.display = 'none';
            this.videoElement.style.display = 'block';
            this.processedFrameElement.style.display = 'block';

            // 开始发送视频帧
            this.startFrameSending();

            Utils.showToast('摄像头已启动', 'success');

        } catch (error) {
            console.error('启动摄像头失败:', error);
            Utils.showToast('无法访问摄像头，请检查权限设置', 'error');
        }
    },

    stopCamera() {
        // 停止发送帧
        if (this.frameInterval) {
            clearInterval(this.frameInterval);
            this.frameInterval = null;
        }

        // 停止视频流
        if (AppState.localStream) {
            AppState.localStream.getTracks().forEach(track => track.stop());
            AppState.localStream = null;
        }

        // 隐藏视频元素
        if (this.videoElement) {
            this.videoElement.srcObject = null;
            this.videoElement.style.display = 'none';
        }

        if (this.processedFrameElement) {
            this.processedFrameElement.style.display = 'none';
            this.processedFrameElement.src = '';
        }

        // 显示占位符
        if (this.cameraPlaceholder) {
            this.cameraPlaceholder.style.display = 'flex';
        }
    },

    startFrameSending() {
        // 每隔一定时间发送视频帧到服务器
        const frameRate = 15; // 每秒15帧
        const interval = 1000 / frameRate;

        this.frameInterval = setInterval(() => {
            this.captureAndSendFrame();
        }, interval);
    },

    captureAndSendFrame() {
        if (!this.videoElement || !AppState.isChallengeActive) return;

        try {
            // 创建canvas来捕获视频帧
            const canvas = document.createElement('canvas');
            canvas.width = 640;
            canvas.height = 480;
            const ctx = canvas.getContext('2d');

            // 绘制视频帧
            ctx.drawImage(this.videoElement, 0, 0, canvas.width, canvas.height);

            // 转换为base64
            const base64Image = canvas.toDataURL('image/jpeg', 0.7);

            // 发送到服务器
            SocketManager.sendVideoFrame(base64Image);

        } catch (error) {
            console.error('捕获帧失败:', error);
        }
    },

    updateDisplay(data) {
        // 更新当前计数
        const currentCountEl = document.getElementById('current-count');
        if (currentCountEl) {
            currentCountEl.textContent = data.count;
        }

        // 更新进度条
        const progressBar = document.getElementById('squat-progress-bar');
        const progressText = document.getElementById('squat-progress-text');
        if (progressBar && progressText) {
            progressBar.style.width = `${data.progress}%`;
            progressText.textContent = `${data.progress}%`;
        }

        // 更新处理后的图像
        if (data.image && this.processedFrameElement) {
            this.processedFrameElement.src = data.image;
        }

        // 更新状态文字
        const statusEl = document.getElementById('squat-status');
        if (statusEl) {
            const state = data.state || 'unknown';
            const stateMap = {
                'standing': { icon: '⏳', text: '站立中，准备下蹲...' },
                'squatting': { icon: '⬇️', text: '正在下蹲...' },
                'deep_squat': { icon: '🔻', text: '深蹲到位！准备站起...' },
                'rising': { icon: '⬆️', text: '正在站起...' },
                'unknown': { icon: '⏳', text: '请站好准备开始...' }
            };
            const stateInfo = stateMap[state] || stateMap['unknown'];
            statusEl.innerHTML = `
                <span class="status-icon">${stateInfo.icon}</span>
                <span class="status-text">${stateInfo.text}</span>
            `;
        }
    },

    stopChallenge() {
        // 停止摄像头
        this.stopCamera();

        // 停止挑战
        AppState.isChallengeActive = false;
        SocketManager.stopSquatChallenge();

        // 重置计数
        AppState.currentCount = 0;

        // 返回开始页面
        ScreenManager.show('start-screen');

        Utils.showToast('挑战已停止', 'info');
    },

    showSuccessScreen(finalCount) {
        // 更新最终计数
        const finalCountEl = document.getElementById('final-squat-count');
        if (finalCountEl) {
            finalCountEl.textContent = finalCount;
        }

        // 显示成功页面
        ScreenManager.show('success-screen');
    },

    returnToStart() {
        // 重置状态
        AppState.currentCount = 0;
        AppState.isChallengeActive = false;

        // 更新计数显示
        const currentCountEl = document.getElementById('current-count');
        if (currentCountEl) {
            currentCountEl.textContent = '0';
        }

        // 重置进度条
        const progressBar = document.getElementById('squat-progress-bar');
        const progressText = document.getElementById('squat-progress-text');
        if (progressBar && progressText) {
            progressBar.style.width = '0%';
            progressText.textContent = '0%';
        }

        // 重置处理后的图像
        if (this.processedFrameElement) {
            this.processedFrameElement.src = '';
        }

        // 返回开始页面
        ScreenManager.show('start-screen');
    }
};

// ============================================
// 系统状态检查
// ============================================
const SystemCheck = {
    async checkDetectorStatus() {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}/system/status`);
            const result = await response.json();

            if (result.success) {
                AppState.systemStatus.detectorReady = result.data.squat_detector_ready;
                this.updateStatusUI();
            }
        } catch (error) {
            console.error('检查系统状态失败:', error);
        }
    },

    updateStatusUI() {
        const dot = document.getElementById('detector-status-dot');
        const text = document.getElementById('detector-status-text');

        if (dot && text) {
            if (AppState.systemStatus.detectorReady) {
                dot.classList.add('ready');
                text.textContent = '检测器就绪';
            } else {
                dot.classList.remove('ready');
                text.textContent = '检测器初始化中...';
            }
        }
    },

    startStatusPolling() {
        // 每秒检查一次状态
        setInterval(() => {
            this.checkDetectorStatus();
        }, 2000);
    }
};

// ============================================
// 初始化应用
// ============================================
document.addEventListener('DOMContentLoaded', async () => {
    console.log('深蹲闯关游戏 - 初始化中...');

    // 初始化屏幕管理器
    ScreenManager.init();

    // 初始化深蹲UI
    SquatUI.init();

    // 模拟加载过程
    const loadingTexts = [
        '正在加载资源...',
        '初始化检测模型...',
        '连接服务器...',
        '准备就绪!'
    ];

    const loadingTextEl = document.querySelector('.loading-text');

    for (let i = 0; i < loadingTexts.length; i++) {
        await new Promise(resolve => setTimeout(resolve, 600));
        if (loadingTextEl) loadingTextEl.textContent = loadingTexts[i];
    }

    // 初始化WebSocket
    try {
        await SocketManager.init();
        console.log('WebSocket连接成功');
    } catch (error) {
        console.warn('WebSocket连接失败，部分功能可能受限');
    }

    // 启动系统状态检查
    SystemCheck.checkDetectorStatus();
    SystemCheck.startStatusPolling();

    // 延迟切换到主页面
    await new Promise(resolve => setTimeout(resolve, 500));
    ScreenManager.show('start-screen');

    console.log('初始化完成!');
});

// 导出全局对象供调试
window.SquatGame = {
    AppState,
    Utils,
    SocketManager,
    ScreenManager,
    SquatUI
};
