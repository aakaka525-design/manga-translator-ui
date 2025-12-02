document.addEventListener('DOMContentLoaded', () => {
    init();
});

// ===== 公告功能 =====
async function loadAnnouncement() {
    try {
        const res = await fetch('/announcement');
        const announcement = await res.json();
        
        if (announcement.enabled && announcement.message) {
            const banner = document.getElementById('announcement-banner');
            banner.textContent = announcement.message;
            banner.style.display = 'block';
            
            // 根据类型设置颜色
            const colors = {
                'info': { bg: '#E3F2FD', text: '#1976D2', border: '#2196F3' },
                'warning': { bg: '#FFF3E0', text: '#E65100', border: '#FF9800' },
                'error': { bg: '#FFEBEE', text: '#C62828', border: '#F44336' }
            };
            
            const color = colors[announcement.type] || colors.info;
            banner.style.backgroundColor = color.bg;
            banner.style.color = color.text;
            banner.style.borderBottom = `3px solid ${color.border}`;
        }
    } catch (e) {
        console.error('Failed to load announcement:', e);
    }
}

// State
let configSchema = {};
let fileList = [];
const hiddenKeys = [
    // 通过其他UI控制的参数
    'upscale.realcugan_model',  // 通过 upscale_ratio 动态控制
    'cli.load_text',  // 通过工作流模式下拉框控制
    'cli.template',  // 通过工作流模式下拉框控制
    'cli.generate_and_export',  // 通过工作流模式下拉框控制
    'cli.colorize_only',  // 通过工作流模式下拉框控制
    'cli.upscale_only',  // 通过工作流模式下拉框控制
    'cli.inpaint_only',  // 通过工作流模式下拉框控制
    // 翻译后检查参数（默认隐藏）
    'translator.enable_post_translation_check',
    'translator.post_check_max_retry_attempts',
    'translator.post_check_repetition_threshold',
    'translator.post_check_target_lang_threshold',
    // 高级翻译器参数（默认隐藏）
    'translator.translator_chain',  // 链式翻译
    'translator.selective_translation',  // Selective Translation
    'translator.skip_lang',  // Skip Lang
    // 废弃参数
    'render.gimp_font',  // 已废弃，使用 font_path 代替
];

// DOM Elements
const els = {
    fileInput: document.getElementById('file-input'),
    folderInput: document.getElementById('folder-input'),
    addFilesBtn: document.getElementById('add-files-btn'),
    addFolderBtn: document.getElementById('add-folder-btn'),
    clearListBtn: document.getElementById('clear-list-btn'),
    fileList: document.getElementById('file-list'),
    fileCount: document.getElementById('file-count'),
    startBtn: document.getElementById('start-btn'),
    workflowMode: document.getElementById('workflow-mode'),
    logBox: document.getElementById('log-box'),
    clearLogBtn: document.getElementById('clear-log-btn'),
    tabs: document.querySelectorAll('.tab-btn'),
    tabPanes: document.querySelectorAll('.tab-pane'),
    exportConfigBtn: document.getElementById('export-config-btn'),
    importConfigBtn: document.getElementById('import-config-btn'),
    configInput: document.getElementById('config-input'),
};

let configOptions = {};  // 存储参数选项

async function init() {
    // 检查是否需要密码
    await checkUserAccess();
    
    // 加载公告
    await loadAnnouncement();
    
    setupEventListeners();
    await loadI18n(); // Load i18n first
    await loadUserSettings(); // Load user visibility settings
    await loadConfigOptions(); // Load parameter options
    await loadConfig();
    await loadFonts();
    await loadPrompts();
    await loadTranslators(); // Load translators
    await loadLanguages(); // Load languages
    await loadWorkflows(); // Load workflows
    
    // 在所有数据加载完成后，填充下拉菜单
    populateDropdowns();
    
    // 只有在允许用户编辑 API keys 时才从 localStorage 恢复
    // 否则清除旧数据，避免覆盖服务器的 API keys
    try {
        // 先检查是否允许用户编辑（通过检查 API key 策略）
        fetch('/api-key-policy')
            .then(res => res.json())
            .then(policy => {
                const showEnvToUsers = policy.show_env_to_users || false;
                
                if (showEnvToUsers) {
                    // 允许用户编辑，恢复保存的 API keys
                    const saved = localStorage.getItem('user_env_vars');
                    if (saved) {
                        currentEnvVars = JSON.parse(saved);
                    }
                } else {
                    // 不允许用户编辑，清除旧数据
                    localStorage.removeItem('user_env_vars');
                    currentEnvVars = {};
                }
            })
            .catch(e => {
                console.error('Failed to check API key policy:', e);
                // 出错时为了安全起见，清除旧数据
                localStorage.removeItem('user_env_vars');
                currentEnvVars = {};
            });
    } catch (e) {
        console.error('Failed to load API keys from localStorage:', e);
    }
    
    // 加载保存的翻译结果
    loadResults();
    
    startLogPolling(); // Start polling logs
}

async function checkUserAccess() {
    try {
        // 首先检查管理员是否已设置密码
        const setupRes = await fetch('/admin/need-setup');
        const setupData = await setupRes.json();
        
        if (setupData.need_setup) {
            // 管理员还没设置密码，提示用户先设置
            const setupPrompt = document.createElement('div');
            setupPrompt.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.8);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 10000;
            `;
            setupPrompt.innerHTML = `
                <div style="background: white; padding: 40px; border-radius: 8px; max-width: 500px; text-align: center;">
                    <h2 style="color: #2196F3; margin-bottom: 20px;">⚠️ 首次使用提示</h2>
                    <p style="font-size: 16px; color: #333; margin-bottom: 30px;">
                        检测到管理员密码尚未设置。<br>
                        为了系统安全，请先设置管理员密码。
                    </p>
                    <button onclick="window.location.href='/admin'" 
                            style="background: #2196F3; color: white; border: none; padding: 12px 30px; 
                                   font-size: 16px; border-radius: 4px; cursor: pointer;">
                        前往设置管理员密码
                    </button>
                </div>
            `;
            document.body.appendChild(setupPrompt);
            throw new Error('Admin password not set');
        }
        
        // 管理员密码已设置，检查用户端访问权限
        const res = await fetch('/user/access');
        const data = await res.json();
        
        if (data.require_password) {
            // 检查是否已经登录
            const isLoggedIn = sessionStorage.getItem('user_logged_in');
            if (!isLoggedIn) {
                // 显示登录界面
                document.getElementById('user-login-screen').style.display = 'flex';
                // 阻止页面交互
                return new Promise((resolve) => {
                    window.userLoginResolve = resolve;
                });
            }
        }
    } catch (e) {
        console.error('Failed to check user access:', e);
        // 如果是管理员密码未设置的错误，不继续执行
        if (e.message === 'Admin password not set') {
            throw e;
        }
    }
}

async function userLogin() {
    const password = document.getElementById('user-password-input').value;
    const errorEl = document.getElementById('user-login-error');
    
    try {
        const formData = new FormData();
        formData.append('password', password);
        
        const res = await fetch('/user/login', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        
        if (data.success) {
            // 登录成功
            sessionStorage.setItem('user_logged_in', 'true');
            document.getElementById('user-login-screen').style.display = 'none';
            errorEl.textContent = '';
            
            // 继续初始化
            if (window.userLoginResolve) {
                window.userLoginResolve();
            }
        } else {
            errorEl.textContent = '密码错误，请重试';
        }
    } catch (e) {
        errorEl.textContent = '登录失败：' + e.message;
    }
}

// 监听回车键登录
document.addEventListener('DOMContentLoaded', () => {
    const passwordInput = document.getElementById('user-password-input');
    if (passwordInput) {
        passwordInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                userLogin();
            }
        });
    }
});

async function loadConfigOptions() {
    try {
        const res = await fetch('/config/options');
        configOptions = await res.json();
        console.log('Loaded config options:', configOptions);
        console.log('high_quality_prompt_path options:', configOptions['high_quality_prompt_path']);
        console.log('font_path options:', configOptions['font_path']);
        console.log('layout_mode options:', configOptions['layout_mode']);
    } catch (e) {
        console.error('Error loading config options:', e);
    }
}

// --- i18n Handling ---
let i18nData = {};
let currentLocale = 'zh_CN'; // Default

async function loadI18n() {
    try {
        // 1. 从 localStorage 读取用户选择的语言
        const savedLocale = localStorage.getItem('locale');
        if (savedLocale) {
            currentLocale = savedLocale;
        } else {
            // 2. 检测浏览器语言
            const browserLang = navigator.language.replace('-', '_');
            if (browserLang.startsWith('en')) currentLocale = 'en_US';
            else if (browserLang.startsWith('zh-CN') || browserLang.startsWith('zh_CN')) currentLocale = 'zh_CN';
            else if (browserLang.startsWith('zh-TW') || browserLang.startsWith('zh_TW')) currentLocale = 'zh_TW';
            else if (browserLang.startsWith('ja')) currentLocale = 'ja_JP';
            else if (browserLang.startsWith('ko')) currentLocale = 'ko_KR';
            else if (browserLang.startsWith('es')) currentLocale = 'es_ES';
        }

        // 3. 从服务器获取翻译数据（使用桌面版的语言文件）
        console.log(`Loading i18n for locale: ${currentLocale}`);
        const res = await fetch(`/i18n/${currentLocale}`);
        i18nData = await res.json();
        console.log(`i18n data loaded, keys count: ${Object.keys(i18nData).length}`);
        console.log('Sample keys:', Object.keys(i18nData).slice(0, 10));

        // 4. 更新语言选择器
        const langSelect = document.getElementById('language-select');
        if (langSelect) {
            langSelect.value = currentLocale;
        }

        applyTranslations();
    } catch (e) {
        console.error("Failed to load i18n", e);
        // 回退到英语
        try {
            const res = await fetch('/i18n/en_US');
            i18nData = await res.json();
            applyTranslations();
        } catch (fallbackError) {
            console.error("Failed to load fallback language", fallbackError);
        }
    }
}

async function changeLanguage(locale) {
    currentLocale = locale;
    localStorage.setItem('locale', locale);
    
    try {
        const res = await fetch(`/i18n/${locale}`);
        i18nData = await res.json();
        applyTranslations();
        
        // 重新生成配置UI以应用新的翻译
        if (configSchema && Object.keys(configSchema).length > 0) {
            // 清空现有配置UI
            document.getElementById('basic-left').innerHTML = '';
            document.getElementById('basic-right').innerHTML = '';
            document.getElementById('advanced-left').innerHTML = '';
            document.getElementById('advanced-right').innerHTML = '';
            document.getElementById('options-left').innerHTML = '';
            document.getElementById('options-right').innerHTML = '';
            
            // 重新生成
            generateConfigUI(configSchema);
        }
        
        const langMsg = currentLocale.startsWith('zh') ? '语言已切换' : 'Language changed';
        log(`${langMsg}: ${locale}`, 'info');
    } catch (e) {
        console.error("Failed to change language", e);
        const errorMsg = currentLocale.startsWith('zh') ? '切换语言失败' : 'Failed to change language';
        log(errorMsg, 'error');
    }
}

function t(key, defaultText = '') {
    // 如果 i18nData 还没加载，返回默认值或键名
    if (!i18nData || Object.keys(i18nData).length === 0) {
        return defaultText || key;
    }
    
    let text = i18nData[key] || defaultText || key;
    // Remove & shortcuts (e.g. "&File" -> "File")
    return text.replace(/&/g, '');
}

function applyTranslations() {
    // Static elements
    document.title = t('Manga Translator', 'Manga Translator Web UI');
    document.querySelector('header h1').textContent = t('Manga Translator');
    
    // Admin link
    const adminLinkText = document.getElementById('admin-link-text');
    if (adminLinkText) {
        adminLinkText.textContent = t('admin', '管理');
    }

    // Left Panel - 使用桌面版已有的键名
    const fileListHeader = document.querySelector('.file-section h3');
    if (fileListHeader) fileListHeader.textContent = '文件列表'; // 暂时硬编码，因为桌面版没有这个键
    
    document.getElementById('add-files-btn').textContent = t('Add Files');
    document.getElementById('clear-list-btn').textContent = t('Clear List');
    
    // 输出目录在 Web 模式下隐藏，不需要翻译
    // const outputHeader = document.querySelector('.output-section h3');
    // if (outputHeader) outputHeader.textContent = t('Output Directory:');
    // document.getElementById('output-dir').placeholder = t('Select or drag output folder...');
    document.querySelector('.workflow-section h3').textContent = t('Translation Workflow Mode:');
    document.getElementById('start-btn').textContent = t('Start Translation');
    document.getElementById('export-config-btn').textContent = t('Export Config');
    document.getElementById('import-config-btn').textContent = t('Import Config');

    // Tabs
    const tabs = document.querySelectorAll('.tab-btn');
    if (tabs[0]) tabs[0].textContent = t('Basic Settings');
    if (tabs[1]) tabs[1].textContent = t('Advanced Settings');
    if (tabs[2]) tabs[2].textContent = t('Options');
    if (tabs[3]) tabs[3].textContent = t('API Keys (.env)');
    
    // API Keys hint
    const envHint = document.getElementById('env-hint-text');
    if (envHint) envHint.textContent = t('env_hint', '根据选择的翻译器，下方会显示所需的 API 密钥输入框');

    // Log Header
    document.querySelector('.log-header h3').textContent = t('Log output...');

    // Workflow Options
    const workflowSelect = document.getElementById('workflow-mode');
    // We need to map values to keys. 
    // Since options are hardcoded in HTML, we can update them by value.
    const workflowMap = {
        'normal': 'Normal Translation',
        'export_trans': 'Export Translation',
        'export_raw': 'Export Original Text',
        'import_trans': 'Import Translation and Render',
        'colorize': 'Colorize Only',
        'upscale': 'Upscale Only',
        'inpaint': 'Inpaint Only' // Check key
    };

    Array.from(workflowSelect.options).forEach(opt => {
        const key = workflowMap[opt.value];
        if (key) opt.textContent = t(key, opt.textContent);
    });
}

function setupEventListeners() {
    // File Management
    els.addFilesBtn.addEventListener('click', () => els.fileInput.click());
    els.addFolderBtn.addEventListener('click', () => els.folderInput.click());
    els.fileInput.addEventListener('change', handleFileSelect);
    els.folderInput.addEventListener('change', handleFolderSelect);
    els.clearListBtn.addEventListener('click', clearFileList);

    // Tabs
    els.tabs.forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Actions
    els.startBtn.addEventListener('click', startTask);
    els.clearLogBtn.addEventListener('click', () => els.logBox.innerHTML = '');

    // Config IO
    els.exportConfigBtn.addEventListener('click', exportConfig);
    els.importConfigBtn.addEventListener('click', () => els.configInput.click());
    els.configInput.addEventListener('change', importConfig);

    // Language selector
    const langSelect = document.getElementById('language-select');
    if (langSelect) {
        langSelect.addEventListener('change', async (e) => {
            currentLocale = e.target.value;
            localStorage.setItem('locale', currentLocale);
            await loadI18n();
        });
    }
    
    // Upload handlers
    const fontUploadBtn = document.getElementById('font-upload-btn');
    const fontUploadInput = document.getElementById('font-upload-input');
    if (fontUploadBtn && fontUploadInput) {
        fontUploadBtn.addEventListener('click', () => fontUploadInput.click());
        fontUploadInput.addEventListener('change', handleFontUpload);
    }
    
    const promptUploadBtn = document.getElementById('prompt-upload-btn');
    const promptUploadInput = document.getElementById('prompt-upload-input');
    if (promptUploadBtn && promptUploadInput) {
        promptUploadBtn.addEventListener('click', () => promptUploadInput.click());
        promptUploadInput.addEventListener('change', handlePromptUpload);
    }
    
    // Results handlers
    const expandResultsBtn = document.getElementById('expand-results-btn');
    const downloadAllBtn = document.getElementById('download-all-btn');
    const clearResultsBtn = document.getElementById('clear-results-btn');
    if (expandResultsBtn) {
        expandResultsBtn.addEventListener('click', openImageViewer);
    }
    if (downloadAllBtn) {
        downloadAllBtn.addEventListener('click', downloadAllResults);
    }
    if (clearResultsBtn) {
        clearResultsBtn.addEventListener('click', clearResults);
    }
}

// --- Config Handling ---

async function loadConfig() {
    try {
        const res = await fetch('/config');
        configSchema = await res.json();
        generateConfigUI(configSchema);
    } catch (e) {
        log(`Error loading config: ${e.message}`, 'error');
    }
}

async function loadFonts() {
    try {
        const res = await fetch('/fonts');
        const fonts = await res.json();
        updateFontSelects(fonts);
    } catch (e) {
        log(`Error loading fonts: ${e.message}`, 'error');
    }
}

async function loadPrompts() {
    try {
        const res = await fetch('/prompts');
        const prompts = await res.json();
        updatePromptSelects(prompts);
    } catch (e) {
        log(`Error loading prompts: ${e.message}`, 'error');
    }
}

let availableTranslators = [];
let availableLanguages = [];

async function loadTranslators() {
    try {
        const res = await fetch('/translators');
        availableTranslators = await res.json();
        console.log('Available translators:', availableTranslators);
    } catch (e) {
        console.error('Error loading translators:', e);
    }
}

async function loadLanguages() {
    try {
        const res = await fetch('/languages');
        availableLanguages = await res.json();
        console.log('Available languages:', availableLanguages);
    } catch (e) {
        console.error('Error loading languages:', e);
    }
}

let availableWorkflows = [];
let userSettings = {};

async function loadUserSettings() {
    try {
        const res = await fetch('/user/settings');
        userSettings = await res.json();
        console.log('User settings:', userSettings);
        
        // 根据设置显示/隐藏 API Keys 标签
        const apikeysTab = document.getElementById('apikeys-tab');
        if (apikeysTab) {
            apikeysTab.style.display = userSettings.show_env_editor ? 'block' : 'none';
        }
        
        // 根据权限显示/隐藏上传区域
        const fontUploadSection = document.getElementById('font-upload-section');
        if (fontUploadSection) {
            fontUploadSection.style.display = userSettings.can_upload_fonts ? 'block' : 'none';
        }
        
        const promptUploadSection = document.getElementById('prompt-upload-section');
        if (promptUploadSection) {
            promptUploadSection.style.display = userSettings.can_upload_prompts ? 'block' : 'none';
        }
    } catch (e) {
        console.error('Error loading user settings:', e);
    }
}

async function loadWorkflows() {
    try {
        const res = await fetch('/workflows');
        availableWorkflows = await res.json();
        console.log('Available workflows:', availableWorkflows);
        updateWorkflowSelect();
    } catch (e) {
        console.error('Error loading workflows:', e);
    }
}

function updateWorkflowSelect() {
    const workflowSelect = document.getElementById('workflow-mode');
    if (!workflowSelect) return;
    
    // 保存当前选中的值
    const currentValue = workflowSelect.value;
    
    // 清空选项
    workflowSelect.innerHTML = '';
    
    // 翻译流程映射
    const workflowMap = {
        'normal': 'Normal Translation',
        'export_trans': 'Export Translation',
        'export_raw': 'Export Original Text',
        'import_trans': 'Import Translation and Render',
        'colorize': 'Colorize Only',
        'upscale': 'Upscale Only',
        'inpaint': 'Inpaint Only'
    };
    
    // 添加允许的选项
    availableWorkflows.forEach(workflow => {
        const option = document.createElement('option');
        option.value = workflow;
        option.textContent = t(workflowMap[workflow], workflowMap[workflow]);
        workflowSelect.appendChild(option);
    });
    
    // 恢复之前的选择（如果还在列表中）
    if (availableWorkflows.includes(currentValue)) {
        workflowSelect.value = currentValue;
    }
}

function generateConfigUI(config) {
    // Helper to create inputs
    const createInput = (key, value, parentKey) => {
        const fullKey = parentKey ? `${parentKey}.${key}` : key;
        if (hiddenKeys.includes(fullKey)) return null;

        const wrapper = document.createElement('div');
        wrapper.className = 'form-group';

        const label = document.createElement('label');
        // 翻译标签：优先使用 label_{key} 格式的翻译键
        let labelText = t(`label_${key}`);
        
        // 如果没找到翻译，尝试直接用 key
        if (labelText === `label_${key}`) {
            labelText = t(key);
        }
        
        // 如果还是没找到，显示格式化的键名（将下划线替换为空格，首字母大写）
        if (labelText === key) {
            labelText = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        }

        label.textContent = labelText;
        wrapper.appendChild(label);


        let input;
        if (typeof value === 'boolean') {
            // 使用下拉框而不是复选框
            input = document.createElement('select');
            const trueOption = document.createElement('option');
            trueOption.value = 'true';
            trueOption.textContent = t('True', '是');
            const falseOption = document.createElement('option');
            falseOption.value = 'false';
            falseOption.textContent = t('False', '否');
            input.appendChild(trueOption);
            input.appendChild(falseOption);
            input.value = value ? 'true' : 'false';
            wrapper.appendChild(input);
        } else if (typeof value === 'number') {
            input = document.createElement('input');
            input.type = 'number';
            input.value = value;
            input.step = Number.isInteger(value) ? '1' : '0.01';
            wrapper.appendChild(input);
        } else {
            // String, null, or Enum - check if we have options for this key
            const options = configOptions[key];
            
            // 特殊处理：font_path 和 high_quality_prompt_path 即使为空也显示下拉菜单
            const alwaysDropdown = (key === 'font_path' || key === 'high_quality_prompt_path');
            
            // 如果有选项列表，创建下拉框（即使当前值是null）
            if (options && Array.isArray(options) && (options.length > 0 || alwaysDropdown)) {
                // Create dropdown
                input = document.createElement('select');
                
                // 为字体和提示词添加实时刷新功能
                if (key === 'font_path' || key === 'high_quality_prompt_path') {
                    input.onfocus = async () => {
                        const currentValue = input.value;
                        try {
                            const res = await fetch('/config/options');
                            const newOptions = await res.json();
                            const optionsList = newOptions[key] || [];
                            
                            // 清空并重新填充
                            input.innerHTML = '';
                            
                            // 添加"不使用"选项
                            const emptyOption = document.createElement('option');
                            emptyOption.value = '';
                            emptyOption.textContent = '-- 不使用 --';
                            input.appendChild(emptyOption);
                            
                            optionsList.forEach(opt => {
                                const option = document.createElement('option');
                                option.value = opt;
                                option.textContent = opt;
                                input.appendChild(option);
                            });
                            
                            // 恢复之前的值
                            if (currentValue === '' || optionsList.includes(currentValue)) {
                                input.value = currentValue;
                            }
                        } catch (e) {
                            console.error('Failed to refresh options:', e);
                        }
                    };
                }
                
                // 为某些参数添加空选项
                if (key === 'font_path' || key === 'high_quality_prompt_path') {
                    const emptyOption = document.createElement('option');
                    emptyOption.value = '';
                    emptyOption.textContent = '-- 不使用 --';
                    input.appendChild(emptyOption);
                }
                
                // 对于 high_quality_prompt_path，跳过初始选项填充，等待 updatePromptSelects
                if (key === 'high_quality_prompt_path') {
                    // 不添加任何选项，updatePromptSelects 会填充
                } else {
                    // 排版模式的翻译映射
                    const layoutModeMap = {
                        'default': t('layout_mode_default'),
                        'smart_scaling': t('layout_mode_smart_scaling'),
                        'strict': t('layout_mode_strict'),
                        'fixed_font': t('layout_mode_fixed_font'),
                        'disable_all': t('layout_mode_disable_all'),
                        'balloon_fill': t('layout_mode_balloon_fill')
                    };
                    
                    options.forEach(opt => {
                        const option = document.createElement('option');
                        option.value = opt;
                        // 如果是排版模式，使用翻译
                        if (key === 'layout_mode' && layoutModeMap[opt]) {
                            option.textContent = layoutModeMap[opt];
                        } else if (key === 'translator') {
                            // 如果是翻译器，使用翻译
                            option.textContent = t(`translator_${opt}`, opt);
                        } else if (key === 'target_lang') {
                            // 如果是目标语言，使用翻译
                            option.textContent = t(`lang_${opt}`, opt);
                        } else {
                            option.textContent = opt;
                        }
                        if (opt === value) {
                            option.selected = true;
                        }
                        input.appendChild(option);
                    });
                }
                
                // 如果当前值是null或空，选择空选项
                if (!value) {
                    input.value = '';
                }
                
                wrapper.appendChild(input);
            } else {
                // Regular text input
                input = document.createElement('input');
                input.type = 'text';
                input.value = value || '';
                wrapper.appendChild(input);
            }
        }

        input.dataset.key = fullKey;
        input.className = input.type === 'checkbox' ? '' : 'full-width-select';

        return wrapper;
    };

    // Distribute to tabs
    // Basic: translator, cli (some)
    // Advanced: detector, inpainter, render, upscale, colorizer
    // Options: ocr, global

    const mapToContainer = (section) => {
        if (section === 'translator') return 'basic-left';
        if (section === 'cli') return 'basic-right';
        if (section === 'detector' || section === 'inpainter') return 'advanced-left';
        if (section === 'render' || section === 'upscale' || section === 'colorizer') return 'advanced-right';
        if (section === 'ocr') return 'options-left';
        return 'options-right'; // Global
    };

    for (const [section, content] of Object.entries(config)) {
        if (typeof content === 'object' && content !== null && !Array.isArray(content)) {
            const containerId = mapToContainer(section);
            const container = document.getElementById(containerId);
            if (container) {
                // Add section header?
                // const header = document.createElement('h4');
                // header.textContent = section;
                // container.appendChild(header);

                for (const [key, value] of Object.entries(content)) {
                    const el = createInput(key, value, section);
                    if (el) container.appendChild(el);
                }
            }
        } else {
            // Global settings
            const container = document.getElementById('options-right');
            const el = createInput(section, content, '');
            if (el) container.appendChild(el);
        }
    }

    // Note: populateDropdowns() will be called after all data is loaded in init()
}

function populateDropdowns() {
    // 翻译器选项（从服务器获取，带翻译）
    const translators = availableTranslators.map(trans => {
        const transKey = `translator_${trans}`;
        return {
            value: trans,
            label: t(transKey, trans.charAt(0).toUpperCase() + trans.slice(1))
        };
    });
    
    if (translators.length > 0) {
        replaceWithSelectTranslated('translator.translator', translators);
        
        // 监听翻译器变化，动态更新 API Keys
        const translatorSelect = document.querySelector('[data-key="translator.translator"]');
        if (translatorSelect) {
            translatorSelect.addEventListener('change', () => {
                updateEnvInputs(translatorSelect.value);
            });
            // 初始化时也更新一次
            updateEnvInputs(translatorSelect.value);
        }
    }

    // 目标语言选项（从服务器获取，带翻译）
    const langs = availableLanguages.map(lang => {
        const langKey = `lang_${lang}`;
        return {
            value: lang,
            label: t(langKey, lang)
        };
    });
    
    if (langs.length > 0) {
        replaceWithSelectTranslated('translator.target_lang', langs);
    }
    
    // 设置超分模型联动
    setupUpscalerDependency();
}

function setupUpscalerDependency() {
    // 监听超分模型变化
    const upscalerSelect = document.querySelector('[data-key="upscale.upscaler"]');
    const upscaleRatioSelect = document.querySelector('[data-key="upscale.upscale_ratio"]');
    
    if (!upscalerSelect || !upscaleRatioSelect) return;
    
    upscalerSelect.addEventListener('change', () => {
        updateUpscaleRatioOptions(upscalerSelect.value, upscaleRatioSelect);
    });
    
    // 初始化时也更新一次
    updateUpscaleRatioOptions(upscalerSelect.value, upscaleRatioSelect);
}

function updateUpscaleRatioOptions(upscaler, ratioSelect) {
    if (!ratioSelect) return;
    
    const currentValue = ratioSelect.value;
    ratioSelect.innerHTML = '';
    
    if (upscaler === 'realcugan') {
        // 显示 Real-CUGAN 模型列表
        const realcuganModels = configOptions['realcugan_model'] || [];
        const options = ['不使用', ...realcuganModels];
        
        options.forEach(opt => {
            const option = document.createElement('option');
            option.value = opt;
            option.textContent = opt;
            ratioSelect.appendChild(option);
        });
        
        // 尝试恢复之前的值
        if (realcuganModels.includes(currentValue)) {
            ratioSelect.value = currentValue;
        } else {
            ratioSelect.value = '不使用';
        }
    } else {
        // 显示普通倍率选项
        const options = ['不使用', '2', '3', '4'];
        
        options.forEach(opt => {
            const option = document.createElement('option');
            option.value = opt;
            option.textContent = opt;
            ratioSelect.appendChild(option);
        });
        
        // 尝试恢复之前的值
        if (options.includes(currentValue)) {
            ratioSelect.value = currentValue;
        } else {
            ratioSelect.value = '不使用';
        }
    }
}

function replaceWithSelect(fullKey, options) {
    const input = document.querySelector(`input[data-key="${fullKey}"]`);
    if (!input) return;

    const select = document.createElement('select');
    select.className = 'full-width-select';
    select.dataset.key = fullKey;

    options.forEach(opt => {
        const option = document.createElement('option');
        option.value = opt;
        option.textContent = opt;
        if (opt === input.value) option.selected = true;
        select.appendChild(option);
    });

    input.parentNode.replaceChild(select, input);
}

function replaceWithSelectTranslated(fullKey, options) {
    const input = document.querySelector(`input[data-key="${fullKey}"]`);
    if (!input) return;

    const select = document.createElement('select');
    select.className = 'full-width-select';
    select.dataset.key = fullKey;

    options.forEach(opt => {
        const option = document.createElement('option');
        option.value = opt.value;
        option.textContent = opt.label;
        if (opt.value === input.value) option.selected = true;
        select.appendChild(option);
    });

    input.parentNode.replaceChild(select, input);
}

function updateFontSelects(fonts) {
    // Find font_path input and replace/update
    const input = document.querySelector(`input[data-key="render.font_path"]`);
    if (input) {
        const select = document.createElement('select');
        select.className = 'full-width-select';
        select.dataset.key = 'render.font_path';

        const defaultOpt = document.createElement('option');
        defaultOpt.value = '';
        defaultOpt.textContent = 'Default';
        select.appendChild(defaultOpt);

        fonts.forEach(f => {
            const option = document.createElement('option');
            option.value = f;
            option.textContent = f;
            if (f === input.value) option.selected = true;
            select.appendChild(option);
        });

        input.parentNode.replaceChild(select, input);
    }
}

function updatePromptSelects(prompts) {
    // 查找 high_quality_prompt_path 元素（可能是 input 或 select）
    let targetElement = document.querySelector(`select[data-key="translator.high_quality_prompt_path"]`);
    if (!targetElement) {
        targetElement = document.querySelector(`input[data-key="translator.high_quality_prompt_path"]`);
    }
    
    if (targetElement) {
        const currentValue = targetElement.value;
        
        // 如果已经是 select，直接更新选项
        if (targetElement.tagName === 'SELECT') {
            targetElement.innerHTML = '';
            
            const defaultOpt = document.createElement('option');
            defaultOpt.value = '';
            defaultOpt.textContent = '-- 不使用 --';
            targetElement.appendChild(defaultOpt);
            
            prompts.forEach(p => {
                const option = document.createElement('option');
                option.value = p;
                option.textContent = p;
                if (p === currentValue) option.selected = true;
                targetElement.appendChild(option);
            });
        } else {
            // 如果是 input，替换为 select
            const select = document.createElement('select');
            select.className = 'full-width-select';
            select.dataset.key = 'translator.high_quality_prompt_path';

            const defaultOpt = document.createElement('option');
            defaultOpt.value = '';
            defaultOpt.textContent = '-- 不使用 --';
            select.appendChild(defaultOpt);

            prompts.forEach(p => {
                const option = document.createElement('option');
                option.value = p;
                option.textContent = p;
                if (p === currentValue) option.selected = true;
                select.appendChild(option);
            });

            targetElement.parentNode.replaceChild(select, targetElement);
        }
    }
}

// --- API Keys / Env Editor ---
let currentEnvVars = {};

async function updateEnvInputs(translator) {
    console.log('updateEnvInputs called with translator:', translator);
    console.log('userSettings.show_env_editor:', userSettings.show_env_editor);
    
    const container = document.getElementById('env-inputs-container');
    if (!container) {
        console.warn('env-inputs-container not found');
        return;
    }
    
    // 清空现有输入框
    container.innerHTML = '';
    
    if (!translator) {
        console.log('No translator selected');
        return;
    }
    
    if (!userSettings.show_env_editor) {
        console.log('API Keys editor is hidden by admin settings');
        return;
    }
    
    try {
        // 获取翻译器配置
        const res = await fetch(`/translator-config/${translator}`);
        const config = await res.json();
        
        const allVars = [...(config.required_env_vars || []), ...(config.optional_env_vars || [])];
        
        if (allVars.length === 0) {
            container.innerHTML = `<p class="env-hint">${t('translator_no_api_keys', '此翻译器不需要 API 密钥')}</p>`;
            return;
        }
        
        // 从 localStorage 恢复用户保存的 API keys
        let savedEnvVars = {};
        try {
            const saved = localStorage.getItem('user_env_vars');
            if (saved) {
                savedEnvVars = JSON.parse(saved);
                // 同时更新 currentEnvVars
                currentEnvVars = {...savedEnvVars};
            }
        } catch (e) {
            console.error('Failed to load from localStorage:', e);
        }
        
        // 根据设置决定是否加载服务器的环境变量值
        let serverEnvVars = {};
        if (userSettings.allow_server_keys) {
            const envRes = await fetch('/env');
            serverEnvVars = await envRes.json();
        }
        
        // 为每个环境变量创建输入框
        allVars.forEach(varName => {
            const wrapper = document.createElement('div');
            wrapper.className = 'form-group';
            
            const label = document.createElement('label');
            label.textContent = t(`label_${varName}`, varName);
            wrapper.appendChild(label);
            
            const input = document.createElement('input');
            input.type = 'text';
            input.className = 'full-width-select';
            // 优先级：用户保存的值 > 服务器的值 > 空
            input.value = savedEnvVars[varName] || serverEnvVars[varName] || '';
            input.placeholder = userSettings.allow_server_keys ? 
                t(`placeholder_${varName}`, '') : 
                t('enter_your_api_key', '请输入您的 API 密钥');
            input.dataset.envKey = varName;
            
            // 标记为已修改
            input.addEventListener('input', () => {
                input.dataset.modified = 'true';
            });
            
            wrapper.appendChild(input);
            container.appendChild(wrapper);
        });
        
        // 添加保存按钮
        const buttonWrapper = document.createElement('div');
        buttonWrapper.style.marginTop = '20px';
        buttonWrapper.style.textAlign = 'center';
        
        const saveBtn = document.createElement('button');
        saveBtn.className = 'primary-btn';
        saveBtn.textContent = t('save_api_keys', '保存 API 密钥');
        saveBtn.onclick = async () => {
            await saveAllEnvVars();
        };
        buttonWrapper.appendChild(saveBtn);
        
        container.appendChild(buttonWrapper);
        
        // 添加提示信息
        const hintWrapper = document.createElement('div');
        hintWrapper.style.marginTop = '10px';
        hintWrapper.style.fontSize = '12px';
        hintWrapper.style.color = '#666';
        hintWrapper.style.textAlign = 'center';
        
        const policy = await fetch('/api-key-policy').then(r => r.json());
        if (policy.save_user_keys_to_server) {
            hintWrapper.textContent = t('api_keys_will_be_saved', 'API 密钥将保存到服务器');
        } else {
            hintWrapper.textContent = t('api_keys_session_only', 'API 密钥仅在本次会话中使用，不会保存到服务器');
        }
        container.appendChild(hintWrapper);
        
    } catch (e) {
        console.error('Error loading translator config:', e);
        container.innerHTML = `<p class="env-hint" style="color: #f44336;">${t('error_loading_translator_config', '加载翻译器配置失败')}</p>`;
    }
}

async function saveAllEnvVars() {
    const container = document.getElementById('env-inputs-container');
    if (!container) return;
    
    const inputs = container.querySelectorAll('input[data-env-key]');
    const envVars = {};
    
    inputs.forEach(input => {
        const key = input.dataset.envKey;
        const value = input.value.trim();
        if (value) {
            envVars[key] = value;
            currentEnvVars[key] = value;
        }
    });
    
    if (Object.keys(envVars).length === 0) {
        log(t('no_api_keys_to_save', '没有要保存的 API 密钥'), 'warning');
        return;
    }
    
    // 保存到 localStorage，页面刷新后不会丢失
    try {
        localStorage.setItem('user_env_vars', JSON.stringify(envVars));
    } catch (e) {
        console.error('Failed to save to localStorage:', e);
    }
    
    try {
        const result = await fetch('/env', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(envVars)
        });
        
        if (!result.ok) {
            throw new Error(`HTTP ${result.status}`);
        }
        
        const data = await result.json();
        
        if (data.saved_to_server) {
            log(t('api_keys_saved_to_server', 'API 密钥已保存到服务器'), 'info');
        } else {
            log(t('api_keys_saved_session', 'API 密钥已保存（仅本次会话）'), 'info');
        }
        
        // 清除修改标记
        inputs.forEach(input => {
            delete input.dataset.modified;
        });
    } catch (e) {
        console.error('Error saving env vars:', e);
        log(t('api_keys_save_failed', 'API 密钥保存失败') + ': ' + e.message, 'error');
    }
}

async function saveEnvVar(key, value) {
    // 这个函数现在只用于更新内存中的值
    currentEnvVars[key] = value;
}

// 旧的自动保存函数（已废弃，保留以防其他地方调用）
async function _oldSaveEnvVar(key, value) {
    // 更新内存中的值（用于本次翻译）
    currentEnvVars[key] = value;
    
    // 根据管理员设置决定是否保存到服务器
    // 注意：多用户场景下建议关闭 save_user_keys_to_server，避免互相覆盖
    try {
        const result = await fetch('/env', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ [key]: value })
        });
        const data = await result.json();
        
        if (data.saved_to_server) {
            log(`${t('env_var_saved', 'API密钥已保存')}: ${key}`, 'info');
        } else {
            // 只在本次翻译使用，不保存到服务器
            console.log(`${key} will be used for this translation only`);
        }
    } catch (e) {
        console.error('Error saving env var:', e);
        log(`${t('env_var_save_failed', 'API密钥保存失败')}: ${key}`, 'error');
    }
}

function collectConfig() {
    const config = JSON.parse(JSON.stringify(configSchema)); // Deep copy

    document.querySelectorAll('[data-key]').forEach(el => {
        const keys = el.dataset.key.split('.');
        let target = config;
        for (let i = 0; i < keys.length - 1; i++) {
            target = target[keys[i]];
        }
        const lastKey = keys[keys.length - 1];

        if (el.type === 'checkbox') {
            target[lastKey] = el.checked;
        } else if (el.type === 'number') {
            // 处理数字类型：空字符串转为 null
            const numValue = el.value.trim();
            target[lastKey] = numValue === '' ? null : parseFloat(numValue);
        } else if (el.tagName === 'SELECT' && (el.value === 'true' || el.value === 'false')) {
            // 布尔值下拉框
            target[lastKey] = el.value === 'true';
        } else {
            // 字符串类型：空字符串转为 null
            target[lastKey] = el.value.trim() === '' ? null : el.value;
        }
    });

    // 处理超分模型和倍率的关系
    const upscalerSelect = document.querySelector('[data-key="upscale.upscaler"]');
    const upscaleRatioSelect = document.querySelector('[data-key="upscale.upscale_ratio"]');
    
    if (upscalerSelect && upscaleRatioSelect && config.upscale) {
        if (upscalerSelect.value === 'realcugan') {
            // 如果选择了 realcugan，upscale_ratio 的值实际上是 realcugan_model
            const ratioValue = upscaleRatioSelect.value;
            if (ratioValue === '不使用') {
                config.upscale.upscale_ratio = null;
                config.upscale.realcugan_model = null;
            } else {
                config.upscale.realcugan_model = ratioValue;
                config.upscale.upscale_ratio = null; // realcugan 不使用普通倍率
            }
        } else {
            // 其他超分模型，使用普通倍率
            const ratioValue = upscaleRatioSelect.value;
            if (ratioValue === '不使用') {
                config.upscale.upscale_ratio = null;
            } else {
                config.upscale.upscale_ratio = parseInt(ratioValue);
            }
            config.upscale.realcugan_model = null;
        }
    }

    return config;
}

// --- File Handling ---
let translationFiles = {}; // 存储翻译文件 {imageName: textFile}

// 检查上传限制的共享函数
function checkUploadLimits(imageFiles, currentFileCount) {
    const maxImageSizeMB = userSettings.max_image_size_mb || 0;
    const maxImagesPerBatch = userSettings.max_images_per_batch || 0;
    
    console.log(`[Upload Limits] Max size: ${maxImageSizeMB}MB, Max count: ${maxImagesPerBatch}, Current: ${currentFileCount}, Adding: ${imageFiles.length}`);
    
    // 检查数量限制
    if (maxImagesPerBatch > 0 && currentFileCount + imageFiles.length > maxImagesPerBatch) {
        const msg = currentLocale.startsWith('zh') 
            ? `超过最大上传数量限制（${maxImagesPerBatch}张），当前已有${currentFileCount}张，尝试添加${imageFiles.length}张`
            : `Exceeds max upload limit (${maxImagesPerBatch}), current: ${currentFileCount}, trying to add: ${imageFiles.length}`;
        log(msg, 'error');
        alert(msg);
        return false;
    }
    
    // 检查文件大小限制
    if (maxImageSizeMB > 0) {
        const maxSizeBytes = maxImageSizeMB * 1024 * 1024;
        console.log(`[Upload Limits] Max size in bytes: ${maxSizeBytes}`);
        
        const oversizedFiles = [];
        imageFiles.forEach(f => {
            const sizeMB = (f.size / 1024 / 1024).toFixed(2);
            console.log(`[Upload Limits] Checking file: ${f.name}, Size: ${f.size} bytes (${sizeMB}MB)`);
            if (f.size > maxSizeBytes) {
                oversizedFiles.push(f);
            }
        });
        
        if (oversizedFiles.length > 0) {
            const msg = currentLocale.startsWith('zh')
                ? `以下文件超过大小限制（${maxImageSizeMB}MB）：\n${oversizedFiles.map(f => `${f.name} (${(f.size / 1024 / 1024).toFixed(2)}MB)`).join('\n')}`
                : `Files exceed size limit (${maxImageSizeMB}MB):\n${oversizedFiles.map(f => `${f.name} (${(f.size / 1024 / 1024).toFixed(2)}MB)`).join('\n')}`;
            log(msg, 'error');
            alert(msg);
            return false;
        }
    }
    
    return true;
}

function handleFileSelect(e) {
    const files = Array.from(e.target.files);
    
    // 分离图片文件和文本文件
    const imageFiles = files.filter(f => f.type.startsWith('image/'));
    const textFiles = files.filter(f => 
        f.name.endsWith('.json') || 
        f.name.endsWith('_original.txt') || 
        f.name.endsWith('_translated.txt')
    );
    
    // 检查上传限制
    if (!checkUploadLimits(imageFiles, fileList.length)) {
        e.target.value = '';
        return;
    }
    
    // 添加图片文件
    imageFiles.forEach(file => {
        fileList.push(file);
        addFileToUI(file);
    });
    
    // 处理文本文件，建立与图片的关联
    textFiles.forEach(textFile => {
        // 提取基础文件名（去掉 _original.txt, _translated.txt, .json 等后缀）
        let baseName = textFile.name
            .replace(/_original\.txt$/, '')
            .replace(/_translated\.txt$/, '')
            .replace(/\.json$/, '');
        
        // 查找匹配的图片
        const matchedImage = fileList.find(img => {
            const imgBaseName = img.name.replace(/\.[^.]+$/, ''); // 去掉扩展名
            return imgBaseName === baseName;
        });
        
        if (matchedImage) {
            translationFiles[matchedImage.name] = textFile;
            log(`${t('translation_file_matched', '翻译文件已匹配')}: ${textFile.name} -> ${matchedImage.name}`, 'info');
        } else {
            log(`${t('translation_file_no_match', '未找到匹配的图片')}: ${textFile.name}`, 'warning');
        }
    });
    
    updateFileCount();
    e.target.value = ''; // Reset
}

function handleFolderSelect(e) {
    const files = Array.from(e.target.files);
    
    // 分离图片文件和文本文件
    const imageFiles = files.filter(f => f.type.startsWith('image/'));
    const textFiles = files.filter(f => 
        f.name.endsWith('.json') || 
        f.name.endsWith('_original.txt') || 
        f.name.endsWith('_translated.txt')
    );
    
    log(`${t('folder_scan_result', '从文件夹中找到')}: ${imageFiles.length} ${t('images', '个图片')}, ${textFiles.length} ${t('translation_files', '个翻译文件')}`);
    
    // 检查上传限制
    if (!checkUploadLimits(imageFiles, fileList.length)) {
        e.target.value = '';
        return;
    }
    
    // 添加图片文件
    imageFiles.forEach(file => {
        fileList.push(file);
        addFileToUI(file);
    });
    
    // 处理文本文件
    textFiles.forEach(textFile => {
        let baseName = textFile.name
            .replace(/_original\.txt$/, '')
            .replace(/_translated\.txt$/, '')
            .replace(/\.json$/, '');
        
        const matchedImage = fileList.find(img => {
            const imgBaseName = img.name.replace(/\.[^.]+$/, '');
            return imgBaseName === baseName;
        });
        
        if (matchedImage) {
            translationFiles[matchedImage.name] = textFile;
        }
    });
    
    updateFileCount();
    e.target.value = ''; // Reset
}

function updateFileCount() {
    if (els.fileCount) {
        els.fileCount.textContent = `${fileList.length} 个文件`;
    }
}

function addFileToUI(file) {
    const li = document.createElement('li');
    li.innerHTML = `
        <span>${file.name} <small>(${formatSize(file.size)})</small></span>
        <span class="remove-btn" onclick="removeFile('${file.name}')">✖</span>
    `;
    els.fileList.appendChild(li);
}

function removeFile(name) {
    const idx = fileList.findIndex(f => f.name === name);
    if (idx !== -1) {
        fileList.splice(idx, 1);
        renderFileList();
        updateFileCount();
    }
}

function renderFileList() {
    els.fileList.innerHTML = '';
    fileList.forEach(addFileToUI);
    updateFileCount();
}

function clearFileList() {
    fileList = [];
    renderFileList();
    updateFileCount();
}

function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// --- Task Execution ---

async function startTask() {
    if (fileList.length === 0) {
        const msg = currentLocale.startsWith('zh') ? '请先添加要翻译的图片文件！' : 'Please add image files to translate!';
        log(msg, 'error');
        return;
    }

    const mode = els.workflowMode.value;
    const config = collectConfig();
    const batchSize = parseInt(config.cli?.batch_size) || 5;

    els.startBtn.disabled = true;
    const startMsg = currentLocale.startsWith('zh') ? '开始任务' : 'Task started';
    log(`${startMsg}: ${mode} - ${fileList.length} 个文件`);

    try {
        // 对于普通翻译模式，如果有多个文件，使用批量接口
        if (mode === 'normal' && fileList.length > 1) {
            // 按批量大小分批处理
            for (let i = 0; i < fileList.length; i += batchSize) {
                const batch = fileList.slice(i, i + batchSize);
                const batchNum = Math.floor(i / batchSize) + 1;
                const totalBatches = Math.ceil(fileList.length / batchSize);
                log(`${currentLocale.startsWith('zh') ? '批次' : 'Batch'} ${batchNum}/${totalBatches}: ${batch.length} ${currentLocale.startsWith('zh') ? '个文件' : 'files'}`, 'info');
                await processBatch(batch, config);
            }
        } else {
            // 其他模式或单个文件，逐个处理
            for (let i = 0; i < fileList.length; i++) {
                const file = fileList[i];
                const processingMsg = currentLocale.startsWith('zh') ? '正在处理' : 'Processing';
                log(`${processingMsg} [${i + 1}/${fileList.length}]: ${file.name}...`);
                await processFile(file, mode, config);
            }
        }
        
        const completeMsg = currentLocale.startsWith('zh') ? '所有任务完成！' : 'All tasks completed!';
        log(completeMsg, 'info');
    } catch (e) {
        const errorMsg = currentLocale.startsWith('zh') ? '任务出错' : 'Task error';
        log(`${errorMsg}: ${e.message}`, 'error');
    } finally {
        els.startBtn.disabled = false;
    }
}

async function processBatch(files, config) {
    const batchMsg = currentLocale.startsWith('zh') ? '批量翻译中' : 'Batch translating';
    log(`${batchMsg}: ${files.length} 个文件...`, 'info');
    
    try {
        // 将文件转换为 data URI 格式（包含前缀）
        const images = await Promise.all(files.map(async file => {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => {
                    // 保留完整的 data URI（包括 data:image/...;base64, 前缀）
                    resolve(reader.result);
                };
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
        }));
        
        // 调用批量翻译接口
        const batchSize = parseInt(config.cli?.batch_size) || 5;
        const response = await fetch('/translate/batch/images', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                images: images,
                config: config,
                batch_size: Math.min(batchSize, files.length)
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        // 获取返回的 ZIP 文件
        const blob = await response.blob();
        
        // 解压并显示每张图片（不自动下载ZIP）
        try {
            if (typeof JSZip !== 'undefined') {
                const zip = new JSZip();
                const zipContent = await zip.loadAsync(blob);
                
                // 遍历 ZIP 中的所有文件
                const imageFiles = Object.keys(zipContent.files).filter(name => 
                    name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg')
                );
                
                for (const filename of imageFiles) {
                    const imageBlob = await zipContent.files[filename].async('blob');
                    const imageUrl = URL.createObjectURL(imageBlob);
                    addResult(filename, imageUrl, 'image');
                }
                
                log(`${currentLocale.startsWith('zh') ? '批量翻译完成，已添加' : 'Batch completed, added'} ${imageFiles.length} ${currentLocale.startsWith('zh') ? '张图片到结果列表' : 'images to results'}`, 'info');
            } else {
                // 如果没有 JSZip，提示用户手动下载
                log(`${currentLocale.startsWith('zh') ? '无法解压ZIP文件，请手动下载' : 'Cannot extract ZIP, please download manually'}`, 'warning');
                const zipFilename = `batch_translated_${Date.now()}.zip`;
                downloadBlob(blob, zipFilename);
            }
        } catch (e) {
            console.error('Failed to extract zip:', e);
            log(`${currentLocale.startsWith('zh') ? '解压失败，自动下载ZIP文件' : 'Extraction failed, downloading ZIP'}`, 'warning');
            const zipFilename = `batch_translated_${Date.now()}.zip`;
            downloadBlob(blob, zipFilename);
        }
        
        log(`${currentLocale.startsWith('zh') ? '批量翻译完成' : 'Batch translation completed'}`, 'info');
    } catch (e) {
        console.error('Batch translation failed:', e);
        log(`${currentLocale.startsWith('zh') ? '批量翻译失败，切换到逐个处理' : 'Batch failed, processing individually'}`, 'warning');
        
        // 回退到逐个处理
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const processingMsg = currentLocale.startsWith('zh') ? '正在处理' : 'Processing';
            log(`${processingMsg} [${i + 1}/${files.length}]: ${file.name}...`);
            await processFile(file, 'normal', config);
        }
    }
}

async function processFile(file, mode, config) {
    const formData = new FormData();
    formData.append('image', file);
    formData.append('config', JSON.stringify(config));
    
    // 如果用户输入了 API Keys，发送给服务器
    if (currentEnvVars && Object.keys(currentEnvVars).length > 0) {
        formData.append('user_env_vars', JSON.stringify(currentEnvVars));
    }

    // Determine endpoint based on mode
    let endpoint = '/translate/with-form/image/stream'; // Default normal

    if (mode === 'export_trans') endpoint = '/translate/export/translated';
    else if (mode === 'export_raw') endpoint = '/translate/export/original';
    else if (mode === 'import_trans') {
        // 导入翻译并渲染：必须上传图片+JSON文件
        const translationFile = translationFiles[file.name];
        
        if (!translationFile) {
            log(`${t('import_mode_no_json', '导入翻译模式：未找到JSON文件')}: ${file.name}`, 'error');
            log(`${t('import_mode_hint', '提示：请同时上传图片和对应的JSON文件（例如：image.png 和 image.json）')}`, 'warning');
            return;
        }
        
        if (!translationFile.name.endsWith('.json')) {
            log(`${t('import_mode_json_only', '导入翻译模式：只支持JSON文件，不支持TXT文件')}: ${translationFile.name}`, 'error');
            log(`${t('import_mode_json_hint', '提示：请使用"导出原文"或"导出翻译"功能生成JSON文件')}`, 'warning');
            return;
        }
        
        endpoint = '/translate/import/json';
        formData.append('json_file', translationFile);
        log(`${t('using_translation_file', '使用翻译文件')}: ${translationFile.name}`, 'info');
    }
    else if (mode === 'colorize') endpoint = '/translate/colorize';
    else if (mode === 'upscale') endpoint = '/translate/upscale';
    else if (mode === 'inpaint') endpoint = '/translate/inpaint';

    // Special handling for stream endpoints
    if (endpoint.includes('stream') && !endpoint.includes('export')) {
        await processStream(endpoint, formData, file.name);
    } else {
        // Standard download endpoints
        const res = await fetch(endpoint, {
            method: 'POST',
            body: formData
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const blob = await res.blob();
        const resultFilename = getDownloadName(file.name, mode);
        
        // 添加到结果列表（不自动下载）
        const resultUrl = URL.createObjectURL(blob);
        const resultType = resultFilename.endsWith('.zip') ? 'zip' : 'image';
        addResult(resultFilename, resultUrl, resultType);
        
        log(`${file.name} 处理完成`, 'info');
    }
}

async function processStream(endpoint, formData, filename) {
    const res = await fetch(endpoint, {
        method: 'POST',
        body: formData
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.getReader();
    let resultChunks = [];
    let pendingBuffer = new Uint8Array(0);

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            // 合并之前的不完整数据和新数据
            let buffer = new Uint8Array(pendingBuffer.length + value.length);
            buffer.set(pendingBuffer);
            buffer.set(value, pendingBuffer.length);
            pendingBuffer = new Uint8Array(0);

            // Parse custom stream format: 1 byte status, 4 bytes len, data
            let offset = 0;
            while (offset < buffer.length) {
                if (buffer.length - offset < 5) {
                    pendingBuffer = buffer.slice(offset);
                    break;
                }

                const status = buffer[offset];
                const len = (buffer[offset + 1] << 24) | (buffer[offset + 2] << 16) | (buffer[offset + 3] << 8) | buffer[offset + 4];

                if (buffer.length - offset < 5 + len) {
                    pendingBuffer = buffer.slice(offset);
                    break;
                }

                const data = buffer.slice(offset + 5, offset + 5 + len);
                offset += 5 + len;

                if (status === 0) { // Result Data
                    resultChunks.push(data);
                } else if (status === 1) { // Progress
                    try {
                        const msg = JSON.parse(new TextDecoder().decode(data));
                        // 保存 task_id 用于日志过滤
                        if (msg.task_id && msg.stage === 'task_id') {
                            currentTaskId = msg.task_id;
                            log(`开始任务: ${msg.task_id.substring(0, 8)}...`, 'info');
                        }
                        if (msg.message) log(`${msg.message}`);
                    } catch (e) {
                        console.error('Failed to parse progress message:', e);
                    }
                } else if (status === 2) { // Error
                    try {
                        const msg = JSON.parse(new TextDecoder().decode(data));
                        log(`错误: ${msg.error}`, 'error');
                        throw new Error(msg.error);
                    } catch (e) {
                        throw new Error('Translation failed');
                    }
                }
            }
        }

        if (resultChunks.length > 0) {
            const blob = new Blob(resultChunks, { type: 'image/png' });
            const resultFilename = `translated_${filename}`;
            
            // 添加到结果列表（不自动下载）
            const imageUrl = URL.createObjectURL(blob);
            addResult(resultFilename, imageUrl, 'image');
            
            log(`${filename} 翻译完成`, 'info');
        } else {
            log(`${filename} 未收到结果数据`, 'error');
        }
    } catch (error) {
        console.error('Stream processing error:', error);
        log(`${filename} 处理失败: ${error.message}`, 'error');
        throw error;
    } finally {
        // 任务完成或失败后，清除 task_id 和时间戳
        currentTaskId = null;
        lastLogTimestamp = null; // 重置时间戳，下次任务从头开始
    }
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    // 不立即释放 URL，因为结果列表需要使用它
    // URL 会在清空结果或删除单个结果时释放
}

function getDownloadName(original, mode) {
    const base = original.split('.')[0];
    if (mode === 'export_trans') return `${base}_translated.zip`;
    if (mode === 'export_raw') return `${base}_original.zip`;
    return `result_${original}`;
}

// --- Utils ---

function switchTab(tabId) {
    els.tabs.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    els.tabPanes.forEach(pane => {
        pane.classList.toggle('active', pane.id === tabId);
    });
}

// --- Log Handling ---

let lastLogTimestamp = null;
let currentTaskId = null; // 当前正在处理的任务ID

function startLogPolling() {
    setInterval(async () => {
        try {
            // 只有在有当前任务时才轮询日志
            if (!currentTaskId) {
                return; // 没有任务，不轮询
            }
            
            // 获取当前任务的日志
            const url = `/logs?limit=50&task_id=${currentTaskId}`;
            const res = await fetch(url);
            const logs = await res.json();

            if (logs.length > 0) {
                // Filter new logs
                const newLogs = lastLogTimestamp
                    ? logs.filter(l => new Date(l.timestamp) > new Date(lastLogTimestamp))
                    : logs;

                if (newLogs.length > 0) {
                    newLogs.forEach(l => {
                        // Avoid duplicates if possible, though timestamp check helps
                        log(`[${l.level}] ${l.message}`, l.level.toLowerCase(), false);
                    });
                    lastLogTimestamp = newLogs[newLogs.length - 1].timestamp;
                }
            }
        } catch (e) {
            // console.error("Log poll failed", e);
        }
    }, 2000); // Poll every 2s
}

function log(msg, type = 'normal', isLocal = true) {
    // If local log (from script), just append.
    // If remote log (from polling), append.
    // We might want to distinguish them visually?

    const div = document.createElement('div');
    div.className = `log-entry ${type}`;

    // If msg already has timestamp (from remote), use it? 
    // Or just use current time for local.
    const timeStr = isLocal ? new Date().toLocaleTimeString() : '';
    div.textContent = isLocal ? `[${timeStr}] ${msg}` : msg;

    els.logBox.appendChild(div);
    els.logBox.scrollTop = els.logBox.scrollHeight;
}

function exportConfig() {
    const config = collectConfig();
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
    downloadBlob(blob, 'config.json');
}

function importConfig() {
    const file = els.configInput.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            const config = JSON.parse(e.target.result);
            // Update UI
            // This requires mapping back to inputs. 
            // Simplified: just reload page or re-generate UI?
            // Re-generating UI is better.
            els.logBox.innerHTML = '';
            document.getElementById('basic-left').innerHTML = '';
            document.getElementById('basic-right').innerHTML = '';
            document.getElementById('advanced-left').innerHTML = '';
            document.getElementById('advanced-right').innerHTML = '';
            document.getElementById('options-left').innerHTML = '';
            document.getElementById('options-right').innerHTML = '';

            configSchema = config; // Update schema with values
            generateConfigUI(config);
            log('配置已导入', 'info');
        } catch (err) {
            log('导入配置失败', 'error');
        }
    };
    reader.readAsText(file);
    els.configInput.value = '';
}


// --- Upload Handlers ---

async function handleFontUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const res = await fetch('/upload/font', {
            method: 'POST',
            body: formData
        });
        
        if (res.ok) {
            log(`${t('font_uploaded', '字体上传成功')}: ${file.name}`, 'info');
            // 重新加载字体列表
            await loadFonts();
        } else {
            const error = await res.text();
            log(`${t('font_upload_failed', '字体上传失败')}: ${error}`, 'error');
        }
    } catch (error) {
        log(`${t('font_upload_error', '字体上传错误')}: ${error.message}`, 'error');
    }
    
    e.target.value = ''; // Reset
}

async function handlePromptUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const res = await fetch('/upload/prompt', {
            method: 'POST',
            body: formData
        });
        
        if (res.ok) {
            log(`${t('prompt_uploaded', '提示词上传成功')}: ${file.name}`, 'info');
            // 重新加载提示词列表
            await loadPrompts();
        } else {
            const error = await res.text();
            log(`${t('prompt_upload_failed', '提示词上传失败')}: ${error}`, 'error');
        }
    } catch (error) {
        log(`${t('prompt_upload_error', '提示词上传错误')}: ${error.message}`, 'error');
    }
    
    e.target.value = ''; // Reset
}


// --- Results Management ---
let resultsList = [];

function loadResults() {
    try {
        const saved = localStorage.getItem('translationResults');
        if (saved) {
            resultsList = JSON.parse(saved);
            renderResults();
        }
    } catch (e) {
        console.error('Error loading results:', e);
        resultsList = [];
    }
}

function saveResults() {
    try {
        localStorage.setItem('translationResults', JSON.stringify(resultsList));
    } catch (e) {
        console.error('Error saving results:', e);
    }
}

function addResult(filename, imageData, type = 'image') {
    const result = {
        id: Date.now() + Math.random(),
        filename,
        imageData,
        type,
        timestamp: new Date().toISOString()
    };
    resultsList.push(result);
    saveResults();
    renderResults();
}

function renderResults() {
    const container = document.getElementById('results-list');
    const emptyHint = document.getElementById('results-empty');
    const expandResultsBtn = document.getElementById('expand-results-btn');
    const downloadAllBtn = document.getElementById('download-all-btn');
    const clearResultsBtn = document.getElementById('clear-results-btn');
    
    if (!container) return;
    
    if (resultsList.length === 0) {
        container.innerHTML = '';
        emptyHint.style.display = 'block';
        if (expandResultsBtn) expandResultsBtn.style.display = 'none';
        downloadAllBtn.style.display = 'none';
        clearResultsBtn.style.display = 'none';
        return;
    }
    
    emptyHint.style.display = 'none';
    
    // 只有当有图片类型的结果时才显示展开按钮
    const hasImages = resultsList.some(r => r.type === 'image');
    if (expandResultsBtn) expandResultsBtn.style.display = hasImages ? 'inline-block' : 'none';
    
    downloadAllBtn.style.display = 'inline-block';
    clearResultsBtn.style.display = 'inline-block';
    
    container.innerHTML = '';
    
    // 按时间倒序显示（最新的在前）
    const sortedResults = [...resultsList].reverse();
    
    sortedResults.forEach(result => {
        const li = document.createElement('li');
        li.className = 'result-item';
        
        const info = document.createElement('div');
        info.className = 'result-info';
        
        const icon = document.createElement('span');
        icon.className = 'result-icon';
        icon.textContent = result.type === 'zip' ? '📦' : '🖼️';
        
        const name = document.createElement('span');
        name.className = 'result-name';
        name.textContent = result.filename;
        name.title = result.filename;
        
        const time = document.createElement('span');
        time.className = 'result-time';
        time.textContent = formatTime(result.timestamp);
        
        info.appendChild(icon);
        info.appendChild(name);
        info.appendChild(time);
        
        const actions = document.createElement('div');
        actions.className = 'result-actions';
        
        // 查看按钮
        const viewBtn = document.createElement('button');
        viewBtn.className = 'result-btn';
        viewBtn.textContent = t('view', '查看');
        viewBtn.onclick = () => viewResult(result);
        
        // 下载按钮
        const downloadBtn = document.createElement('button');
        downloadBtn.className = 'result-btn';
        downloadBtn.textContent = t('download', '下载');
        downloadBtn.onclick = () => downloadResult(result);
        
        // 删除按钮
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'result-btn delete-btn';
        deleteBtn.textContent = '×';
        deleteBtn.title = t('delete', '删除');
        deleteBtn.onclick = () => deleteResult(result.id);
        
        actions.appendChild(viewBtn);
        actions.appendChild(downloadBtn);
        actions.appendChild(deleteBtn);
        
        li.appendChild(info);
        li.appendChild(actions);
        container.appendChild(li);
    });
}

function formatTime(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    // 小于1分钟
    if (diff < 60000) {
        return t('just_now', '刚刚');
    }
    
    // 小于1小时
    if (diff < 3600000) {
        const minutes = Math.floor(diff / 60000);
        return currentLocale.startsWith('zh') ? `${minutes}分钟前` : `${minutes}m ago`;
    }
    
    // 小于24小时
    if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return currentLocale.startsWith('zh') ? `${hours}小时前` : `${hours}h ago`;
    }
    
    // 显示日期时间
    return date.toLocaleString(currentLocale.replace('_', '-'));
}

function viewResult(result) {
    // 在新标签页打开
    window.open(result.imageData, '_blank');
}

function downloadResult(result) {
    const a = document.createElement('a');
    a.href = result.imageData;
    a.download = result.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

function deleteResult(id) {
    const result = resultsList.find(r => r.id === id);
    if (result && result.imageData && result.imageData.startsWith('blob:')) {
        URL.revokeObjectURL(result.imageData);
    }
    
    resultsList = resultsList.filter(r => r.id !== id);
    saveResults();
    renderResults();
}

async function downloadAllResults() {
    if (resultsList.length === 0) return;
    
    try {
        log(t('packing_results', '正在打包所有结果...'), 'info');
        
        // 动态导入 JSZip
        if (typeof JSZip === 'undefined') {
            // 如果没有加载 JSZip，使用简单的逐个下载
            for (const result of resultsList) {
                downloadResult(result);
                await new Promise(resolve => setTimeout(resolve, 500)); // 延迟避免浏览器阻止
            }
            log(t('download_complete', '下载完成'), 'info');
            return;
        }
        
        const zip = new JSZip();
        
        // 添加所有文件到 ZIP
        for (const result of resultsList) {
            try {
                const response = await fetch(result.imageData);
                const blob = await response.blob();
                zip.file(result.filename, blob);
            } catch (e) {
                console.error(`Failed to add ${result.filename} to zip:`, e);
            }
        }
        
        // 生成 ZIP 文件
        const zipBlob = await zip.generateAsync({ type: 'blob' });
        
        // 下载 ZIP
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
        const zipFilename = `translation_results_${timestamp}.zip`;
        
        const url = URL.createObjectURL(zipBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = zipFilename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        log(t('download_complete', '下载完成'), 'info');
    } catch (e) {
        console.error('Failed to pack results:', e);
        log(t('download_failed', '下载失败') + ': ' + e.message, 'error');
        
        // 回退到逐个下载
        for (const result of resultsList) {
            downloadResult(result);
            await new Promise(resolve => setTimeout(resolve, 500));
        }
    }
}

function clearResults() {
    if (confirm(t('confirm_clear_results', '确定要清空所有翻译结果吗？'))) {
        // 释放所有 blob URLs
        resultsList.forEach(result => {
            if (result.imageData && result.imageData.startsWith('blob:')) {
                URL.revokeObjectURL(result.imageData);
            }
        });
        
        resultsList = [];
        saveResults();
        renderResults();
        log(t('results_cleared', '翻译结果已清空'), 'info');
    }
}


// --- Image Viewer ---
let currentPreviewIndex = -1;

function openImageViewer() {
    const modal = document.getElementById('image-viewer-modal');
    modal.style.display = 'flex';
    renderThumbnails();
}

function closeImageViewer() {
    const modal = document.getElementById('image-viewer-modal');
    modal.style.display = 'none';
    currentPreviewIndex = -1;
}

function renderThumbnails() {
    const container = document.getElementById('thumbnails-container');
    container.innerHTML = '';
    
    // 只显示图片类型的结果
    const imageResults = resultsList.filter(r => r.type === 'image');
    
    if (imageResults.length === 0) {
        container.innerHTML = '<div style="padding: 20px; text-align: center; color: #999;">暂无图片</div>';
        return;
    }
    
    imageResults.forEach((result, index) => {
        const item = document.createElement('div');
        item.className = 'thumbnail-item';
        item.onclick = () => showPreview(index);
        
        const img = document.createElement('img');
        img.src = result.imageData;
        img.alt = result.filename;
        
        const icon = document.createElement('div');
        icon.className = 'thumbnail-icon';
        icon.textContent = '🖼️';
        
        const name = document.createElement('div');
        name.className = 'thumbnail-name';
        name.textContent = result.filename;
        name.title = result.filename;
        
        item.appendChild(img);
        item.appendChild(icon);
        item.appendChild(name);
        container.appendChild(item);
    });
    
    // 自动显示第一张图片
    if (imageResults.length > 0) {
        showPreview(0);
    }
}

function showPreview(index) {
    const imageResults = resultsList.filter(r => r.type === 'image');
    if (index < 0 || index >= imageResults.length) return;
    
    currentPreviewIndex = index;
    const result = imageResults[index];
    
    // 更新缩略图选中状态
    const thumbnails = document.querySelectorAll('.thumbnail-item');
    thumbnails.forEach((thumb, i) => {
        thumb.classList.toggle('active', i === index);
    });
    
    // 显示大图
    const previewContainer = document.getElementById('preview-container');
    previewContainer.innerHTML = '';
    
    const img = document.createElement('img');
    img.src = result.imageData;
    img.alt = result.filename;
    previewContainer.appendChild(img);
    
    // 更新文件名和下载按钮
    document.getElementById('preview-filename').textContent = result.filename;
    const downloadBtn = document.getElementById('preview-download-btn');
    downloadBtn.style.display = 'inline-block';
    downloadBtn.onclick = () => downloadResult(result);
}

// 键盘导航
document.addEventListener('keydown', (e) => {
    const modal = document.getElementById('image-viewer-modal');
    if (modal.style.display !== 'flex') return;
    
    const imageResults = resultsList.filter(r => r.type === 'image');
    
    if (e.key === 'ArrowLeft' && currentPreviewIndex > 0) {
        showPreview(currentPreviewIndex - 1);
    } else if (e.key === 'ArrowRight' && currentPreviewIndex < imageResults.length - 1) {
        showPreview(currentPreviewIndex + 1);
    } else if (e.key === 'Escape') {
        closeImageViewer();
    }
});

// 点击模态框背景关闭
document.getElementById('image-viewer-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'image-viewer-modal') {
        closeImageViewer();
    }
});
