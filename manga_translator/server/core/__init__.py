"""
核心模块

提供配置管理、身份验证、日志管理、任务管理、响应工具、数据模型和持久化功能。
"""

# 数据模型
from .models import (
    UserPermissions,
    UserAccount,
    Session,
    AuditEvent,
)

# 持久化工具
from .persistence import (
    atomic_write_json,
    load_json,
    create_backup,
    cleanup_old_backups,
    ensure_directory,
)

# 服务
from .account_service import AccountService
from .session_service import SessionService
from .permission_service import PermissionService
from .audit_service import AuditService
from .env_service import EnvService

# 系统初始化
from .system_init import (
    SystemInitializer,
    init_system,
    get_system_initializer,
)

# 配置管理
from .config_manager import (
    ADMIN_CONFIG_PATH,
    SERVER_CONFIG_PATH,
    DEFAULT_ADMIN_SETTINGS,
    AVAILABLE_WORKFLOWS,
    load_admin_settings,
    save_admin_settings,
    load_default_config_dict,
    load_default_config,
    parse_config,
    get_available_workflows,
    temp_env_vars,
    init_server_config_file,
)

# 身份验证（旧版）
from .auth import (
    valid_admin_tokens,
    generate_admin_token,
    validate_admin_token,
    add_admin_token,
    remove_admin_token,
    clear_admin_tokens,
    require_admin_token,
    admin_login,
    setup_admin_password,
    change_admin_password,
    user_login,
    check_user_access,
)

# 认证和授权中间件（新版）
from .middleware import (
    init_middleware_services,
    get_services,
    create_error_response,
    require_auth,
    require_admin,
    check_translator_permission,
    check_parameter_permission,
    check_concurrent_limit,
    check_daily_quota,
    increment_task_count,
    decrement_task_count,
    increment_daily_usage,
)

# 日志管理
from .logging_manager import (
    task_logs,
    global_log_queue,
    generate_task_id,
    set_task_id,
    get_task_id,
    add_log,
    get_logs,
    export_logs,
    WebLogHandler,
    setup_log_handler,
)

# 任务管理
from .task_manager import (
    translation_semaphore,
    server_config,
    active_tasks,
    init_semaphore,
    get_semaphore,
    register_active_task,
    unregister_active_task,
    update_task_status,
    get_active_tasks,
    is_task_cancelled,
    cancel_task,
    update_server_config,
    get_server_config,
)

# 响应工具
from .response_utils import (
    transform_to_image,
    transform_to_json,
    transform_to_bytes,
    apply_user_env_vars,
)

__all__ = [
    # 数据模型
    'UserPermissions',
    'UserAccount',
    'Session',
    'AuditEvent',
    # 持久化工具
    'atomic_write_json',
    'load_json',
    'create_backup',
    'cleanup_old_backups',
    'ensure_directory',
    # 服务
    'AccountService',
    'SessionService',
    'PermissionService',
    'AuditService',
    'EnvService',
    # 系统初始化
    'SystemInitializer',
    'init_system',
    'get_system_initializer',
    # 配置管理
    'ADMIN_CONFIG_PATH',
    'SERVER_CONFIG_PATH',
    'DEFAULT_ADMIN_SETTINGS',
    'AVAILABLE_WORKFLOWS',
    'load_admin_settings',
    'save_admin_settings',
    'load_default_config_dict',
    'load_default_config',
    'parse_config',
    'get_available_workflows',
    'temp_env_vars',
    'init_server_config_file',
    # 身份验证（旧版）
    'valid_admin_tokens',
    'generate_admin_token',
    'validate_admin_token',
    'add_admin_token',
    'remove_admin_token',
    'clear_admin_tokens',
    'require_admin_token',
    'admin_login',
    'setup_admin_password',
    'change_admin_password',
    'user_login',
    'check_user_access',
    # 认证和授权中间件（新版）
    'init_middleware_services',
    'get_services',
    'create_error_response',
    'require_auth',
    'require_admin',
    'check_translator_permission',
    'check_parameter_permission',
    'check_concurrent_limit',
    'check_daily_quota',
    'increment_task_count',
    'decrement_task_count',
    'increment_daily_usage',
    # 日志管理
    'task_logs',
    'global_log_queue',
    'generate_task_id',
    'set_task_id',
    'get_task_id',
    'add_log',
    'get_logs',
    'export_logs',
    'WebLogHandler',
    'setup_log_handler',
    # 任务管理
    'translation_semaphore',
    'server_config',
    'active_tasks',
    'init_semaphore',
    'get_semaphore',
    'register_active_task',
    'unregister_active_task',
    'get_active_tasks',
    'is_task_cancelled',
    'cancel_task',
    'update_server_config',
    'get_server_config',
    # 响应工具
    'transform_to_image',
    'transform_to_json',
    'transform_to_bytes',
    'apply_user_env_vars',
]
