import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError

from manga_translator.server.instance import ExecutorInstance, executor_instances
import logging

# Import core modules
from manga_translator.server.core import config_manager, logging_manager, task_manager

# 初始化服务器配置文件（如果不存在则从模板复制）
config_manager.init_server_config_file()

# Import route modules
from manga_translator.server.routes import (
    translation_router,
    admin_router,
    config_router,
    files_router,
    web_router,
    users_router,
    audit_router,
    auth_router,
    init_auth_services,
    groups_router,
    resources_router,
    init_resource_routes,
    history_router,
    init_history_routes,
    quota_router,
    init_quota_routes,
    config_management_router,
    logs_router,
    v1_manga_router,
    v1_translate_router,
    internal_translate_router,
    v1_scraper_router,
    v1_parser_router,
    v1_settings_router,
    v1_system_router,
)

# Import sessions_router
from manga_translator.server.routes import sessions_router

logger = logging.getLogger('manga_translator.server')
GEMINI_PRIMARY_MODEL_DEFAULT = "gemini-3-flash-preview"
GEMINI_FALLBACK_MODEL_DEFAULT = "gemini-2.5-flash"
DEPRECATED_GEMINI_MODELS = {"gemini-2.0-flash"}

# 设置Web服务器标志，防止翻译器重新加载.env覆盖用户环境变量
os.environ['MANGA_TRANSLATOR_WEB_SERVER'] = 'true'

# 启动时加载 .env 文件
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"[INFO] Loaded environment variables from: {env_path}")
    # 打印已加载的 API Keys（不显示值）
    loaded_keys = [k for k in os.environ.keys() if 'API' in k or 'KEY' in k or 'TOKEN' in k]
    if loaded_keys:
        print(f"[INFO] Loaded API keys: {', '.join(loaded_keys)}")
else:
    print(f"[WARNING] .env file not found at: {env_path}")

app = FastAPI()
nonce = None

# Initialize logging manager
logging_manager.setup_log_handler()

# Note: config_manager and task_manager are initialized when imported
# task_manager.init_semaphore() will be called in run_server()

# Global service instances (will be initialized on startup)
_account_service = None
_session_service = None
_permission_service = None
_audit_service = None
_system_initializer = None


def _normalize_gemini_model(model_name: str | None, *, role: str) -> str:
    fallback = GEMINI_FALLBACK_MODEL_DEFAULT if role == "fallback" else GEMINI_PRIMARY_MODEL_DEFAULT
    normalized = str(model_name or "").strip() or fallback
    if normalized.lower() in DEPRECATED_GEMINI_MODELS:
        logger.warning(
            "Deprecated Gemini model '%s' requested for %s; normalized to '%s'",
            normalized,
            role,
            GEMINI_FALLBACK_MODEL_DEFAULT,
        )
        return GEMINI_FALLBACK_MODEL_DEFAULT
    return normalized


def _resolve_runtime_gemini_models() -> tuple[str, str]:
    primary = _normalize_gemini_model(os.getenv("GEMINI_MODEL"), role="primary")
    fallback = _normalize_gemini_model(os.getenv("GEMINI_FALLBACK_MODEL"), role="fallback")
    os.environ["GEMINI_MODEL"] = primary
    os.environ["GEMINI_FALLBACK_MODEL"] = fallback
    return primary, fallback


@app.on_event("startup")
async def startup_event():
    """Initialize services on server startup"""
    global _account_service, _session_service, _permission_service, _audit_service, _system_initializer

    from manga_translator.server.core.logging_manager import add_log

    resolved_use_gpu = _ensure_runtime_server_config()
    runtime_source = task_manager.server_config.get("_runtime_config_source", "unknown")
    logger.info("Runtime config ready: use_gpu=%s source=%s", resolved_use_gpu, runtime_source)
    add_log(f"运行时配置: use_gpu={resolved_use_gpu}, source={runtime_source}", "INFO")
    compute_only = str(os.getenv("MANGA_CLOUDRUN_COMPUTE_ONLY", "")).strip().lower() in {"1", "true", "yes", "on"}
    gemini_model, gemini_fallback_model = _resolve_runtime_gemini_models()
    has_gemini_key = bool(str(os.getenv("GEMINI_API_KEY", "")).strip())
    logger.info(
        "Compute runtime check: compute_only=%s primary_model=%s fallback_model=%s has_gemini_key=%s",
        compute_only,
        gemini_model,
        gemini_fallback_model,
        has_gemini_key,
    )

    from manga_translator.server.core import (
        AccountService,
        SessionService,
        PermissionService,
        AuditService,
        init_middleware_services,
        init_system
    )
    from manga_translator.server.routes.translation_auth import init_translation_auth
    
    # 添加启动日志
    add_log("服务器正在启动...", "INFO")
    logger.info("Server starting up...")
    from manga_translator.server.core.resource_service import ResourceManagementService
    from manga_translator.server.core.permission_service_v2 import EnhancedPermissionService
    from manga_translator.server.core.permission_integration import IntegratedPermissionService
    from manga_translator.server.repositories.resource_repository import ResourceRepository
    from manga_translator.server.repositories.permission_repository import PermissionRepository
    
    # Initialize services - 所有数据文件统一放在 manga_translator/server/data 目录
    DATA_DIR = "manga_translator/server/data"
    _account_service = AccountService(accounts_file=f"{DATA_DIR}/accounts.json")
    _session_service = SessionService(
        sessions_file=f"{DATA_DIR}/sessions.json",
        session_timeout_minutes=60,
        enable_persistence=True
    )
    _permission_service = PermissionService(_account_service)
    _audit_service = AuditService(audit_log_file=f"{DATA_DIR}/audit.log")
    
    # Initialize middleware services
    init_middleware_services(_account_service, _session_service, _permission_service)
    
    # Initialize auth services
    init_auth_services(_account_service, _session_service, _audit_service)

    # Initialize scraper task sqlite store
    import manga_translator.server.routes.v1_scraper as v1_scraper_routes
    v1_scraper_routes.init_task_store(Path(DATA_DIR) / "scraper_tasks.db")
    stale_tasks = v1_scraper_routes.recover_stale_tasks()
    if stale_tasks:
        logger.warning("Recovered %s stale scraper task(s) after startup", stale_tasks)
    await v1_scraper_routes.start_alert_scheduler()
    
    # Initialize translation authentication
    init_translation_auth(_audit_service)
    
    # Initialize resource management services
    prompts_repo = ResourceRepository("manga_translator/server/user_resources/prompts/index.json")
    fonts_repo = ResourceRepository("manga_translator/server/user_resources/fonts/index.json")
    resource_service = ResourceManagementService(prompts_repo, fonts_repo)
    
    # Initialize enhanced permission service for resource routes
    permission_repo = PermissionRepository("manga_translator/server/data/permissions.json")
    enhanced_permission_service = EnhancedPermissionService(permission_repo)
    
    # Initialize integrated permission service (with user group support)
    integrated_permission_service = IntegratedPermissionService(_account_service, enhanced_permission_service)
    
    # Initialize resource routes
    init_resource_routes(resource_service, integrated_permission_service)
    
    # Initialize history management services
    from manga_translator.server.core.history_service import HistoryManagementService
    from manga_translator.server.core.search_service import SearchService
    from manga_translator.server.repositories.translation_repository import TranslationRepository
    
    translation_repo = TranslationRepository("manga_translator/server/data/translation_history.json")
    history_service = HistoryManagementService(
        result_directory="manga_translator/server/data/results",
        translation_repo=translation_repo
    )
    search_service = SearchService()
    
    # Initialize history routes
    init_history_routes(history_service, integrated_permission_service, search_service)
    
    # Initialize quota management services
    from manga_translator.server.core.quota_service import QuotaManagementService
    from manga_translator.server.core.group_service import GroupService
    from manga_translator.server.repositories.quota_repository import QuotaRepository
    
    quota_repo = QuotaRepository("manga_translator/server/data/quotas.json")
    group_service = GroupService()
    quota_service = QuotaManagementService(quota_repo, permission_repo, group_service)
    
    # Initialize quota routes
    init_quota_routes(quota_service)
    
    # Initialize system (includes creating default admin, starting background tasks)
    _system_initializer = init_system(_account_service, _session_service, _audit_service)
    await _system_initializer.initialize()
    
    # Start cleanup service
    from manga_translator.server.core.cleanup_service import get_cleanup_service
    cleanup_service = get_cleanup_service()
    cleanup_service.start()
    
    logger.info("Services initialized successfully")
    add_log("服务器启动完成，所有服务已初始化", "INFO")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on server shutdown"""
    global _system_initializer

    import manga_translator.server.routes.v1_scraper as v1_scraper_routes
    await v1_scraper_routes.stop_alert_scheduler()
    
    # Stop cleanup service
    from manga_translator.server.core.cleanup_service import get_cleanup_service
    cleanup_service = get_cleanup_service()
    cleanup_service.stop()
    
    if _system_initializer:
        await _system_initializer.shutdown()
    
    logger.info("Server shutdown completed")

# Configure middleware
def _parse_cors_origins() -> list[str]:
    raw = os.getenv("MANGA_TRANSLATOR_CORS_ORIGINS", "*")
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or ["*"]


cors_origins = _parse_cors_origins()
allow_cors_credentials = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证错误，返回详细的错误信息"""
    error_details = []
    for error in exc.errors():
        error_details.append({
            'loc': error['loc'],
            'msg': error['msg'],
            'type': error['type']
        })
    
    print(f"[ERROR] Request validation failed for {request.url.path}")
    print(f"[ERROR] Validation errors: {json.dumps(error_details, indent=2)}")
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": error_details,
            "body": str(exc.body) if hasattr(exc, 'body') else None
        }
    )

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
dist_dir = os.path.join(static_dir, "dist")
dist_assets_dir = os.path.join(dist_dir, "assets")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Vue build defaults to absolute `/assets/*` in production output.
# Expose dist assets at root-level `/assets` so SPA scripts/styles resolve.
if os.path.isdir(dist_assets_dir):
    app.mount("/assets", StaticFiles(directory=dist_assets_dir), name="frontend-assets")

# Mount data/output directories used by Vue web frontend.
data_dir = os.path.join(os.path.dirname(__file__), "data")
raw_data_dir = os.path.join(data_dir, "raw")
result_data_dir = os.path.join(data_dir, "results")
os.makedirs(raw_data_dir, exist_ok=True)
os.makedirs(result_data_dir, exist_ok=True)
app.mount("/data", StaticFiles(directory=data_dir), name="data")
app.mount("/output", StaticFiles(directory=result_data_dir), name="output")

# Favicon route
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    favicon_path = os.path.join(static_dir, "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    raise HTTPException(status_code=404)


@app.get("/icon.png", include_in_schema=False)
async def frontend_icon():
    icon_path = os.path.join(dist_dir, "icon.png")
    if os.path.exists(icon_path):
        return FileResponse(icon_path)
    raise HTTPException(status_code=404)


@app.get("/manifest.webmanifest", include_in_schema=False)
async def frontend_manifest():
    manifest_path = os.path.join(dist_dir, "manifest.webmanifest")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path)
    raise HTTPException(status_code=404)


@app.get("/pwa-192x192.png", include_in_schema=False)
async def frontend_pwa_icon_192():
    icon_path = os.path.join(dist_dir, "pwa-192x192.png")
    if os.path.exists(icon_path):
        return FileResponse(icon_path)
    raise HTTPException(status_code=404)


@app.get("/pwa-512x512.png", include_in_schema=False)
async def frontend_pwa_icon_512():
    icon_path = os.path.join(dist_dir, "pwa-512x512.png")
    if os.path.exists(icon_path):
        return FileResponse(icon_path)
    raise HTTPException(status_code=404)


@app.get("/sw.js", include_in_schema=False)
async def frontend_service_worker():
    sw_path = os.path.join(dist_dir, "sw.js")
    if os.path.exists(sw_path):
        return FileResponse(sw_path)
    raise HTTPException(status_code=404)


@app.get("/workbox-{workbox_hash}.js", include_in_schema=False)
async def frontend_workbox_js(workbox_hash: str):
    workbox_path = os.path.join(dist_dir, f"workbox-{workbox_hash}.js")
    if os.path.exists(workbox_path):
        return FileResponse(workbox_path)
    raise HTTPException(status_code=404)


# Mount Qt UI locales for i18n (共享翻译文件)
locales_dir = os.path.join(os.path.dirname(__file__), "../../desktop_qt_ui/locales")
if os.path.exists(locales_dir):
    app.mount("/locales", StaticFiles(directory=locales_dir), name="locales")

# Mount result folder
if os.path.exists("../result"):
    app.mount("/result", StaticFiles(directory="../result"), name="result")

# Register route modules
app.include_router(translation_router)
app.include_router(admin_router)
app.include_router(config_router)
app.include_router(files_router)
app.include_router(web_router)
app.include_router(users_router)
app.include_router(sessions_router)
app.include_router(audit_router)
app.include_router(auth_router)
app.include_router(groups_router)
app.include_router(resources_router)
app.include_router(history_router)
app.include_router(quota_router)
app.include_router(config_management_router)
app.include_router(logs_router)
app.include_router(v1_manga_router)
app.include_router(v1_translate_router)
app.include_router(internal_translate_router)
app.include_router(v1_scraper_router)
app.include_router(v1_parser_router)
app.include_router(v1_settings_router)
app.include_router(v1_system_router)

# Internal API endpoint for instance registration
@app.post("/register", response_description="no response", tags=["internal-api"])
async def register_instance(instance: ExecutorInstance, req: Request, req_nonce: str = Header(alias="X-Nonce")):
    if req_nonce != nonce:
        raise HTTPException(401, detail="Invalid nonce")
    instance.ip = req.client.host
    executor_instances.register(instance)

def generate_nonce():
    return secrets.token_hex(16)

def start_translator_client_proc(host: str, port: int, nonce: str, params: Namespace):
    cmds = [
        sys.executable,
        '-m', 'manga_translator',
        'shared',
        '--host', host,
        '--port', str(port),
        '--nonce', nonce,
    ]
    if params.use_gpu:
        cmds.append('--use-gpu')
    if params.ignore_errors:
        cmds.append('--ignore-errors')
    if params.verbose:
        cmds.append('--verbose')
    if params.models_ttl:
        cmds.append('--models-ttl=%s' % params.models_ttl)
    if getattr(params, 'pre_dict', None):
        cmds.extend(['--pre-dict', params.pre_dict])
    if getattr(params, 'post_dict', None):
        cmds.extend(['--post-dict', params.post_dict])       
    base_path = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(base_path)
    proc = subprocess.Popen(cmds, cwd=parent)
    executor_instances.register(ExecutorInstance(ip=host, port=port))

    def handle_exit_signals(signal, frame):
        proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit_signals)
    signal.signal(signal.SIGTERM, handle_exit_signals)

    return proc

def prepare(args):
    global nonce
    
    # web 模式没有 nonce 参数，使用 getattr 避免 AttributeError
    args_nonce = getattr(args, 'nonce', None)
    if args_nonce is None:
        nonce = os.getenv('MT_WEB_NONCE', generate_nonce())
    else:
        nonce = args_nonce
    
    # start_instance 也可能不存在于某些模式
    if getattr(args, 'start_instance', False):
        return start_translator_client_proc(args.host, args.port + 1, nonce, args)
    
    folder_name= "upload-cache"
    if os.path.exists(folder_name):
        shutil.rmtree(folder_name)
    os.makedirs(folder_name)

def init_translator(use_gpu=False, verbose=False):
    """初始化翻译器（预留函数）"""
    # 这个函数用于预加载模型等初始化操作
    # 目前翻译器在首次请求时才会初始化
    pass


def _resolve_runtime_use_gpu(explicit: bool | None) -> bool:
    """Compatibility wrapper around task_manager runtime GPU resolver."""
    return task_manager._resolve_runtime_use_gpu(explicit)


def _ensure_runtime_server_config(explicit: bool | None = None) -> bool:
    """Ensure runtime config is initialized for direct uvicorn startup paths."""
    return task_manager._ensure_runtime_for_translator(
        explicit,
        source="startup_auto",
        force=False,
    )

def run_server(args):
    """启动 Web API 服务器（纯API模式，不带界面）"""
    import uvicorn
    
    resolved_use_gpu = task_manager._ensure_runtime_for_translator(
        getattr(args, 'use_gpu', None),
        source="run_server",
        force=True,
    )

    # 设置服务器配置（在 prepare 之前）
    task_manager.server_config['verbose'] = getattr(args, 'verbose', False)
    task_manager.server_config['models_ttl'] = getattr(args, 'models_ttl', 0)
    task_manager.server_config['retry_attempts'] = getattr(args, 'retry_attempts', None)
    
    # 历史字段保留但不再写入明文管理员密码
    task_manager.server_config['admin_password'] = None
    if config_manager.admin_settings.get('max_concurrent_tasks'):
        task_manager.server_config['max_concurrent_tasks'] = config_manager.admin_settings['max_concurrent_tasks']
    if config_manager.admin_settings.get('chapter_page_concurrency'):
        task_manager.server_config['chapter_page_concurrency'] = config_manager.admin_settings['chapter_page_concurrency']
    if config_manager.admin_settings.get('cleanup_interval_requests'):
        task_manager.server_config['cleanup_interval_requests'] = config_manager.admin_settings['cleanup_interval_requests']
    if config_manager.admin_settings.get('chapter_execution_mode'):
        task_manager.server_config['chapter_execution_mode'] = config_manager.admin_settings['chapter_execution_mode']
    if config_manager.admin_settings.get('runtime_profile'):
        task_manager.server_config['runtime_profile'] = config_manager.admin_settings['runtime_profile']
    
    print(
        f"[SERVER CONFIG] use_gpu={task_manager.server_config['use_gpu']}, "
        f"verbose={task_manager.server_config['verbose']}, "
        f"models_ttl={task_manager.server_config['models_ttl']}, "
        f"retry_attempts={task_manager.server_config['retry_attempts']}, "
        f"max_concurrent_tasks={task_manager.server_config['max_concurrent_tasks']}, "
        f"chapter_page_concurrency={task_manager.server_config['chapter_page_concurrency']}, "
        f"cleanup_interval_requests={task_manager.server_config['cleanup_interval_requests']}, "
        f"chapter_execution_mode={task_manager.server_config['chapter_execution_mode']}, "
        f"runtime_profile={task_manager.server_config['runtime_profile']}"
    )
    if not task_manager.server_config['use_gpu']:
        print("[SERVER CONFIG] use_gpu=False (set MT_USE_GPU=true or --use-gpu for GPU-aligned benchmarking)")
    else:
        print("[SERVER CONFIG] use_gpu=True (GPU path enabled)")
    
    # 初始化并发控制
    task_manager.init_semaphore()
    
    # web 模式不启动独立的翻译实例（与旧版本保持一致）
    args.start_instance = False
    proc = prepare(args)
    print("Nonce: "+nonce)
    try:
        # 增加超时配置以支持批量翻译（30分钟）
        uvicorn.run(
            app, 
            host=args.host, 
            port=args.port,
            timeout_keep_alive=1800,  # 保持连接30分钟
            timeout_graceful_shutdown=30  # 优雅关闭超时30秒
        )
    except Exception:
        if proc:
            proc.terminate()

def main(args):
    """启动 Web UI 服务器（带界面模式）"""
    # ui 模式和 web 模式使用相同的实现
    run_server(args)

if __name__ == '__main__':
    from manga_translator.args import parse_arguments
    args = parse_arguments()
    main(args)
