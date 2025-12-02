let adminToken = null;
let i18nData = {};
let currentLocale = localStorage.getItem('locale') || 'zh_CN';

// i18n 功能
async function loadI18n(locale) {
    try {
        const res = await fetch(`/i18n/${locale}`);
        i18nData = await res.json();
        currentLocale = locale;
        localStorage.setItem('locale', locale);
        console.log(`Loaded i18n for ${locale}`);
        
        // 更新语言选择器
        const langSelect = document.getElementById('language-select');
        if (langSelect) {
            langSelect.value = locale;
        }
    } catch (e) {
        console.error('Failed to load i18n:', e);
    }
}

function changeLanguage(locale) {
    loadI18n(locale);
}

function t(key) {
    return i18nData[key] || key;
}

// Login
async function login() {
    const password = document.getElementById('admin-password').value;
    const formData = new FormData();
    formData.append('password', password);

    try {
        const res = await fetch('/admin/login', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();

        if (data.success) {
            adminToken = data.token;
            localStorage.setItem('adminToken', adminToken);
            document.getElementById('login-screen').style.display = 'none';
            document.getElementById('admin-panel').style.display = 'block';
            loadAdminData();
        } else {
            document.getElementById('login-error').textContent = '密码错误';
        }
    } catch (e) {
        document.getElementById('login-error').textContent = '登录失败：' + e.message;
    }
}

function logout() {
    adminToken = null;
    localStorage.removeItem('adminToken');
    document.getElementById('login-screen').style.display = 'flex';
    document.getElementById('admin-panel').style.display = 'none';
}

// Load admin data
async function loadAdminData() {
    await loadServerConfig();
    await loadPermissions();
    await loadUserAccess();
    await loadApiKeyPolicy();
    await loadServerApiKeys();
    await loadVisibleSettings();
    await loadAllTranslators();
    await loadAllLanguages();
    await loadAllWorkflows();
    await loadFonts();
    await loadPrompts();
    // 加载任务和日志
    await refreshTasks();
    await refreshLogs();
}

async function loadServerConfig() {
    try {
        const res = await fetch('/admin/server-config', {
            headers: { 'X-Admin-Token': adminToken }
        });
        const config = await res.json();
        document.getElementById('max-concurrent').value = config.max_concurrent_tasks || 3;
        
        // 显示配置文件路径
        if (config.admin_config_path) {
            document.getElementById('admin-config-path').textContent = config.admin_config_path;
            const statusEl = document.getElementById('config-status');
            if (config.admin_config_exists) {
                statusEl.innerHTML = '<span style="color: #2E7D32;">✓ 已存在</span>';
            } else {
                statusEl.innerHTML = '<span style="color: #F57C00;">⚠ 将在首次保存时创建</span>';
            }
        }
    } catch (e) {
        console.error('Failed to load server config:', e);
    }
}

async function saveServerConfig() {
    const maxConcurrent = parseInt(document.getElementById('max-concurrent').value);
    
    try {
        const res = await fetch('/admin/server-config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Admin-Token': adminToken
            },
            body: JSON.stringify({
                max_concurrent_tasks: maxConcurrent
            })
        });
        
        if (res.ok) {
            alert('服务器配置已保存');
        }
    } catch (e) {
        alert('保存失败：' + e.message);
    }
}

async function changeAdminPassword() {
    const oldPassword = document.getElementById('old-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('new-password-confirm').value;
    const messageDiv = document.getElementById('change-password-message');
    
    // 清除之前的消息
    messageDiv.textContent = '';
    messageDiv.style.color = '';
    
    // 验证输入
    if (!oldPassword) {
        messageDiv.textContent = '请输入当前密码';
        messageDiv.style.color = 'red';
        return;
    }
    
    if (!newPassword || newPassword.length < 6) {
        messageDiv.textContent = '新密码至少需要6位';
        messageDiv.style.color = 'red';
        return;
    }
    
    if (newPassword !== confirmPassword) {
        messageDiv.textContent = '两次输入的新密码不一致';
        messageDiv.style.color = 'red';
        return;
    }
    
    if (oldPassword === newPassword) {
        messageDiv.textContent = '新密码不能与当前密码相同';
        messageDiv.style.color = 'red';
        return;
    }
    
    try {
        const formData = new FormData();
        formData.append('old_password', oldPassword);
        formData.append('new_password', newPassword);
        
        const res = await fetch('/admin/change-password', {
            method: 'POST',
            headers: {
                'X-Admin-Token': adminToken
            },
            body: formData
        });
        
        const data = await res.json();
        
        if (data.success) {
            messageDiv.textContent = '✓ ' + data.message;
            messageDiv.style.color = '#2E7D32';
            
            // 清空输入框
            document.getElementById('old-password').value = '';
            document.getElementById('new-password').value = '';
            document.getElementById('new-password-confirm').value = '';
            
            // 3秒后自动退出登录
            setTimeout(() => {
                alert('密码已更改，请使用新密码重新登录');
                logout();
            }, 3000);
        } else {
            messageDiv.textContent = '✗ ' + data.message;
            messageDiv.style.color = '#C62828';
        }
    } catch (e) {
        messageDiv.textContent = '✗ 更改失败：' + e.message;
        messageDiv.style.color = '#C62828';
    }
}

async function loadPermissions() {
    try {
        const res = await fetch('/admin/settings', {
            headers: { 'X-Admin-Token': adminToken }
        });
        const settings = await res.json();
        
        const permissions = settings.permissions || {};
        document.getElementById('perm-upload-fonts').checked = permissions.can_upload_fonts !== false;
        document.getElementById('perm-delete-fonts').checked = permissions.can_delete_fonts !== false;
        document.getElementById('perm-upload-prompts').checked = permissions.can_upload_prompts !== false;
        document.getElementById('perm-delete-prompts').checked = permissions.can_delete_prompts !== false;
        
        // 加载上传限制
        const upload_limits = settings.upload_limits || {};
        document.getElementById('max-image-size').value = upload_limits.max_image_size_mb || 10;
        document.getElementById('max-images-batch').value = upload_limits.max_images_per_batch || 50;
    } catch (e) {
        console.error('Failed to load permissions:', e);
    }
}

async function savePermissions() {
    const permissions = {
        can_upload_fonts: document.getElementById('perm-upload-fonts').checked,
        can_delete_fonts: document.getElementById('perm-delete-fonts').checked,
        can_upload_prompts: document.getElementById('perm-upload-prompts').checked,
        can_delete_prompts: document.getElementById('perm-delete-prompts').checked
    };
    
    try {
        const res = await fetch('/admin/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Admin-Token': adminToken
            },
            body: JSON.stringify({ permissions })
        });
        
        if (res.ok) {
            alert('权限设置已保存');
            // 重新加载字体和提示词列表以更新按钮状态
            await loadFonts();
            await loadPrompts();
        }
    } catch (e) {
        alert('保存失败：' + e.message);
    }
}

async function saveUploadLimits() {
    const upload_limits = {
        max_image_size_mb: parseFloat(document.getElementById('max-image-size').value) || 0,
        max_images_per_batch: parseInt(document.getElementById('max-images-batch').value) || 0
    };
    
    try {
        const res = await fetch('/admin/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Admin-Token': adminToken
            },
            body: JSON.stringify({ upload_limits })
        });
        
        if (res.ok) {
            alert('上传限制已保存');
        }
    } catch (e) {
        alert('保存失败：' + e.message);
    }
}

async function loadUserAccess() {
    try {
        const res = await fetch('/admin/settings', {
            headers: { 'X-Admin-Token': adminToken }
        });
        const settings = await res.json();
        
        const user_access = settings.user_access || {};
        document.getElementById('require-user-password').checked = user_access.require_password || false;
        document.getElementById('user-password').value = user_access.user_password || '';
    } catch (e) {
        console.error('Failed to load user access settings:', e);
    }
}

async function saveUserAccess() {
    const user_access = {
        require_password: document.getElementById('require-user-password').checked,
        user_password: document.getElementById('user-password').value
    };
    
    try {
        const res = await fetch('/admin/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Admin-Token': adminToken
            },
            body: JSON.stringify({ user_access })
        });
        
        if (res.ok) {
            alert('用户访问控制已保存');
        }
    } catch (e) {
        alert('保存失败：' + e.message);
    }
}

async function loadApiKeyPolicy() {
    try {
        const res = await fetch('/admin/settings', {
            headers: { 'X-Admin-Token': adminToken }
        });
        const settings = await res.json();
        
        // 加载 show_env_to_users 设置
        document.getElementById('show-env-to-users').checked = settings.show_env_to_users || false;
        
        const policy = settings.api_key_policy || {};
        document.getElementById('policy-require-user-keys').checked = policy.require_user_keys || false;
        document.getElementById('policy-allow-server-keys').checked = policy.allow_server_keys !== false;
        document.getElementById('policy-save-user-keys').checked = policy.save_user_keys_to_server || false;
    } catch (e) {
        console.error('Failed to load API key policy:', e);
    }
}

async function saveApiKeyPolicy() {
    const show_env_to_users = document.getElementById('show-env-to-users').checked;
    const api_key_policy = {
        require_user_keys: document.getElementById('policy-require-user-keys').checked,
        allow_server_keys: document.getElementById('policy-allow-server-keys').checked,
        save_user_keys_to_server: document.getElementById('policy-save-user-keys').checked
    };
    
    try {
        const res = await fetch('/admin/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Admin-Token': adminToken
            },
            body: JSON.stringify({ 
                show_env_to_users,
                api_key_policy 
            })
        });
        
        if (res.ok) {
            alert('API Key 策略已保存');
        }
    } catch (e) {
        alert('保存失败：' + e.message);
    }
}

async function loadServerApiKeys() {
    try {
        // 获取所有翻译器
        const transRes = await fetch('/translators?mode=admin');
        const translators = await transRes.json();
        
        // 获取当前环境变量（包含实际值）
        const envRes = await fetch('/env-vars?show_values=true', {
            headers: { 'X-Admin-Token': adminToken }
        });
        const envData = await envRes.json();
        const envVars = envData.vars || {};
        const envPath = envData.path || '.env';
        
        const container = document.getElementById('server-api-keys');
        container.innerHTML = '';
        
        // 显示 .env 文件路径
        const pathInfo = document.createElement('div');
        pathInfo.style.cssText = 'background: #E3F2FD; padding: 10px; border-radius: 4px; margin-bottom: 15px; font-size: 13px;';
        pathInfo.innerHTML = `<strong>📁 .env 文件路径：</strong><br><code style="background: white; padding: 2px 6px; border-radius: 3px;">${envPath}</code>`;
        container.appendChild(pathInfo);
        
        // 常见的 API Key 配置
        const commonApiKeys = [
            { key: 'OPENAI_API_KEY', label: 'OpenAI API Key', translators: ['openai', 'gpt3', 'gpt3.5', 'gpt4'] },
            { key: 'OPENAI_MODEL', label: 'OpenAI Model', translators: ['openai'] },
            { key: 'OPENAI_API_BASE', label: 'OpenAI API Base URL', translators: ['openai'] },
            { key: 'DEEPL_AUTH_KEY', label: 'DeepL Auth Key', translators: ['deepl'] },
            { key: 'BAIDU_APP_ID', label: 'Baidu App ID', translators: ['baidu'] },
            { key: 'BAIDU_SECRET_KEY', label: 'Baidu Secret Key', translators: ['baidu'] },
            { key: 'YOUDAO_APP_KEY', label: 'Youdao App Key', translators: ['youdao'] },
            { key: 'YOUDAO_SECRET_KEY', label: 'Youdao Secret Key', translators: ['youdao'] },
            { key: 'CAIYUN_TOKEN', label: 'Caiyun Token', translators: ['caiyun'] },
            { key: 'GEMINI_API_KEY', label: 'Gemini API Key', translators: ['gemini'] },
            { key: 'GEMINI_MODEL', label: 'Gemini Model', translators: ['gemini'] },
            { key: 'GEMINI_API_BASE', label: 'Gemini API Base', translators: ['gemini'] },
            { key: 'GROQ_API_KEY', label: 'Groq API Key', translators: ['groq'] },
            { key: 'GROQ_MODEL', label: 'Groq Model', translators: ['groq'] },
            { key: 'SAKURA_API_BASE', label: 'Sakura API Base', translators: ['sakura'] },
        ];
        
        commonApiKeys.forEach(apiKey => {
            const div = document.createElement('div');
            div.className = 'form-group';
            div.style.marginBottom = '15px';
            
            const labelDiv = document.createElement('div');
            labelDiv.style.display = 'flex';
            labelDiv.style.justifyContent = 'space-between';
            labelDiv.style.alignItems = 'center';
            labelDiv.style.marginBottom = '5px';
            
            const label = document.createElement('label');
            label.textContent = apiKey.label;
            label.style.fontWeight = '500';
            
            const status = document.createElement('span');
            status.style.fontSize = '12px';
            status.style.padding = '2px 8px';
            status.style.borderRadius = '3px';
            if (envVars[apiKey.key]) {
                status.textContent = '✓ 已设置';
                status.style.background = '#C8E6C9';
                status.style.color = '#2E7D32';
            } else {
                status.textContent = '✗ 未设置';
                status.style.background = '#FFCDD2';
                status.style.color = '#C62828';
            }
            
            labelDiv.appendChild(label);
            labelDiv.appendChild(status);
            
            const inputWrapper = document.createElement('div');
            inputWrapper.style.display = 'flex';
            inputWrapper.style.gap = '5px';
            
            const input = document.createElement('input');
            input.type = 'text';  // 默认显示为文本
            input.dataset.key = apiKey.key;
            input.value = envVars[apiKey.key] || '';
            input.placeholder = '未设置';
            input.style.flex = '1';
            input.style.padding = '6px 10px';
            input.style.border = '1px solid #CFD8DC';
            input.style.borderRadius = '4px';
            input.style.fontFamily = 'monospace';
            input.style.fontSize = '13px';
            
            // 添加显示/隐藏按钮（仅对敏感字段）
            if (apiKey.key.includes('KEY') || apiKey.key.includes('TOKEN') || apiKey.key.includes('SECRET')) {
                const toggleBtn = document.createElement('button');
                toggleBtn.textContent = '👁️';
                toggleBtn.className = 'secondary-btn';
                toggleBtn.style.padding = '6px 12px';
                toggleBtn.title = '显示/隐藏';
                toggleBtn.onclick = () => {
                    if (input.type === 'password') {
                        input.type = 'text';
                        toggleBtn.textContent = '🙈';
                    } else {
                        input.type = 'password';
                        toggleBtn.textContent = '👁️';
                    }
                };
                inputWrapper.appendChild(input);
                inputWrapper.appendChild(toggleBtn);
                
                // 默认隐藏敏感信息
                input.type = 'password';
            } else {
                inputWrapper.appendChild(input);
            }
            
            const hint = document.createElement('small');
            hint.textContent = `用于: ${apiKey.translators.join(', ')}`;
            hint.style.color = '#999';
            hint.style.fontSize = '12px';
            hint.style.display = 'block';
            hint.style.marginTop = '3px';
            
            div.appendChild(labelDiv);
            div.appendChild(inputWrapper);
            div.appendChild(hint);
            container.appendChild(div);
        });
    } catch (e) {
        console.error('Failed to load server API keys:', e);
        const container = document.getElementById('server-api-keys');
        container.innerHTML = '<p style="color: red;">加载失败：' + e.message + '</p>';
    }
}

async function saveServerApiKeys() {
    const inputs = document.querySelectorAll('#server-api-keys input');
    const envVars = {};
    
    inputs.forEach(input => {
        if (input.value.trim()) {
            envVars[input.dataset.key] = input.value.trim();
        }
    });
    
    if (Object.keys(envVars).length === 0) {
        alert('请至少输入一个 API Key');
        return;
    }
    
    try {
        const res = await fetch('/env-vars', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Admin-Token': adminToken
            },
            body: JSON.stringify(envVars)
        });
        
        if (res.ok) {
            alert('服务器 API Keys 已保存到 .env 文件');
            await loadServerApiKeys(); // 重新加载以更新占位符
        }
    } catch (e) {
        alert('保存失败：' + e.message);
    }
}

async function loadVisibleSettings() {
    try {
        const res = await fetch('/admin/settings', {
            headers: { 'X-Admin-Token': adminToken }
        });
        const settings = await res.json();
        
        const visibleSections = settings.visible_sections || [];
        document.getElementById('visible-translator').checked = visibleSections.includes('translator');
        document.getElementById('visible-detector').checked = visibleSections.includes('detector');
        document.getElementById('visible-render').checked = visibleSections.includes('render');
        document.getElementById('visible-ocr').checked = visibleSections.includes('ocr');
    } catch (e) {
        console.error('Failed to load visible settings:', e);
    }
}

async function saveVisibleSettings() {
    const visibleSections = [];
    if (document.getElementById('visible-translator').checked) visibleSections.push('translator');
    if (document.getElementById('visible-detector').checked) visibleSections.push('detector');
    if (document.getElementById('visible-render').checked) visibleSections.push('render');
    if (document.getElementById('visible-ocr').checked) visibleSections.push('ocr');
    
    try {
        const res = await fetch('/admin/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Admin-Token': adminToken
            },
            body: JSON.stringify({
                visible_sections: visibleSections
            })
        });
        
        if (res.ok) {
            alert('可见设置已保存');
        }
    } catch (e) {
        alert('保存失败：' + e.message);
    }
}

// Load all translators
async function loadAllTranslators() {
    try {
        const res = await fetch('/translators?mode=admin');
        const translators = await res.json();
        
        const settingsRes = await fetch('/admin/settings', {
            headers: { 'X-Admin-Token': adminToken }
        });
        const settings = await settingsRes.json();
        const allowedTranslators = settings.allowed_translators || [];
        
        const container = document.getElementById('translator-checkboxes');
        container.innerHTML = '';
        
        translators.forEach(trans => {
            const div = document.createElement('div');
            div.className = 'checkbox-wrapper';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `trans-${trans}`;
            checkbox.value = trans;
            checkbox.checked = allowedTranslators.length === 0 || allowedTranslators.includes(trans);
            
            const label = document.createElement('label');
            label.textContent = trans;
            label.htmlFor = `trans-${trans}`;
            
            div.appendChild(checkbox);
            div.appendChild(label);
            container.appendChild(div);
        });
    } catch (e) {
        console.error('Failed to load translators:', e);
    }
}

async function saveAllowedTranslators() {
    const checkboxes = document.querySelectorAll('#translator-checkboxes input[type="checkbox"]');
    const allowedTranslators = [];
    
    checkboxes.forEach(cb => {
        if (cb.checked) {
            allowedTranslators.push(cb.value);
        }
    });
    
    try {
        const res = await fetch('/admin/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Admin-Token': adminToken
            },
            body: JSON.stringify({
                allowed_translators: allowedTranslators
            })
        });
        
        if (res.ok) {
            alert('翻译器设置已保存');
        }
    } catch (e) {
        alert('保存失败：' + e.message);
    }
}

// Load all languages
async function loadAllLanguages() {
    try {
        const res = await fetch('/languages?mode=admin');
        const languages = await res.json();
        
        const settingsRes = await fetch('/admin/settings', {
            headers: { 'X-Admin-Token': adminToken }
        });
        const settings = await settingsRes.json();
        const allowedLanguages = settings.allowed_languages || [];
        
        const container = document.getElementById('language-checkboxes');
        container.innerHTML = '';
        
        languages.forEach(lang => {
            const div = document.createElement('div');
            div.className = 'checkbox-wrapper';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `lang-${lang}`;
            checkbox.value = lang;
            checkbox.checked = allowedLanguages.length === 0 || allowedLanguages.includes(lang);
            
            const label = document.createElement('label');
            label.textContent = lang;
            label.htmlFor = `lang-${lang}`;
            
            div.appendChild(checkbox);
            div.appendChild(label);
            container.appendChild(div);
        });
    } catch (e) {
        console.error('Failed to load languages:', e);
    }
}

async function saveAllowedLanguages() {
    const checkboxes = document.querySelectorAll('#language-checkboxes input[type="checkbox"]');
    const allowedLanguages = [];
    
    checkboxes.forEach(cb => {
        if (cb.checked) {
            allowedLanguages.push(cb.value);
        }
    });
    
    try {
        const res = await fetch('/admin/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Admin-Token': adminToken
            },
            body: JSON.stringify({
                allowed_languages: allowedLanguages
            })
        });
        
        if (res.ok) {
            alert('语言设置已保存');
        }
    } catch (e) {
        alert('保存失败：' + e.message);
    }
}

// Load all workflows
async function loadAllWorkflows() {
    try {
        const res = await fetch('/workflows?mode=admin');
        const workflows = await res.json();
        
        const settingsRes = await fetch('/admin/settings', {
            headers: { 'X-Admin-Token': adminToken }
        });
        const settings = await settingsRes.json();
        const allowedWorkflows = settings.allowed_workflows || [];
        
        const container = document.getElementById('workflow-checkboxes');
        container.innerHTML = '';
        
        // 翻译流程名称映射
        const workflowNames = {
            'normal': '正常翻译流程',
            'export_trans': '导出翻译',
            'export_raw': '导出原文',
            'import_trans': '导入翻译并渲染',
            'colorize': '仅上色',
            'upscale': '仅超分',
            'inpaint': '仅修复'
        };
        
        workflows.forEach(workflow => {
            const div = document.createElement('div');
            div.className = 'checkbox-wrapper';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `workflow-${workflow}`;
            checkbox.value = workflow;
            checkbox.checked = allowedWorkflows.length === 0 || allowedWorkflows.includes(workflow);
            
            const label = document.createElement('label');
            label.textContent = workflowNames[workflow] || workflow;
            label.htmlFor = `workflow-${workflow}`;
            
            div.appendChild(checkbox);
            div.appendChild(label);
            container.appendChild(div);
        });
    } catch (e) {
        console.error('Failed to load workflows:', e);
    }
}

async function saveAllowedWorkflows() {
    const checkboxes = document.querySelectorAll('#workflow-checkboxes input[type="checkbox"]');
    const allowedWorkflows = [];
    
    checkboxes.forEach(cb => {
        if (cb.checked) {
            allowedWorkflows.push(cb.value);
        }
    });
    
    try {
        const res = await fetch('/admin/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Admin-Token': adminToken
            },
            body: JSON.stringify({
                allowed_workflows: allowedWorkflows
            })
        });
        
        if (res.ok) {
            alert('翻译流程设置已保存');
        }
    } catch (e) {
        alert('保存失败：' + e.message);
    }
}

// Font upload
document.getElementById('font-upload').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/upload/font', {
            method: 'POST',
            headers: { 'X-Admin-Token': adminToken },
            body: formData
        });
        
        if (res.ok) {
            alert('字体上传成功');
            loadFonts();
        } else {
            const data = await res.json();
            alert('上传失败：' + (data.detail || '未知错误'));
        }
    } catch (e) {
        alert('上传失败：' + e.message);
    }
    
    e.target.value = '';
});

async function loadFonts() {
    try {
        const res = await fetch('/fonts');
        const fonts = await res.json();
        
        // 获取权限设置
        const settingsRes = await fetch('/admin/settings', {
            headers: { 'X-Admin-Token': adminToken }
        });
        const settings = await settingsRes.json();
        const canDelete = settings.permissions?.can_delete_fonts !== false;
        const canUpload = settings.permissions?.can_upload_fonts !== false;
        
        // 控制上传按钮显示
        const uploadBtn = document.querySelector('#font-upload').parentElement.querySelector('button');
        if (uploadBtn) {
            uploadBtn.style.display = canUpload ? 'inline-block' : 'none';
        }
        
        const list = document.getElementById('font-list');
        list.innerHTML = '<h4>已有的字体文件：</h4>';
        if (fonts.length === 0) {
            list.innerHTML += '<p style="color: #999;">暂无字体文件</p>';
        } else {
            fonts.forEach(font => {
                const div = document.createElement('div');
                div.style.cssText = 'display: flex; justify-content: space-between; align-items: center; padding: 5px; border-bottom: 1px solid #eee;';
                
                // 只有有删除权限才显示删除按钮
                const deleteBtn = canDelete 
                    ? `<button onclick="deleteFont('${font}')" class="secondary-btn" style="padding: 2px 8px; background: #ef5350; color: white;">删除</button>`
                    : '';
                
                div.innerHTML = `
                    <span>${font}</span>
                    ${deleteBtn}
                `;
                list.appendChild(div);
            });
        }
    } catch (e) {
        console.error('Failed to load fonts:', e);
    }
}

async function deleteFont(filename) {
    if (!confirm(`确定要删除字体 ${filename} 吗？`)) return;
    
    try {
        const res = await fetch(`/fonts/${filename}`, {
            method: 'DELETE',
            headers: { 'X-Admin-Token': adminToken }
        });
        
        if (res.ok) {
            alert('字体已删除');
            loadFonts();
        } else {
            const data = await res.json();
            alert('删除失败：' + (data.detail || '未知错误'));
        }
    } catch (e) {
        alert('删除失败：' + e.message);
    }
}

// Prompt upload
document.getElementById('prompt-upload').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/upload/prompt', {
            method: 'POST',
            headers: { 'X-Admin-Token': adminToken },
            body: formData
        });
        
        if (res.ok) {
            alert('提示词上传成功');
            loadPrompts();
        } else {
            const data = await res.json();
            alert('上传失败：' + (data.detail || '未知错误'));
        }
    } catch (e) {
        alert('上传失败：' + e.message);
    }
    
    e.target.value = '';
});

async function loadPrompts() {
    try {
        const res = await fetch('/prompts', {
            headers: { 'X-Admin-Token': adminToken }
        });
        
        if (!res.ok) {
            console.error('Failed to fetch prompts:', res.status, res.statusText);
            const list = document.getElementById('prompt-list');
            list.innerHTML = '<h4>已有的提示词文件：</h4><p style="color: red;">加载失败</p>';
            return;
        }
        
        const prompts = await res.json();
        
        if (!Array.isArray(prompts)) {
            console.error('Prompts response is not an array:', prompts);
            const list = document.getElementById('prompt-list');
            list.innerHTML = '<h4>已有的提示词文件：</h4><p style="color: red;">数据格式错误</p>';
            return;
        }
        
        // 获取权限设置
        const settingsRes = await fetch('/admin/settings', {
            headers: { 'X-Admin-Token': adminToken }
        });
        const settings = await settingsRes.json();
        const canDelete = settings.permissions?.can_delete_prompts !== false;
        const canUpload = settings.permissions?.can_upload_prompts !== false;
        
        // 控制上传按钮显示
        const uploadBtn = document.querySelector('#prompt-upload').parentElement.querySelector('button');
        if (uploadBtn) {
            uploadBtn.style.display = canUpload ? 'inline-block' : 'none';
        }
        
        const list = document.getElementById('prompt-list');
        list.innerHTML = '<h4>已有的提示词文件：</h4>';
        if (prompts.length === 0) {
            list.innerHTML += '<p style="color: #999;">暂无提示词文件</p>';
        } else {
            prompts.forEach(prompt => {
                const div = document.createElement('div');
                div.style.cssText = 'display: flex; justify-content: space-between; align-items: center; padding: 5px; border-bottom: 1px solid #eee;';
                
                // 只有有删除权限才显示删除按钮
                const deleteBtn = canDelete
                    ? `<button onclick="deletePrompt('${prompt}')" class="secondary-btn" style="padding: 2px 8px; background: #ef5350; color: white;">删除</button>`
                    : '';
                
                div.innerHTML = `
                    <span>${prompt}</span>
                    <div>
                        <button onclick="viewPrompt('${prompt}')" class="secondary-btn" style="padding: 2px 8px; margin-right: 5px;">查看</button>
                        ${deleteBtn}
                    </div>
                `;
                list.appendChild(div);
            });
        }
    } catch (e) {
        console.error('Failed to load prompts:', e);
    }
}

async function viewPrompt(filename) {
    try {
        const res = await fetch(`/prompts/${filename}`, {
            headers: { 'X-Admin-Token': adminToken }
        });
        const data = await res.json();
        
        // 格式化 JSON 显示
        const formatted = JSON.stringify(JSON.parse(data.content), null, 2);
        alert(`${filename}:\n\n${formatted}`);
    } catch (e) {
        alert('查看失败：' + e.message);
    }
}

async function deletePrompt(filename) {
    if (!confirm(`确定要删除提示词 ${filename} 吗？`)) return;
    
    try {
        const res = await fetch(`/prompts/${filename}`, {
            method: 'DELETE',
            headers: { 'X-Admin-Token': adminToken }
        });
        
        if (res.ok) {
            alert('提示词已删除');
            loadPrompts();
        } else {
            const data = await res.json();
            alert('删除失败：' + (data.detail || '未知错误'));
        }
    } catch (e) {
        alert('删除失败：' + e.message);
    }
}

async function setupPassword() {
    const password = document.getElementById('setup-password').value;
    const confirm = document.getElementById('setup-password-confirm').value;
    const errorDiv = document.getElementById('setup-error');
    
    if (!password || password.length < 6) {
        errorDiv.textContent = '密码至少需要6位';
        return;
    }
    
    if (password !== confirm) {
        errorDiv.textContent = '两次输入的密码不一致';
        return;
    }
    
    try {
        const formData = new FormData();
        formData.append('password', password);
        const res = await fetch('/admin/setup', {
            method: 'POST',
            body: formData
        });
        
        const data = await res.json();
        if (data.success) {
            adminToken = data.token;
            localStorage.setItem('adminToken', adminToken);
            document.getElementById('setup-screen').style.display = 'none';
            document.getElementById('admin-panel').style.display = 'block';
            loadAdminData();
        } else {
            errorDiv.textContent = data.message || '设置失败';
        }
    } catch (e) {
        errorDiv.textContent = '设置失败：' + e.message;
    }
}

// Check if already logged in or try auto-login
window.addEventListener('DOMContentLoaded', async () => {
    // 先加载 i18n
    await loadI18n(currentLocale);
    
    // 检查是否需要首次设置密码
    try {
        const setupRes = await fetch('/admin/need-setup');
        const setupData = await setupRes.json();
        
        console.log('Setup check result:', setupData);  // 调试日志
        
        if (setupData.need_setup) {
            // 显示首次设置界面
            console.log('Showing setup screen');  // 调试日志
            document.getElementById('setup-screen').style.display = 'flex';
            document.getElementById('login-screen').style.display = 'none';
            document.getElementById('admin-panel').style.display = 'none';
            return;
        }
    } catch (e) {
        console.error('Failed to check setup status:', e);
        // 如果检查失败，默认显示登录界面
        document.getElementById('login-screen').style.display = 'flex';
        document.getElementById('setup-screen').style.display = 'none';
        document.getElementById('admin-panel').style.display = 'none';
        return;
    }
    
    // 如果不需要设置，检查是否有保存的 token
    const savedToken = localStorage.getItem('adminToken');
    if (savedToken) {
        adminToken = savedToken;
        document.getElementById('login-screen').style.display = 'none';
        document.getElementById('setup-screen').style.display = 'none';
        document.getElementById('admin-panel').style.display = 'block';
        loadAdminData();
    } else {
        // 显示登录界面
        document.getElementById('login-screen').style.display = 'flex';
        document.getElementById('setup-screen').style.display = 'none';
        document.getElementById('admin-panel').style.display = 'none';
    }
});


// ===== 任务管理功能 =====
async function refreshTasks() {
    try {
        const res = await fetch('/admin/tasks', {
            headers: { 'X-Admin-Token': adminToken }
        });
        const tasks = await res.json();
        
        const container = document.getElementById('active-tasks-list');
        if (tasks.length === 0) {
            container.innerHTML = '<p style="color: #666;">当前没有活动任务</p>';
            return;
        }
        
        let html = '<table style="width: 100%; border-collapse: collapse;">';
        html += '<thead><tr style="background: #F5F7FA; border-bottom: 2px solid #E0E0E0;">';
        html += '<th style="padding: 10px; text-align: left;">任务ID</th>';
        html += '<th style="padding: 10px; text-align: left;">开始时间</th>';
        html += '<th style="padding: 10px; text-align: left;">运行时长</th>';
        html += '<th style="padding: 10px; text-align: left;">状态</th>';
        html += '<th style="padding: 10px; text-align: center;">操作</th>';
        html += '</tr></thead><tbody>';
        
        tasks.forEach(task => {
            const duration = Math.floor(task.duration);
            const minutes = Math.floor(duration / 60);
            const seconds = duration % 60;
            const durationStr = `${minutes}分${seconds}秒`;
            
            html += '<tr style="border-bottom: 1px solid #E0E0E0;">';
            html += `<td style="padding: 10px; font-family: monospace;">${task.task_id.substring(0, 8)}...</td>`;
            html += `<td style="padding: 10px;">${new Date(task.start_time).toLocaleString('zh-CN')}</td>`;
            html += `<td style="padding: 10px;">${durationStr}</td>`;
            html += `<td style="padding: 10px;"><span style="color: #4CAF50;">●</span> ${task.status}</td>`;
            html += `<td style="padding: 10px; text-align: center;">`;
            html += `<button onclick="viewTaskLogs('${task.task_id}')" class="secondary-btn" style="padding: 5px 10px; font-size: 12px; margin-right: 5px;">查看日志</button>`;
            html += `<button onclick="cancelTask('${task.task_id}', false)" class="secondary-btn" style="padding: 5px 10px; font-size: 12px; margin-right: 5px;">取消</button>`;
            html += `<button onclick="cancelTask('${task.task_id}', true)" class="secondary-btn" style="padding: 5px 10px; font-size: 12px; background: #E57373; color: white;">强制终止</button>`;
            html += `</td></tr>`;
        });
        
        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (e) {
        console.error('Failed to refresh tasks:', e);
        document.getElementById('active-tasks-list').innerHTML = '<p style="color: red;">加载失败</p>';
    }
}

async function viewTaskLogs(taskId) {
    // 切换到日志查看器并过滤该任务的日志
    const logsContainer = document.getElementById('logs-container');
    const logLevelFilter = document.getElementById('log-level-filter');
    
    try {
        const res = await fetch(`/logs?task_id=${taskId}&limit=500`);
        const logs = await res.json();
        
        if (logs.length === 0) {
            logsContainer.innerHTML = `<p style="color: #666;">任务 ${taskId.substring(0, 8)}... 暂无日志</p>`;
            return;
        }
        
        let html = `<div style="margin-bottom: 10px; padding: 10px; background: #37474F; border-radius: 4px;">`;
        html += `<strong style="color: #81C784;">任务日志: ${taskId.substring(0, 8)}...</strong>`;
        html += `<button onclick="refreshLogs()" style="margin-left: 10px; padding: 5px 10px; background: #546E7A; color: white; border: none; border-radius: 3px; cursor: pointer;">返回全局日志</button>`;
        html += `</div>`;
        
        logs.forEach(log => {
            const levelColor = {
                'DEBUG': '#90CAF9',
                'INFO': '#81C784',
                'WARNING': '#FFB74D',
                'ERROR': '#E57373'
            }[log.level] || '#ADBAC7';
            
            const time = new Date(log.timestamp).toLocaleTimeString('zh-CN');
            html += `<div style="margin-bottom: 8px; padding: 8px; background: #1E2A30; border-left: 3px solid ${levelColor}; border-radius: 3px;">`;
            html += `<span style="color: #78909C; font-size: 11px;">${time}</span> `;
            html += `<span style="color: ${levelColor}; font-weight: bold;">[${log.level}]</span> `;
            html += `<span style="color: #ECEFF1;">${escapeHtml(log.message)}</span>`;
            html += `</div>`;
        });
        
        logsContainer.innerHTML = html;
        
        // 滚动到日志区域
        logsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) {
        console.error('Failed to load task logs:', e);
        alert('加载任务日志失败：' + e.message);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function cancelTask(taskId, force = false) {
    const action = force ? '强制终止' : '取消';
    const warning = force 
        ? `⚠️ 确定要强制终止任务 ${taskId.substring(0, 8)}... 吗？\n\n强制终止会立即中断任务，可能导致：\n- 未保存的进度丢失\n- 临时文件残留\n- GPU 显存未释放\n\n建议先尝试普通取消，如果任务卡住再使用强制终止。`
        : `确定要取消任务 ${taskId.substring(0, 8)}... 吗？\n\n任务将在下一个检查点停止（通常 < 1秒）`;
    
    if (!confirm(warning)) {
        return;
    }
    
    try {
        const url = `/admin/tasks/${taskId}/cancel${force ? '?force=true' : ''}`;
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'X-Admin-Token': adminToken }
        });
        const data = await res.json();
        
        if (data.success) {
            alert(data.message || `${action}请求已发送`);
            refreshTasks();
        } else {
            alert(`${action}失败：` + (data.message || '未知错误'));
        }
    } catch (e) {
        console.error(`Failed to ${action} task:`, e);
        alert(`${action}失败：` + e.message);
    }
}

// ===== 日志查看功能 =====
async function refreshLogs() {
    try {
        const level = document.getElementById('log-level-filter').value;
        const limit = document.getElementById('log-limit').value || 200;
        
        let url = `/logs?limit=${limit}`;
        if (level) {
            url += `&level=${level}`;
        }
        
        const res = await fetch(url);
        const logs = await res.json();
        
        const container = document.getElementById('logs-container');
        if (logs.length === 0) {
            container.innerHTML = '<p style="color: #666;">暂无日志</p>';
            return;
        }
        
        let html = '';
        logs.forEach(log => {
            const levelColor = {
                'DEBUG': '#90CAF9',
                'INFO': '#81C784',
                'WARNING': '#FFB74D',
                'ERROR': '#E57373'
            }[log.level] || '#ADBAC7';
            
            const time = new Date(log.timestamp).toLocaleTimeString('zh-CN');
            html += `<div style="margin-bottom: 5px;">`;
            html += `<span style="color: #666;">[${time}]</span> `;
            html += `<span style="color: ${levelColor}; font-weight: bold;">[${log.level}]</span> `;
            html += `<span>${log.message}</span>`;
            html += `</div>`;
        });
        
        container.innerHTML = html;
        // 自动滚动到底部
        container.scrollTop = container.scrollHeight;
    } catch (e) {
        console.error('Failed to refresh logs:', e);
        document.getElementById('logs-container').innerHTML = '<p style="color: red;">加载失败</p>';
    }
}

async function exportLogs() {
    try {
        const res = await fetch('/admin/logs/export', {
            headers: { 'X-Admin-Token': adminToken }
        });
        
        if (!res.ok) {
            throw new Error('导出失败');
        }
        
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `logs_${new Date().toISOString().replace(/[:.]/g, '-')}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        alert('日志已导出');
    } catch (e) {
        console.error('Failed to export logs:', e);
        alert('导出失败：' + e.message);
    }
}

// 自动刷新任务和日志
setInterval(() => {
    if (adminToken && document.getElementById('admin-panel').style.display !== 'none') {
        refreshTasks();
        refreshLogs();
    }
}, 5000); // 每5秒刷新一次

// 页面加载时初始化
// ===== 公告管理功能 =====
async function loadAnnouncement() {
    try {
        const res = await fetch('/admin/announcement', {
            headers: { 'X-Admin-Token': adminToken }
        });
        
        if (!res.ok) {
            // 如果端点不存在，使用默认值
            return;
        }
        
        const announcement = await res.json();
        document.getElementById('announcement-enabled').checked = announcement.enabled || false;
        document.getElementById('announcement-type').value = announcement.type || 'info';
        document.getElementById('announcement-message').value = announcement.message || '';
    } catch (e) {
        console.error('Failed to load announcement:', e);
    }
}

async function saveAnnouncement() {
    const announcement = {
        enabled: document.getElementById('announcement-enabled').checked,
        type: document.getElementById('announcement-type').value,
        message: document.getElementById('announcement-message').value
    };
    
    try {
        const res = await fetch('/admin/announcement', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Admin-Token': adminToken
            },
            body: JSON.stringify(announcement)
        });
        
        const data = await res.json();
        if (data.success) {
            alert('公告已保存');
        } else {
            alert('保存失败');
        }
    } catch (e) {
        console.error('Failed to save announcement:', e);
        alert('保存失败：' + e.message);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // 如果已登录，加载任务和日志
    if (adminToken) {
        refreshTasks();
        refreshLogs();
        loadAnnouncement();  // 加载公告
        
        // 自动刷新任务列表（每3秒）
        setInterval(() => {
            refreshTasks();
        }, 3000);
        
        // 自动刷新日志（每5秒）
        setInterval(() => {
            refreshLogs();
        }, 5000);
    }
});
