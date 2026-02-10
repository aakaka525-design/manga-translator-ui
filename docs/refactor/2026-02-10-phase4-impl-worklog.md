# 2026-02-10 Phase4 S1 Implementation Worklog

## 记录模板（每条任务必须填写）
- TASK-ID:
- 状态:
- 改动文件:
- 接口影响:
- 验证命令:
- 验证结果:
- 提交哈希:

## TASK-035
- TASK-ID: TASK-035
- 状态: completed
- 改动文件: `docs/plans/2026-02-10-phase4-s1-implementation.md`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`, `docs/api/2026-02-10-v1-scraper-phase4-s1-contract.md`, `docs/refactor/INDEX.md`
- 接口影响: 无
- 验证命令: `ls docs/plans docs/refactor docs/api`
- 验证结果: pass
- 提交哈希: b3a7b61

## TASK-036
- TASK-ID: TASK-036
- 状态: completed
- 改动文件: `manga_translator/server/core/config_manager.py`
- 接口影响: 默认配置新增 `scraper_alerts`
- 验证命令: `pytest -q tests/test_v1_scraper_phase4.py -k config`
- 验证结果: pass
- 提交哈希: 4929a86

## TASK-037
- TASK-ID: TASK-037
- 状态: completed
- 改动文件: `manga_translator/server/scraper_v1/task_store.py`
- 接口影响: SQLite 新增 `scraper_alerts` 表、告警查询、队列统计
- 验证命令: `pytest -q tests/test_v1_scraper_phase4.py -k 'alert_store or queue_stats or migration'`
- 验证结果: pass
- 提交哈希: 4929a86

## TASK-038
- TASK-ID: TASK-038
- 状态: completed
- 改动文件: `manga_translator/server/scraper_v1/alerts.py`, `manga_translator/server/scraper_v1/__init__.py`
- 接口影响: 告警规则与 webhook 重试发送能力新增
- 验证命令: `pytest -q tests/test_v1_scraper_phase4.py -k 'rules or webhook or cooldown'`
- 验证结果: pass
- 提交哈希: 4929a86

## TASK-039
- TASK-ID: TASK-039
- 状态: completed
- 改动文件: `manga_translator/server/routes/admin.py`
- 接口影响: 新增 `/admin/scraper/health`、`/admin/scraper/alerts`、`/admin/scraper/alerts/test-webhook`、`/admin/scraper/queue/stats`
- 验证命令: `pytest -q tests/test_v1_scraper_phase4.py -k 'admin and health and alerts and queue and auth'`
- 验证结果: pass
- 提交哈希: 4929a86

## TASK-040
- TASK-ID: TASK-040
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_scraper.py`
- 接口影响: `GET /api/v1/scraper/task/{task_id}` 扩展 `queue_status/enqueued_at/dequeued_at/worker_id`
- 验证命令: `pytest -q tests/test_v1_scraper_phase4.py -k 'task_status and queue_status and compatibility'`
- 验证结果: pass
- 提交哈希: 4929a86

## TASK-041
- TASK-ID: TASK-041
- 状态: completed
- 改动文件: `manga_translator/server/main.py`, `manga_translator/server/routes/v1_scraper.py`
- 接口影响: 启动/关闭接入告警调度与退化健康状态
- 验证命令: `pytest -q tests/test_v1_scraper_phase4.py -k 'startup or shutdown or scheduler'`
- 验证结果: pass
- 提交哈希: 4929a86

## TASK-042
- TASK-ID: TASK-042
- 状态: completed
- 改动文件: `frontend/src/stores/adminScraper.js`
- 接口影响: 新增 `fetchHealth/fetchAlerts/fetchQueueStats/sendTestWebhook` 与错误码映射
- 验证命令: `cd frontend && npm test -- --run -t 'admin scraper store'`
- 验证结果: pass
- 提交哈希: 9cd1c65

## TASK-043
- TASK-ID: TASK-043
- 状态: completed
- 改动文件: `frontend/src/views/AdminView.vue`
- 接口影响: `/admin` 新增健康、告警、队列统计与 webhook 测试区块
- 验证命令: `cd frontend && npm test -- --run -t 'admin scraper panel'`
- 验证结果: pass
- 提交哈希: 9cd1c65

## TASK-044
- TASK-ID: TASK-044
- 状态: completed
- 改动文件: `tests/test_v1_scraper_phase4.py`, `tests/test_v1_scraper_phase3.py`
- 接口影响: 后端 phase4 告警与兼容性测试覆盖新增
- 验证命令: `pytest -q tests/test_v1_routes.py tests/test_v1_scraper_phase2.py tests/test_v1_scraper_phase3.py tests/test_v1_scraper_phase4.py`
- 验证结果: pass
- 提交哈希: 4929a86

## TASK-045
- TASK-ID: TASK-045
- 状态: completed
- 改动文件: `frontend/tests/admin_scraper_store_phase4.test.js`, `frontend/tests/admin_scraper_alerts_panel.test.js`, `frontend/tests/admin_scraper_health_queue.test.js`, `frontend/tests/admin_scraper_panel.test.js`
- 接口影响: 前端管理页监控与 webhook 测试行为测试新增
- 验证命令: `cd frontend && npm test -- --run && npm run build`
- 验证结果: pass
- 提交哈希: 9cd1c65

## TASK-046
- TASK-ID: TASK-046
- 状态: completed
- 改动文件: `docs/refactor/2026-02-10-phase4-impl-worklog.md`, `docs/api/2026-02-10-v1-scraper-phase4-s1-contract.md`, `docs/plans/2026-02-10-phase4-s1-implementation.md`, `docs/refactor/INDEX.md`, `README.md`, `doc/CLI_USAGE.md`
- 接口影响: 文档闭环与交付规则更新
- 验证命令: `git status --short && git log --oneline -n 20 && git ls-remote --heads personal`
- 验证结果: pass
- 提交哈希: b3a7b61

## FIX-001
- TASK-ID: FIX-001
- 状态: completed
- 改动文件: `manga_translator/server/routes/admin.py`, `tests/test_v1_scraper_phase4.py`
- 接口影响: `/admin/scraper/*` 的 `X-Admin-Token` 兼容由声明变为真实可用
- 验证命令: `pytest -q tests/test_v1_scraper_phase4.py -k 'legacy_token'`
- 验证结果: pass
- 提交哈希: N/A

## FIX-002
- TASK-ID: FIX-002
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_scraper.py`, `tests/test_v1_scraper_phase4.py`
- 接口影响: `/api/v1/scraper/download` 在 task store 写失败时回滚内存任务，避免幽灵 pending
- 验证命令: `pytest -q tests/test_v1_scraper_phase4.py -k 'store_failure'`
- 验证结果: pass
- 提交哈希: N/A

## FIX-003
- TASK-ID: FIX-003
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_scraper.py`, `tests/test_v1_scraper_phase4.py`
- 接口影响: `retry_count` 改为真实重试次数；`error_code` 仅在可重试耗尽时为 `SCRAPER_RETRY_EXHAUSTED`
- 验证命令: `pytest -q tests/test_v1_scraper_phase4.py -k 'non_retryable'`
- 验证结果: pass
- 提交哈希: N/A

## FIX-004
- TASK-ID: FIX-004
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_parser.py`, `tests/test_v1_scraper_phase4.py`
- 接口影响: parser async 路由通过 `asyncio.to_thread` 执行阻塞抓取，避免直接阻塞事件循环
- 验证命令: `pytest -q tests/test_v1_scraper_phase4.py -k 'thread_offload'`
- 验证结果: pass
- 提交哈希: N/A

## FIX-005
- TASK-ID: FIX-005
- 状态: completed
- 改动文件: `tests/test_v1_scraper_phase4.py`
- 接口影响: 新增 5 个回归用例覆盖 legacy token、store 原子性、重试语义、parser 线程卸载
- 验证命令: `pytest -q tests/test_v1_routes.py tests/test_v1_scraper_phase2.py tests/test_v1_scraper_phase3.py tests/test_v1_scraper_phase4.py`
- 验证结果: pass
- 提交哈希: N/A

## FIX-006
- TASK-ID: FIX-006
- 状态: completed
- 改动文件: `docs/api/2026-02-10-v1-scraper-phase4-s1-contract.md`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`, `docs/refactor/INDEX.md`
- 接口影响: 文档补齐 `retry_count/error_code` 语义与 `/admin/scraper/*` legacy token 兼容真实行为
- 验证命令: `rg -n 'retry_count|SCRAPER_RETRY_EXHAUSTED|SCRAPER_DOWNLOAD_FAILED|X-Admin-Token|FIX-00' docs/api/2026-02-10-v1-scraper-phase4-s1-contract.md docs/refactor/2026-02-10-phase4-impl-worklog.md docs/refactor/INDEX.md`
- 验证结果: pass
- 提交哈希: N/A

## TASK-CHECK-001
- TASK-ID: TASK-CHECK-001
- 状态: completed
- 改动文件: `scripts/check_runtime_deps.py`, `tests/test_runtime_deps_check.py`
- 接口影响: 新增开发者前置检查命令 `python scripts/check_runtime_deps.py`
- 验证命令: `pytest -q tests/test_runtime_deps_check.py`
- 验证结果: pass
- 提交哈希: N/A

## TASK-CHECK-002
- TASK-ID: TASK-CHECK-002
- 状态: completed
- 改动文件: `README.md`, `doc/INSTALLATION.md`, `doc/CLI_USAGE.md`
- 接口影响: 无运行时接口变更；启动文档统一为 venv -> requirements -> `check_runtime_deps` -> web
- 验证命令: `rg -n 'check_runtime_deps.py|python -m manga_translator web|X-Session-Token' README.md doc/INSTALLATION.md doc/CLI_USAGE.md`
- 验证结果: pass
- 提交哈希: N/A

## TASK-CHECK-003
- TASK-ID: TASK-CHECK-003
- 状态: completed
- 改动文件: `docs/api/2026-02-10-v1-api-contract.md`, `doc/CLI_USAGE.md`
- 接口影响: 文档补齐 `/api/v1/settings*` 与 `/api/v1/system/logs` 契约说明
- 验证命令: `rg -n '/api/v1/settings|/api/v1/system/logs|X-Session-Token|X-Admin-Token' docs/api/2026-02-10-v1-api-contract.md doc/CLI_USAGE.md`
- 验证结果: pass
- 提交哈希: N/A

## TASK-CHECK-004
- TASK-ID: TASK-CHECK-004
- 状态: completed
- 改动文件: `tests/test_runtime_deps_check.py`
- 接口影响: 无
- 验证命令: `pytest -q tests/test_runtime_deps_check.py`
- 验证结果: pass
- 提交哈希: N/A

## TASK-CHECK-005
- TASK-ID: TASK-CHECK-005
- 状态: completed
- 改动文件: `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无
- 验证命令: `rg -n 'TASK-CHECK-00|TASK-ID|提交哈希' docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 验证结果: pass
- 提交哈希: N/A

## AUDIT-FIX-001
- TASK-ID: AUDIT-FIX-001
- 状态: completed
- 改动文件: `manga_translator/server/core/auth.py`, `manga_translator/server/routes/admin.py`, `manga_translator/server/routes/web.py`, `manga_translator/server/core/config_manager.py`, `manga_translator/server/main.py`
- 接口影响: 旧端点 `/admin/setup`、`/admin/login`、`/admin/change-password`、`/user/login` 改为优先 bcrypt 哈希校验；保留 legacy 明文兼容并在成功登录后自动迁移为哈希；`server_config` 不再写入明文管理员密码
- 验证命令: `pytest -q tests/test_security_audit_fixes.py`
- 验证结果: pass（5 passed）
- 提交哈希: N/A

## AUDIT-FIX-002
- TASK-ID: AUDIT-FIX-002
- 状态: completed
- 改动文件: `manga_translator/server/routes/web.py`, `tests/test_security_audit_fixes.py`
- 接口影响: `/result/{folder_name}/final.png`、`/results/{folder_name}` 增加目录名校验与路径规范化，阻断 `..` 路径遍历
- 验证命令: `pytest -q tests/test_security_audit_fixes.py -k traversal`
- 验证结果: pass
- 提交哈希: N/A

## AUDIT-FIX-003
- TASK-ID: AUDIT-FIX-003
- 状态: completed
- 改动文件: `manga_translator/server/main.py`
- 接口影响: CORS 改为环境变量可配置；当 `allow_origins` 包含 `*` 时强制 `allow_credentials=False`
- 验证命令: `python - <<'PY'\nfrom manga_translator.server import main\ncors = [m for m in main.app.user_middleware if m.cls.__name__ == 'CORSMiddleware'][0]\nprint(cors.kwargs.get('allow_origins'), cors.kwargs.get('allow_credentials'))\nPY`
- 验证结果: pass（`['*'] False`）
- 提交哈希: N/A

## AUDIT-FIX-004
- TASK-ID: AUDIT-FIX-004
- 状态: completed
- 改动文件: `tests/test_security_audit_fixes.py`
- 接口影响: 无（新增安全回归测试）
- 验证命令: `pytest -q tests/test_security_audit_fixes.py tests/test_mask_refinement_fallback.py tests/test_runtime_deps_check.py tests/test_v1_routes.py tests/test_v1_scraper_phase2.py tests/test_v1_scraper_phase3.py tests/test_v1_scraper_phase4.py`
- 验证结果: pass（58 passed）
- 提交哈希: N/A

## BUGFIX-TRANSLATE-001
- TASK-ID: BUGFIX-TRANSLATE-001
- 状态: completed
- 改动文件: `manga_translator/server/core/library_service.py`, `manga_translator/server/routes/v1_translate.py`, `tests/test_v1_routes.py`
- 接口影响: `/api/v1/manga/{manga_id}/chapter/{chapter_id}` 的 `translated_url` 增加 `?v=<mtime>` 缓存戳并忽略与原图完全一致的伪结果；`/api/v1/translate/page` 在输出无可见变化时返回 `409`（不再误判完成）
- 验证命令: `pytest -q tests/test_v1_routes.py -k 'ignore_identical_result_copy or output_url_contains_cache_buster or no_change_result_is_not_counted_as_success or no_visible_change'`
- 验证结果: pass（4 passed）
- 提交哈希: N/A

## BUGFIX-TRANSLATE-002
- TASK-ID: BUGFIX-TRANSLATE-002
- 状态: completed
- 改动文件: `frontend/src/views/ReaderView.vue`, `frontend/tests/reader_mobile_actions.test.js`
- 接口影响: 前端阅读页“重新翻译”成功后立即刷新章节数据，避免使用旧缓存 URL 导致“显示成功但图未更新”
- 验证命令: `cd frontend && npm test -- --run tests/reader_mobile_actions.test.js -t 'reloads chapter pages after retranslate request succeeds'`
- 验证结果: pass
- 提交哈希: N/A

## BUGFIX-TRANSLATE-003
- TASK-ID: BUGFIX-TRANSLATE-003
- 状态: completed
- 改动文件: `manga_translator/rendering/__init__.py`
- 接口影响: 渲染阶段多边形并集增加几何修复与重试，降低 `TopologyException: side location conflict` 对排版路径的干扰（保留 fallback）
- 验证命令: `pytest -q tests/test_v1_routes.py tests/test_v1_scraper_phase2.py tests/test_v1_scraper_phase3.py tests/test_v1_scraper_phase4.py tests/test_security_audit_fixes.py tests/test_runtime_deps_check.py tests/test_mask_refinement_fallback.py`
- 验证结果: pass（62 passed）
- 提交哈希: N/A

## BUGFIX-TRANSLATE-004
- TASK-ID: BUGFIX-TRANSLATE-004
- 状态: completed
- 改动文件: `manga_translator/server/core/library_service.py`（行为验证）
- 接口影响: 实图验证确认“原图拷贝”被识别为 pending；“真实变更图”被识别为 translated 且返回带版本戳 URL
- 验证命令: `python - <<'PY' (使用临时目录调用 LibraryService.get_chapter，并对 real image 做像素差异统计) PY`
- 验证结果: pass（`case_a_status=pending`, `case_b_status=translated`, `actual_test_nonzero_pixels=764129`）
- 提交哈希: N/A

## AUDIT-FIX-005
- TASK-ID: AUDIT-FIX-005
- 状态: completed
- 改动文件: `manga_translator/server/core/auth.py`, `manga_translator/server/routes/admin.py`, `manga_translator/server/routes/web.py`, `tests/test_security_audit_fixes.py`
- 接口影响: legacy 端点 `/admin/login`、`/admin/change-password`、`/user/login` 新增失败速率限制（5 分钟窗口/10 次），超限返回 `429 RATE_LIMIT_EXCEEDED`
- 验证命令: `pytest -q tests/test_security_audit_fixes.py -k 'rate_limit_blocks_after_repeated_failures'`
- 验证结果: pass（3 passed）
- 提交哈希: N/A

## AUDIT-FIX-006
- TASK-ID: AUDIT-FIX-006
- 状态: completed
- 改动文件: `.github/workflows/build-and-release.yml`, `.github/workflows/docker-build-push.yml`
- 接口影响: 无运行时接口变化；CI 在构建前新增后端测试门禁
- 验证命令: `python - <<'PY'\nfrom pathlib import Path\nfor p in ['.github/workflows/build-and-release.yml','.github/workflows/docker-build-push.yml']:\n    txt = Path(p).read_text(encoding='utf-8')\n    assert 'pytest -q' in txt\nprint('workflow-test-gates-ok')\nPY`
- 验证结果: pass（workflow-test-gates-ok）
- 提交哈希: N/A

## AUDIT-FIX-007
- TASK-ID: AUDIT-FIX-007
- 状态: completed
- 改动文件: `docs/2026-02-10-project-audit.md`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无运行时接口变化；审计报告状态与实际修复保持一致（补充 P1-6 与 CI 门禁回填）
- 验证命令: `rg -n '旧端点无速率限制|CI 无测试步骤|RATE_LIMIT_EXCEEDED|test-suite|test-before-build' docs/2026-02-10-project-audit.md`
- 验证结果: pass
- 提交哈希: N/A

## AUDIT-FIX-008
- TASK-ID: AUDIT-FIX-008
- 状态: completed
- 改动文件: `docs/2026-02-10-project-audit.md`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无运行时接口变化；将审计文档 P0 标题改为“历史发现（已修复）”，避免与修复进展表冲突
- 验证命令: `rg -n 'P0 — 历史发现（已修复）|修复进展（2026-02-10 当日回填）' docs/2026-02-10-project-audit.md`
- 验证结果: pass
- 提交哈希: N/A

## AUDIT-FIX-009
- TASK-ID: AUDIT-FIX-009
- 状态: completed
- 改动文件: `tests/test_core_services.py`, `docs/2026-02-10-project-audit.md`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无运行时接口变化；新增核心服务回归测试覆盖 `AccountService`/`SessionService`/`PermissionService`
- 验证命令: `pytest -q tests/test_core_services.py`
- 验证结果: pass（6 passed）
- 提交哈希: N/A

## AUDIT-FIX-010
- TASK-ID: AUDIT-FIX-010
- 状态: completed
- 改动文件: `.github/workflows/build-and-release.yml`, `.github/workflows/docker-build-push.yml`, `docs/2026-02-10-project-audit.md`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无运行时接口变化；CI 测试门禁升级为 `pytest -q tests`，确保新增后端测试默认纳入门禁
- 验证命令: `python - <<'PY'\nfrom pathlib import Path\nfor p in ['.github/workflows/build-and-release.yml','.github/workflows/docker-build-push.yml']:\n    txt = Path(p).read_text(encoding='utf-8')\n    assert 'pytest -q tests' in txt\nprint('ci-test-gate-all-tests-ok')\nPY`
- 验证结果: pass（ci-test-gate-all-tests-ok）
- 提交哈希: N/A

## AUDIT-FIX-011
- TASK-ID: AUDIT-FIX-011
- 状态: completed
- 改动文件: `tests/test_security_support_services.py`, `docs/2026-02-10-project-audit.md`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无运行时接口变化；新增 `SessionSecurityService`/`AuditService` 关键路径单测（token 格式校验、所有权校验、枚举限流、审计筛选/导出/轮转）
- 验证命令: `pytest -q tests/test_security_support_services.py`
- 验证结果: pass（4 passed）
- 提交哈希: N/A

## AUDIT-FIX-012
- TASK-ID: AUDIT-FIX-012
- 状态: completed
- 改动文件: `tests/test_middleware_and_quota_services.py`, `docs/2026-02-10-project-audit.md`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无运行时接口变化；新增 `middleware` 与 `QuotaManagementService` 主流程回归测试（鉴权/授权错误码、并发与配额限制、用户组配额继承）
- 验证命令: `pytest -q tests/test_middleware_and_quota_services.py`
- 验证结果: pass（8 passed）
- 提交哈希: N/A

## AUDIT-FIX-013
- TASK-ID: AUDIT-FIX-013
- 状态: completed
- 改动文件: `manga_translator/server/core/group_service.py`, `tests/test_middleware_and_quota_services.py`, `docs/2026-02-10-project-audit.md`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无对外 API 变更；修复 `QuotaManagementService` 调用 `GroupService.get_group_config` 缺失导致的用户组配额路径异常（补充兼容方法）
- 验证命令: `pytest -q tests/test_middleware_and_quota_services.py -k 'applies_group_quota_limits_when_user_has_group'`
- 验证结果: pass
- 提交哈希: N/A

## BUGFIX-TRANSLATE-005
- TASK-ID: BUGFIX-TRANSLATE-005
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`, `tests/test_v1_routes.py`, `docs/api/2026-02-10-v1-api-contract.md`, `docs/2026-02-10-project-audit.md`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: `/api/v1/translate/page` 新增“无文本区域”失败语义（`409 no detected text regions`）；`/api/v1/translate/chapter` 仅在 `regions_count > 0` 且有可见变化时计入成功；`target_language` 增加短码归一化并默认 `CHS`
- 验证命令: `pytest -q tests/test_v1_routes.py`
- 验证结果: pass（19 passed）
- 提交哈希: N/A

## BUGFIX-TRANSLATE-006
- TASK-ID: BUGFIX-TRANSLATE-006
- 状态: completed
- 改动文件: `frontend/src/views/MangaView.vue`, `frontend/src/views/ReaderView.vue`, `frontend/tests/manga_delete_actions.test.js`, `frontend/tests/reader_mobile_actions.test.js`
- 接口影响: 前端章节翻译与单页重翻译请求补充 `source_language/target_language`（从设置读取），避免回退到后端默认语言导致“成功但无翻译内容”
- 验证命令: `cd frontend && npm test -- --run tests/reader_mobile_actions.test.js tests/manga_delete_actions.test.js`
- 验证结果: pass（12 passed）
- 提交哈希: N/A

## BUGFIX-TRANSLATE-007
- TASK-ID: BUGFIX-TRANSLATE-007
- 状态: completed
- 改动文件: `manga_translator/server/data/results/isekai-dragondick-knight-commander/chapter-1/001.jpg`（实图验证产物）
- 接口影响: 无接口变更；完成“后端输出目录 -> `/api/v1/manga` -> `/output/*` 静态读取”实图链路验证
- 验证命令: `python - <<'PY' (对真实 raw 图片写入可见标记后，调用 /api/v1/manga/.../chapter/... 并请求 translated_url) PY`
- 验证结果: pass（`page_status=translated`, `translated_url=/output/...`, `fetch_status=200`）
- 提交哈希: N/A

## BUGFIX-TRANSLATE-008
- TASK-ID: BUGFIX-TRANSLATE-008
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`, `tests/test_v1_routes.py`, `frontend/src/views/MangaView.vue`, `docs/2026-02-10-project-audit.md`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: `/api/v1/translate/page` 修复 RGBA 结果写入 JPEG 失败回退（`cannot write mode RGBA as JPEG`）；失败路径清理同 stem 历史译图，避免 `/api/v1/manga/.../chapter/...` 误判 translated；翻译超时改为环境变量 `MANGA_TRANSLATE_CONTEXT_TIMEOUT_SEC`（默认 600s）；章节按钮提示从“已启动成功”改为“已提交等待结果”
- 验证命令: `pytest -q tests/test_v1_scraper_phase2.py tests/test_v1_routes.py tests/test_v1_scraper_phase3.py tests/test_v1_scraper_phase4.py && cd frontend && npm test -- --run && npm run build && python - <<'PY' (TestClient 调用 /api/v1/translate/page 对实图裁剪样本验证 PAGE_STATUS=200, output_changed=True) PY`
- 验证结果: pass（后端 59 passed；前端 49 passed；build 成功；实图 API 验证 `PAGE_STATUS=200`、`output_changed=True`、`CHAPTER_PAGE_STATUS=translated`）
- 提交哈希: N/A

## BUGFIX-TRANSLATE-009
- TASK-ID: BUGFIX-TRANSLATE-009
- 状态: completed
- 改动文件: `examples/config.json`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无 API 变更；调大默认渲染字体参数（`render.font_size_offset=2`, `render.font_size_minimum=14`, `render.line_spacing=0.95`, `render.font_scale_ratio=1.2`），改善“翻译文字偏小”观感
- 验证命令: `pytest -q tests/test_v1_routes.py -k 'translate_page_returns_503_when_fallback_used or translate_single_image_converts_rgba_result_for_jpeg_output' && python - <<'PY' (同一张真实样本生成 baseline/tuned 对比并统计像素差) PY`
- 验证结果: pass（2 passed；实图对比 `DIFF_SOURCE_BASELINE=171292`, `DIFF_SOURCE_TUNED=171331`, `DIFF_BASELINE_TUNED=12676`，调参后输出有效变化且翻译成功）
- 提交哈希: N/A

## BUGFIX-TRANSLATE-010
- TASK-ID: BUGFIX-TRANSLATE-010
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`, `manga_translator/server/request_extraction.py`, `tests/test_v1_routes.py`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: `/api/v1/translate/page` 与 `/api/v1/translate/chapter` 执行语义向 CLI 对齐（默认不再强制 600s 超时；`attempts` 优先读取 server config `retry_attempts`，否则保持 translator/CLI 语义）；翻译参数中的 `use_gpu` 与 server 配置对齐；请求图像解码改为 eager load，避免超时取消时出现输入图像提前关闭导致的链路不一致。
- 验证命令: `pytest -q tests/test_v1_routes.py && pytest -q tests/test_v1_routes.py tests/test_v1_scraper_phase2.py tests/test_v1_scraper_phase3.py tests/test_v1_scraper_phase4.py && cd frontend && npm test -- --run && npm run build && python /tmp/mt_repro2_api_once.py && python /tmp/mt_repro2_metrics.py`
- 验证结果: pass（后端 `61 passed`；前端 `49 passed`；build 成功；实图对照：Qt/CLI `real 61.39s`，API `elapsed_sec=217.03`，两侧均产出图片，路径分别为 `/tmp/mt_repro2/qt_out/001.jpg` 与 `/tmp/mt_repro2/api_case/results/bench/ch1/001.jpg`，指标 `mean_abs_diff`：Qt `4.328` / API `4.6609`）
- 提交哈希: `b1b679f`

## BUGFIX-TRANSLATE-011
- TASK-ID: BUGFIX-TRANSLATE-011
- 状态: completed
- 改动文件: `manga_translator/translators/common.py`, `tests/test_translator_attempt_state.py`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无新增端点；修复 `gemini_hq/openai_hq` 等翻译器共享实例下“全局尝试计数”跨并发请求污染问题。`_global_attempt_count/_max_total_attempts` 改为基于 `ContextVar` 的请求隔离状态，避免线程B耗尽重试额度后线程A提前命中“达到最大尝试次数”。
- 验证命令: `pytest -q tests/test_translator_attempt_state.py && pytest -q tests/test_v1_routes.py tests/test_v1_scraper_phase2.py tests/test_v1_scraper_phase3.py tests/test_v1_scraper_phase4.py tests/test_translator_attempt_state.py`
- 验证结果: pass（新增并发隔离用例 `2 passed`；后端回归 `64 passed`）
- 提交哈希: N/A

## BUGFIX-TRANSLATE-012
- TASK-ID: BUGFIX-TRANSLATE-012
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`, `tests/test_v1_routes.py`, `tests/test_v1_translate_perf_quick.py`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无新增端点；修复 `/api/v1/translate/chapter` 在 `chapter_execution_mode=auto` 且翻译器为 `gemini_hq` 时被强制 `single_page` 的行为，改为多页默认走 `batch_pipeline`，与 CLI 批量链路对齐；单页章节仍保持 `single_page`。
- 验证命令: `pytest -q tests/test_v1_routes.py -k chapter_execution_mode_auto_prefers_batch_pipeline_for_gemini_hq && pytest -q tests/test_v1_translate_perf_quick.py -k \"chapter_auto_mode_prefers_batch_pipeline_for_gemini_hq or mock_parallel_candidate_beats_serial_baseline or mock_parallel_with_tail_beats_serial or metrics_shape_is_complete\" && pytest -q tests/test_v1_translate_perf_quick.py tests/test_v1_routes.py tests/test_v1_scraper_phase2.py tests/test_v1_scraper_phase3.py tests/test_v1_scraper_phase4.py tests/test_translator_attempt_state.py`
- 验证结果: pass（新增模式回归与性能脚本回归通过；后端组合回归 `74 passed, 1 skipped`）
- 提交哈希: N/A

## BUGFIX-TRANSLATE-013
- TASK-ID: BUGFIX-TRANSLATE-013
- 状态: completed
- 改动文件: `manga_translator/server/request_extraction.py`, `tests/test_request_extraction_event_loop.py`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无新增端点；优化 API 翻译执行链路为“线程级事件循环复用”，修复每次请求创建/关闭 event loop 的开销。`_run_translate_sync/_run_translate_batch_sync` 改为复用当前翻译线程 loop，并保留 pending task 清理与请求级 cleanup 行为。
- 验证命令: `pytest -q tests/test_request_extraction_event_loop.py && pytest -q tests/test_v1_routes.py tests/test_v1_scraper_phase2.py tests/test_v1_scraper_phase3.py tests/test_v1_scraper_phase4.py tests/test_translator_attempt_state.py && python - <<'PY' (500 次 _run_translate_sync 压测，统计 loops_created/ms_per_call) PY`
- 验证结果: pass（loop 复用测试 `2 passed`；后端回归 `65 passed`；压测 `loops_created=1`, `ms_per_call=0.032`）
- 提交哈希: N/A

## BUGFIX-TRANSLATE-014
- TASK-ID: BUGFIX-TRANSLATE-014
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`, `tests/test_v1_routes.py`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无新增端点；优化翻译结果“可见变化”判定开销。对 `regions_count > 0` 的页面不再执行全图像素差分，直接标记 `output_changed=True`；仅在无文本区域时执行 `_image_has_visible_changes` 兜底判定，保持“无文本区域失败”语义。
- 验证命令: `pytest -q tests/test_v1_routes.py -k \"skips_pixel_diff_when_regions_detected or uses_pixel_diff_when_no_regions\" && pytest -q tests/test_v1_routes.py tests/test_v1_scraper_phase2.py tests/test_v1_scraper_phase3.py tests/test_v1_scraper_phase4.py tests/test_translator_attempt_state.py tests/test_request_extraction_event_loop.py && python - <<'PY' (2000x3000 样本测 _image_has_visible_changes 开销与 fast-path 分支对照) PY`
- 验证结果: pass（新增像素差分分支测试 `2 passed`；后端回归 `69 passed`；样本测得 `diff_ms_per_call=43.729`，fast-path 分支近似 `0`）
- 提交哈希: N/A

## BUGFIX-TRANSLATE-015
- TASK-ID: BUGFIX-TRANSLATE-015
- 状态: completed
- 改动文件: `manga_translator/translators/common.py`, `tests/test_translator_attempt_state.py`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无新增端点；修复全局重试计数边界语义：`attempts=1` 现在允许执行 1 次真实翻译请求，不再在首轮直接命中“达到最大尝试次数（Unknown error）”导致 API 503 回退。
- 验证命令: `pytest -q tests/test_translator_attempt_state.py -k \"limit_is_one or single_attempt_limit\" && pytest -q tests/test_translator_attempt_state.py tests/test_request_extraction_event_loop.py tests/test_v1_translate_perf_quick.py && pytest -q tests/test_v1_routes.py tests/test_v1_scraper_phase2.py tests/test_v1_scraper_phase3.py tests/test_v1_scraper_phase4.py`
- 验证结果: pass（新增 attempts=1 边界回归通过；翻译链路与 scraper 主回归通过）
- 提交哈希: a3fcfe0
