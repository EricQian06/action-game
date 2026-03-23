/**
 * 动作闯关游戏 - 前端主应用
 * 负责页面交互、WebSocket通信和游戏逻辑
 */

// ============================================
// 全局配置和状态
// ============================================
const CONFIG = {
    API_BASE_URL: 'http://localhost:5000/api/v1',
    WS_URL: 'http://localhost:5000',
    COUNTDOWN_SECONDS: 3,
    ACTION_TIMEOUT: 10
};

const AppState = {
    currentScreen: 'loading',
    user: null,
    socket: null,
    currentSession: null,
    currentLevel: null,
    gameState: 'idle', // idle, countdown, capturing, processing, result
    countdownInterval: null,
    systemStatus: {
        stm32Connected: false,
        cameraReady: false,
        mediaPipeReady: false
    }
};

// ============================================
// 工具函数
// ============================================
const Utils = {
    // 格式化时间
    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    },

    // 防抖函数
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // 动画数字
    animateNumber(element, target, duration = 1000) {
        const start = parseInt(element.textContent) || 0;
        const startTime = performance.now();

        const update = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // 使用缓动函数
            const easeOutQuart = 1 - Math.pow(1 - progress, 4);
            const current = Math.floor(start + (target - start) * easeOutQuart);

            element.textContent = current;

            if (progress < 1) {
                requestAnimationFrame(update);
            }
        };

        requestAnimationFrame(update);
    },

    // 显示Toast提示
    showToast(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <span class="toast-message">${message}</span>
        `;

        document.body.appendChild(toast);

        // 触发动画
        requestAnimationFrame(() => {
            toast.classList.add('show');
        });

        // 自动移除
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    },

    // 显示/隐藏加载动画
    showLoading(element, text = '加载中...') {
        const loader = document.createElement('div');
        loader.className = 'loading-overlay';
        loader.innerHTML = `
            <div class="loading-spinner"></div>
            <span class="loading-text">${text}</span>
        `;
        element.style.position = 'relative';
        element.appendChild(loader);
        return loader;
    },

    hideLoading(element) {
        const loader = element.querySelector('.loading-overlay');
        if (loader) loader.remove();
    }
};

// ============================================
// API 通信
// ============================================
const API = {
    // 基础请求函数
    async request(endpoint, options = {}) {
        const url = `${CONFIG.API_BASE_URL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        if (config.body && typeof config.body === 'object') {
            config.body = JSON.stringify(config.body);
        }

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || `HTTP ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error('API请求失败:', error);
            throw error;
        }
    },

    // 用户认证
    auth: {
        async register(username, password) {
            return API.request('/auth/register', {
                method: 'POST',
                body: { username, password }
            });
        },

        async login(username, password) {
            const response = await API.request('/auth/login', {
                method: 'POST',
                body: { username, password }
            });

            if (response.success) {
                AppState.user = response.data;
                localStorage.setItem('user', JSON.stringify(response.data));
            }

            return response;
        },

        logout() {
            AppState.user = null;
            localStorage.removeItem('user');
        }
    },

    // 游戏数据
    game: {
        async getLevels() {
            return API.request('/game/levels');
        },

        async getLevel(levelId) {
            return API.request(`/game/level/${levelId}`);
        },

        async startGame(userId, levelId) {
            return API.request('/game/start', {
                method: 'POST',
                body: { user_id: userId, level_id: levelId }
            });
        }
    },

    // 系统状态
    system: {
        async getStatus() {
            return API.request('/system/status');
        }
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

                AppState.socket.on('disconnect', () => {
                    console.log('WebSocket已断开');
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

        // 加入游戏确认
        AppState.socket.on('joined', (data) => {
            console.log('已加入游戏:', data);
        });

        // 倒计时开始
        AppState.socket.on('countdown_start', (data) => {
            console.log('倒计时开始:', data);
            GameUI.startCountdown(data.seconds);
        });

        // 倒计时滴答
        AppState.socket.on('countdown_tick', (data) => {
            GameUI.updateCountdown(data.seconds_remaining);
        });

        // 触发拍照
        AppState.socket.on('capture_triggered', (data) => {
            console.log('拍照已触发:', data);
            GameUI.showCapturingState();
        });

        // 预览图像
        AppState.socket.on('preview_image', (data) => {
            console.log('收到预览图像');
            GameUI.showPreviewImage(data.image_base64);
        });

        // 动作结果
        AppState.socket.on('action_result', (data) => {
            console.log('动作结果:', data);
            GameUI.showActionResult(data);
        });

        // 下一个动作
        AppState.socket.on('action_assigned', (data) => {
            console.log('下一个动作:', data);
            GameUI.setupNextAction(data);
        });

        // 游戏结束
        AppState.socket.on('game_ended', (data) => {
            console.log('游戏结束:', data);
            GameUI.showGameResult(data);
        });

        // 错误
        AppState.socket.on('error', (data) => {
            console.error('服务器错误:', data);
            Utils.showToast(data.message || '发生错误', 'error');
        });
    },

    // 发送事件
    joinGame(sessionId) {
        AppState.socket.emit('join_game', { session_id: sessionId });
    },

    leaveGame(sessionId) {
        AppState.socket.emit('leave_game', { session_id: sessionId });
    },

    playerReady(sessionId, actionIndex) {
        AppState.socket.emit('player_ready', {
            session_id: sessionId,
            action_index: actionIndex
        });
    }
};

// ============================================
// 页面切换管理
// ============================================
const ScreenManager = {
    screens: {},

    init() {
        // 收集所有屏幕
        document.querySelectorAll('.screen').forEach(screen => {
            this.screens[screen.id] = screen;
        });
    },

    show(screenId) {
        // 隐藏所有屏幕
        Object.values(this.screens).forEach(screen => {
            screen.classList.remove('active');
        });

        // 显示目标屏幕
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
// 游戏UI控制器
// ============================================
const GameUI = {
    // 开始倒计时
    startCountdown(seconds) {
        AppState.gameState = 'countdown';
        const overlay = document.getElementById('countdown-overlay');
        const numberEl = document.getElementById('countdown-number');

        overlay.classList.add('active');

        let count = seconds;
        numberEl.textContent = count;

        const interval = setInterval(() => {
            count--;
            if (count > 0) {
                numberEl.textContent = count;
                numberEl.classList.add('pulse');
                setTimeout(() => numberEl.classList.remove('pulse'), 300);
            } else {
                clearInterval(interval);
                overlay.classList.remove('active');
            }
        }, 1000);

        AppState.countdownInterval = interval;
    },

    // 更新倒计时
    updateCountdown(seconds) {
        const numberEl = document.getElementById('countdown-number');
        if (numberEl) {
            numberEl.textContent = seconds;
        }
    },

    // 显示拍照中状态
    showCapturingState() {
        AppState.gameState = 'capturing';
        const previewPanel = document.getElementById('camera-preview-panel');
        previewPanel.classList.add('capturing');

        // 显示闪烁效果
        const flash = document.createElement('div');
        flash.className = 'camera-flash';
        document.body.appendChild(flash);

        setTimeout(() => {
            flash.remove();
            previewPanel.classList.remove('capturing');
        }, 300);
    },

    // 显示预览图像
    showPreviewImage(base64Data) {
        const img = document.getElementById('camera-preview-img');
        const placeholder = document.querySelector('.preview-placeholder');

        img.src = `data:image/jpeg;base64,${base64Data}`;
        img.style.display = 'block';

        if (placeholder) {
            placeholder.style.display = 'none';
        }
    },

    // 显示动作结果
    showActionResult(data) {
        AppState.gameState = 'result';

        const overlay = document.getElementById('action-result-overlay');
        const icon = document.getElementById('result-icon');
        const score = document.getElementById('result-score');
        const feedback = document.getElementById('result-feedback');

        // 设置结果内容
        overlay.className = 'action-result-overlay active ' + (data.success ? 'success' : 'failure');
        icon.innerHTML = data.success ? '✓' : '✗';
        score.textContent = Math.round(data.score * 100);
        feedback.textContent = data.feedback;

        // 显示并自动隐藏
        setTimeout(() => {
            overlay.classList.remove('active');
        }, 3000);

        // 更新分数显示
        this.updateGameScore(data.score);
    },

    // 设置下一个动作
    setupNextAction(data) {
        // 更新目标动作显示
        const poseImg = document.getElementById('target-pose-img');
        const poseName = document.getElementById('target-pose-name');

        if (data.action) {
            poseImg.src = `assets/poses/${data.action.name_en}.svg`;
            poseName.textContent = data.action.name;
        }

        // 更新进度
        document.getElementById('current-action-num').textContent = data.action_index + 1;
        this.updateProgressBar(data.action_index + 1);

        // 重置准备按钮
        const readyBtn = document.getElementById('btn-start-action');
        readyBtn.disabled = false;
        readyBtn.innerHTML = '<i class="icon-play"></i><span>准备就绪</span>';

        AppState.gameState = 'idle';
    },

    // 更新游戏分数
    updateGameScore(score) {
        const scoreEl = document.getElementById('game-score');
        const currentScore = parseInt(scoreEl.textContent) || 0;
        const newScore = currentScore + Math.round(score * 100);

        Utils.animateNumber(scoreEl, newScore, 500);
    },

    // 更新进度条
    updateProgressBar(current) {
        const total = parseInt(document.getElementById('total-action-num').textContent) || 1;
        const percentage = (current / total) * 100;
        document.getElementById('action-progress-fill').style.width = percentage + '%';
    },

    // 显示游戏结果
    showGameResult(data) {
        ScreenManager.show('result-screen');

        // 更新结果数据
        document.getElementById('final-score').textContent = data.total_score || 0;
        document.getElementById('actions-completed').textContent =
            `${data.actions_completed || 0}/${data.actions_total || 0}`;
        document.getElementById('accuracy').textContent =
            Math.round((data.completion_rate || 0) * 100) + '%';

        // 更新星级
        const stars = Math.ceil((data.completion_rate || 0) * 3);
        document.querySelectorAll('#result-stars .star').forEach((star, index) => {
            star.classList.toggle('active', index < stars);
        });
    }
};

// ============================================
// 事件处理器
// ============================================
const EventHandlers = {
    init() {
        this.setupAuthEvents();
        this.setupMenuEvents();
        this.setupGameEvents();
    },

    // 认证相关事件
    setupAuthEvents() {
        // 登录/注册标签切换
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tab = e.target.dataset.tab;

                // 切换标签按钮
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');

                // 切换表单
                document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
                document.getElementById(`${tab}-form`).classList.add('active');
            });
        });

        // 登录表单提交
        document.getElementById('login-form').addEventListener('submit', async (e) => {
            e.preventDefault();

            const username = document.getElementById('login-username').value;
            const password = document.getElementById('login-password').value;

            try {
                const result = await API.auth.login(username, password);
                if (result.success) {
                    Utils.showToast('登录成功!', 'success');
                    this.onLoginSuccess(result.data);
                }
            } catch (error) {
                Utils.showToast(error.message || '登录失败', 'error');
            }
        });

        // 注册表单提交
        document.getElementById('register-form').addEventListener('submit', async (e) => {
            e.preventDefault();

            const username = document.getElementById('reg-username').value;
            const password = document.getElementById('reg-password').value;
            const passwordConfirm = document.getElementById('reg-password-confirm').value;

            if (password !== passwordConfirm) {
                Utils.showToast('两次输入的密码不一致', 'error');
                return;
            }

            try {
                const result = await API.auth.register(username, password);
                if (result.success) {
                    Utils.showToast('注册成功!请登录', 'success');
                    // 切换到登录标签
                    document.querySelector('.tab-btn[data-tab="login"]').click();
                }
            } catch (error) {
                Utils.showToast(error.message || '注册失败', 'error');
            }
        });
    },

    // 菜单相关事件
    setupMenuEvents() {
        // 检查系统状态
        document.getElementById('btn-refresh-status')?.addEventListener('click', () => {
            this.updateSystemStatus();
        });
    },

    // 游戏相关事件
    setupGameEvents() {
        // 准备按钮
        document.getElementById('btn-start-action')?.addEventListener('click', () => {
            if (AppState.currentSession) {
                const actionIndex = parseInt(document.getElementById('current-action-num').textContent) - 1;
                SocketManager.playerReady(AppState.currentSession.session_id, actionIndex);

                // 禁用按钮
                const btn = document.getElementById('btn-start-action');
                btn.disabled = true;
                btn.innerHTML = '<i class="icon-loading"></i><span>等待中...</span>';
            }
        });

        // 暂停按钮
        document.getElementById('btn-pause')?.addEventListener('click', () => {
            // 显示暂停菜单
            this.showPauseMenu();
        });

        // 结果页面按钮
        document.getElementById('btn-retry')?.addEventListener('click', () => {
            // 重新开始当前关卡
            if (AppState.currentLevel) {
                this.startGame(AppState.currentLevel.id);
            }
        });

        document.getElementById('btn-next-level')?.addEventListener('click', () => {
            // 进入下一关
            if (AppState.currentLevel) {
                this.startGame(AppState.currentLevel.id + 1);
            }
        });

        document.getElementById('btn-back-menu')?.addEventListener('click', () => {
            ScreenManager.show('main-menu-screen');
        });
    },

    // 登录成功处理
    onLoginSuccess(userData) {
        AppState.user = userData;
        this.updateUserInfo(userData);
        this.loadLevels();
        ScreenManager.show('main-menu-screen');
    },

    // 更新用户信息显示
    updateUserInfo(userData) {
        document.getElementById('user-name').textContent = userData.username;
        document.getElementById('user-level').textContent = userData.current_level;
        document.getElementById('user-score').textContent = userData.total_score;
    },

    // 加载关卡列表
    async loadLevels() {
        const container = document.getElementById('levels-container');

        try {
            const result = await API.game.getLevels();

            if (result.success) {
                container.innerHTML = '';

                result.data.forEach(level => {
                    const card = this.createLevelCard(level);
                    container.appendChild(card);
                });
            }
        } catch (error) {
            console.error('加载关卡失败:', error);
            Utils.showToast('加载关卡失败', 'error');
        }
    },

    // 创建关卡卡片
    createLevelCard(level) {
        const card = document.createElement('div');
        card.className = 'level-card';
        card.dataset.levelId = level.id;

        const isLocked = level.id > (AppState.user?.current_level || 1);

        card.innerHTML = `
            <div class="level-preview">
                <div class="level-number">${level.id}</div>
                ${isLocked ? '<div class="lock-icon">🔒</div>' : ''}
            </div>
            <div class="level-info">
                <h3>${level.name}</h3>
                <p class="level-description">${level.description}</p>
                <div class="level-meta">
                    <span class="difficulty">
                        ${'★'.repeat(level.difficulty)}${'☆'.repeat(5 - level.difficulty)}
                    </span>
                    <span class="actions">${level.action_sequence?.length || 0} 个动作</span>
                </div>
            </div>
        `;

        if (!isLocked) {
            card.addEventListener('click', () => {
                this.startGame(level.id);
            });
        }

        return card;
    },

    // 开始游戏
    async startGame(levelId) {
        if (!AppState.user) {
            Utils.showToast('请先登录', 'warning');
            ScreenManager.show('auth-screen');
            return;
        }

        // 检查系统状态
        if (!AppState.systemStatus.stm32Connected) {
            Utils.showToast('开发板未连接，请检查硬件', 'error');
            return;
        }

        try {
            // 加载关卡详情
            const levelResult = await API.game.getLevel(levelId);
            if (levelResult.success) {
                AppState.currentLevel = levelResult.data;
                this.setupGameUI(levelResult.data);
            }

            // 创建游戏会话
            const result = await API.game.startGame(AppState.user.user_id, levelId);

            if (result.success) {
                AppState.currentSession = result.data;

                // 加入WebSocket房间
                SocketManager.joinGame(result.data.session_id);

                // 切换到游戏屏幕
                ScreenManager.show('game-screen');

                // 设置第一个动作
                if (result.data.first_action) {
                    this.setupTargetAction(result.data.first_action);
                }

                Utils.showToast('游戏开始！准备好挑战吧！', 'success');
            }
        } catch (error) {
            console.error('开始游戏失败:', error);
            Utils.showToast(error.message || '开始游戏失败', 'error');
        }
    },

    // 设置游戏UI
    setupGameUI(levelData) {
        document.getElementById('game-level-name').textContent = levelData.name;
        document.getElementById('total-action-num').textContent =
            levelData.actions?.length || levelData.action_sequence?.length || 0;
        document.getElementById('current-action-num').textContent = '1';
        document.getElementById('game-score').textContent = '0';

        this.updateProgressBar(1);
    },

    // 设置目标动作
    setupTargetAction(action) {
        const img = document.getElementById('target-pose-img');
        const name = document.getElementById('target-pose-name');

        img.src = `assets/poses/${action.name_en || 'placeholder'}.svg`;
        img.onerror = () => {
            img.src = 'assets/poses/pose-placeholder.svg';
        };

        name.textContent = action.name || '准备动作';
    },

    // 更新系统状态显示
    updateSystemStatus() {
        API.system.getStatus().then(result => {
            if (result.success) {
                const status = result.data;
                AppState.systemStatus = {
                    stm32Connected: status.stm32_connected,
                    cameraReady: status.camera_ready,
                    mediaPipeReady: status.mediapipe_ready
                };

                // 更新UI
                this.updateStatusIndicators();
            }
        }).catch(error => {
            console.error('获取系统状态失败:', error);
        });
    },

    // 更新状态指示器
    updateStatusIndicators() {
        const stm32El = document.getElementById('status-stm32');
        const cameraEl = document.getElementById('status-camera');

        if (stm32El) {
            stm32El.classList.toggle('connected', AppState.systemStatus.stm32Connected);
        }
        if (cameraEl) {
            cameraEl.classList.toggle('connected', AppState.systemStatus.cameraReady);
        }
    },

    // 显示暂停菜单
    showPauseMenu() {
        // 实现暂停菜单显示逻辑
        console.log('显示暂停菜单');
    }
};

// ============================================
// 初始化应用
// ============================================
document.addEventListener('DOMContentLoaded', async () => {
    console.log('动作闯关游戏 - 初始化中...');

    // 初始化屏幕管理器
    ScreenManager.init();

    // 检查本地存储的用户信息
    const savedUser = localStorage.getItem('user');
    if (savedUser) {
        AppState.user = JSON.parse(savedUser);
        GameUI.updateUserInfo(AppState.user);
    }

    // 模拟加载过程
    const loadingTexts = [
        '正在加载资源...',
        '初始化游戏模块...',
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

    // 延迟切换到主屏幕
    await new Promise(resolve => setTimeout(resolve, 500));

    // 根据用户状态决定显示哪个屏幕
    if (AppState.user) {
        await GameUI.loadLevels();
        ScreenManager.show('main-menu-screen');
        GameUI.updateSystemStatus();
    } else {
        ScreenManager.show('auth-screen');
    }

    console.log('初始化完成!');
});

// 导出全局对象供调试
window.ActionGame = {
    AppState,
    Utils,
    API,
    GameUI,
    ScreenManager
};
