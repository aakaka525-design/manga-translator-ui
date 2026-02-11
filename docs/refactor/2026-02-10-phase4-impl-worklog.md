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
- 提交哈希: 4327862

## FIX-002
- TASK-ID: FIX-002
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_scraper.py`, `tests/test_v1_scraper_phase4.py`
- 接口影响: `/api/v1/scraper/download` 在 task store 写失败时回滚内存任务，避免幽灵 pending
- 验证命令: `pytest -q tests/test_v1_scraper_phase4.py -k 'store_failure'`
- 验证结果: pass
- 提交哈希: 4327862

## FIX-003
- TASK-ID: FIX-003
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_scraper.py`, `tests/test_v1_scraper_phase4.py`
- 接口影响: `retry_count` 改为真实重试次数；`error_code` 仅在可重试耗尽时为 `SCRAPER_RETRY_EXHAUSTED`
- 验证命令: `pytest -q tests/test_v1_scraper_phase4.py -k 'non_retryable'`
- 验证结果: pass
- 提交哈希: 4327862

## FIX-004
- TASK-ID: FIX-004
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_parser.py`, `tests/test_v1_scraper_phase4.py`
- 接口影响: parser async 路由通过 `asyncio.to_thread` 执行阻塞抓取，避免直接阻塞事件循环
- 验证命令: `pytest -q tests/test_v1_scraper_phase4.py -k 'thread_offload'`
- 验证结果: pass
- 提交哈希: 808e00a

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

## BUGFIX-TRANSLATE-016
- TASK-ID: BUGFIX-TRANSLATE-016
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`, `manga_translator/server/request_extraction.py`, `manga_translator/server/main.py`, `manga_translator/args.py`, `manga_translator/rendering/__init__.py`, `tests/test_v1_translate_pipeline.py`, `tests/test_v1_translate_concurrency.py`, `tests/test_render_polygon_stability.py`, `tests/test_v1_translate_perf_quick.py`, `test_vue_api_path.py`
- 接口影响: 无新增端点；`/api/v1/translate/chapter` 与页面进度事件新增可选诊断字段（`pipeline`、`stage_elapsed_ms`、`failure_stage`）；`single_page` 模式页并发强制为 1（稳定性优先）；`web` 模式 `use_gpu` 默认值改为“未显式指定时跟随配置文件”；渲染并集路径新增 `_safe_union_polygons` 容错。
- 验证命令: `pytest -q tests/test_v1_translate_pipeline.py tests/test_v1_translate_concurrency.py tests/test_render_polygon_stability.py && pytest -q tests/test_v1_routes.py tests/test_v1_translate_perf_quick.py tests/test_request_extraction_event_loop.py tests/test_translator_attempt_state.py tests/test_v1_translate_pipeline.py tests/test_v1_translate_concurrency.py tests/test_render_polygon_stability.py`
- 验证结果: pass（翻译链路新增/既有回归通过，稳定性策略与诊断字段生效）
- 提交哈希: N/A

## BUGFIX-TRANSLATE-017
- TASK-ID: BUGFIX-TRANSLATE-017
- 状态: completed
- 改动文件: `frontend/src/api/index.js`, `frontend/src/views/ReaderView.vue`, `frontend/tests/reader_mobile_actions.test.js`
- 接口影响: 无新增端点；前端长任务交互优化：翻译 API 请求超时策略调整（章节提交 60s、单页重翻译不限时），阅读页重翻译成功后新增“后端结果可读性”二次确认提示，避免“显示成功但页面无变化”的误导反馈。
- 验证命令: `cd frontend && npm test -- --run && npm run build`
- 验证结果: pass（前端 49/49；构建成功）
- 提交哈希: N/A

## BUGFIX-TRANSLATE-018
- TASK-ID: BUGFIX-TRANSLATE-018
- 状态: completed
- 改动文件: `docs/2026-02-10-project-audit.md`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无运行时接口变化；补充 Qt/CLI 等价链路 vs Vue/API 等价链路实图对照结论（同一张 `001.jpg`）与耗时/产图指标。
- 验证命令: `python - <<'PY' (同一输入图分别跑 CLI 核心 translate_batch 与 API 核心 _translate_single_image，记录 elapsed/output/md5/nonzero diff) PY`
- 验证结果: pass（CLI `54.058s`，API `48.590s`；两侧均产出图片；API `fallback_used=false`、`output_changed=true`；输出路径：`/tmp/mt_repro3/cli_001.jpg`、`/tmp/mt_repro3/api_001.jpg`）
- 提交哈希: N/A

## BUGFIX-TRANSLATE-019
- TASK-ID: BUGFIX-TRANSLATE-019
- 状态: completed
- 改动文件: `manga_translator/server/main.py`, `manga_translator/server/core/task_manager.py`, `manga_translator/server/request_extraction.py`, `tests/test_v1_translate_concurrency.py`, `tests/test_v1_routes.py`, `docs/2026-02-10-project-audit.md`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无新增/删除 API；修复 Web/API 在不同启动方式下的 GPU 配置一致性（新增内部运行时标记 `_runtime_config_initialized`、`_runtime_config_source`），并避免 runtime 未初始化时错误覆盖 `cli.use_gpu`。
- 验证命令: `pytest -q tests/test_v1_translate_concurrency.py tests/test_v1_routes.py && pytest -q && python -m manga_translator web --host 127.0.0.1 --port 8011 && python -m uvicorn manga_translator.server.main:app --host 127.0.0.1 --port 8012 && MT_USE_GPU=false python -m uvicorn manga_translator.server.main:app --host 127.0.0.1 --port 8013`（启动命令以后台短时启动+日志抓取方式执行）
- 验证结果: pass（定向测试 `33 passed`；全量后端 `118 passed, 1 skipped`；启动日志分别为 `use_gpu=True, source=run_server`、`use_gpu=True, source=startup_auto`、`use_gpu=False, source=startup_auto`）
- 提交哈希: 1eeae1d

## BUGFIX-TRANSLATE-020
- TASK-ID: BUGFIX-TRANSLATE-020
- 状态: completed
- 改动文件: `manga_translator/server/core/task_manager.py`, `manga_translator/server/main.py`, `manga_translator/server/request_extraction.py`, `tests/test_runtime_gpu_lazy_init.py`, `tests/test_v1_routes.py`, `test_vue_api_path.py`, `test_vue_api_path_timed.py`, `test_deep_diagnosis.py`, `docs/2026-02-10-project-audit.md`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无新增/删除 API；内部 runtime 初始化策略增强为 lazy + startup 双兜底，确保 API 核心直调链路不因未初始化回落 CPU
- 验证命令: `pytest -q tests/test_runtime_gpu_lazy_init.py tests/test_v1_translate_concurrency.py tests/test_v1_routes.py && pytest -q && /usr/bin/time -p python test_vue_api_path_timed.py --runs 1 --image manga_translator/server/data/raw/isekai-dragondick-knight-commander/chapter-1/001.jpg --output result/test_vue_api_timed_001_phasefix.jpg && /usr/bin/time -p python test_qt_cli_path_timed.py --runs 1 --image manga_translator/server/data/raw/isekai-dragondick-knight-commander/chapter-1/001.jpg --output result/test_qt_cli_timed_001_phasefix.jpg`
- 验证结果: pass（`37 passed`；全量 `122 passed, 1 skipped`；实图 API `TOTAL_get_ctx=57.11s, device=mps`；Qt/CLI `TOTAL_translate_batch=55.96s, device=mps`；耗时比 `1.02 <= 1.3`；两侧均成功产图）
- 提交哈希: eb887c3, 293de53

## BUGFIX-TRANSLATE-021
- TASK-ID: BUGFIX-TRANSLATE-021
- 状态: completed
- 改动文件: `frontend/src/stores/translate.js`, `frontend/tests/translate.test.js`, `docs/2026-02-10-project-audit.md`, `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- 接口影响: 无新增/删除 API；前端章节状态机从“仅 `chapter_complete` 收口”改为“`progress` 覆盖总页数也可收口”，解决“已翻译仍显示处理中”问题并保持 SSE 协议兼容
- 验证命令: `cd frontend && npm test -- --run tests/translate.test.js && cd frontend && npm test -- --run tests/smoke.test.js tests/manga_delete_actions.test.js`
- 验证结果: pass（新增用例先红后绿；`translate.test.js` 3/3 通过；回归 `smoke + manga_delete_actions` 9/9 通过）
- 提交哈希: N/A

## TASK-DEP-01
- TASK-ID: TASK-DEP-01
- 状态: completed
- 改动文件: `deploy/nginx/manga-translator-82.conf`, `deploy/systemd/manga-translator.service`, `docs/deployment/2026-02-11-82-cloudrun-hybrid.md`
- 接口影响: 无 API 变更；新增 82 生产入口模板（Nginx 反代 `/api` `/auth` `/admin` `/output` + SSE，systemd 常驻服务模板）
- 验证命令: `rg -n "location /api/|location /auth/|location /admin/|location /output/|translate/events|ExecStart=|MANGA_TRANSLATE_EXECUTION_BACKEND" deploy/nginx/manga-translator-82.conf deploy/systemd/manga-translator.service`
- 验证结果: pass
- 提交哈希: e364550

## TASK-DEP-02
- TASK-ID: TASK-DEP-02
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`, `manga_translator/server/request_extraction.py`, `tests/test_v1_routes.py`
- 接口影响: `POST /api/v1/translate/chapter` 新增可选返回 `task_id/execution_backend/accepted_at`；章节执行改为 executor 编排并固定“逐页成功保留、失败页重试后独立失败、章节可 partial”
- 验证命令: `pytest -q tests/test_v1_routes.py -k "translate_chapter_returns_execution_metadata or translate_chapter_partial_keeps_successful_pages"`
- 验证结果: pass
- 提交哈希: e364550

## TASK-DEP-03
- TASK-ID: TASK-DEP-03
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`, `manga_translator/server/routes/__init__.py`, `manga_translator/server/main.py`, `deploy/cloudrun/deploy-compute.sh`
- 接口影响: 新增内部端点 `POST /internal/translate/page`（内部 token 鉴权）；Cloud Run 计算执行器落地
- 验证命令: `pytest -q tests/test_v1_routes.py -k "internal_translate_page_requires_internal_token"`
- 验证结果: pass
- 提交哈希: e364550

## TASK-DEP-04
- TASK-ID: TASK-DEP-04
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`, `manga_translator/server/request_extraction.py`, `tests/test_v1_routes.py`
- 接口影响: HQ 上下文透传固定为前 3 页 `context_translations`，无实例内会话态依赖
- 验证命令: `pytest -q tests/test_v1_routes.py -k "build_context_translations_uses_latest_three"`
- 验证结果: pass
- 提交哈希: e364550

## TASK-DEP-05
- TASK-ID: TASK-DEP-05
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`, `docs/api/2026-02-10-v1-api-contract.md`
- 接口影响: 章节/SSE 事件补充可选诊断字段 `execution_backend`、`remote_elapsed_ms`、`failure_stage`、`pipeline`，用于远端计算可观测
- 验证命令: `rg -n "execution_backend|remote_elapsed_ms|failure_stage|pipeline|accepted_at|task_id|/internal/translate/page" manga_translator/server/routes/v1_translate.py docs/api/2026-02-10-v1-api-contract.md`
- 验证结果: pass
- 提交哈希: e364550

## TASK-DEP-06
- TASK-ID: TASK-DEP-06
- 状态: completed
- 改动文件: `docs/deployment/2026-02-11-82-cloudrun-hybrid.md`
- 接口影响: 无 API 变更；补充一期二进制回传的流量/耗时审计项与二期 GCS 直写立项阈值
- 验证命令: `rg -n "传输与成本审计|request_bytes_total|response_bytes_total|transport_ratio" docs/deployment/2026-02-11-82-cloudrun-hybrid.md`
- 验证结果: pass
- 提交哈希: e364550

## TASK-DEP-07
- TASK-ID: TASK-DEP-07
- 状态: completed
- 改动文件: `docs/deployment/2026-02-11-82-cloudrun-hybrid.md`
- 接口影响: 无 API 变更；新增 82 主机与 Cloud Run 安全加固基线（禁 root 远程、密钥登录、内部 token + Secret Manager）
- 验证命令: `rg -n "安全加固基线|PermitRootLogin no|PasswordAuthentication no|Secret Manager|X-Internal-Token" docs/deployment/2026-02-11-82-cloudrun-hybrid.md`
- 验证结果: pass
- 提交哈希: e364550

## TASK-DEP-08
- TASK-ID: TASK-DEP-08
- 状态: completed（82 已上线，Cloud Run 待项目参数）
- 改动文件: 无仓库代码改动（远端实操：`82.22.36.81` 部署）
- 接口影响: 无 API 契约变更；`/`、`/signin`、`/auth/status`、`/api/v1/manga` 在 82 入口可用
- 验证命令: `curl -I http://82.22.36.81/`、`curl http://82.22.36.81/auth/status`、`curl http://82.22.36.81/api/v1/manga`、`systemctl status manga-translator.service nginx`
- 验证结果: pass（`/` 200；`/signin` 200；`/auth/status` 200；未登录 `/api/v1/manga` 401；`manga-translator.service` 与 `nginx` active）
- 提交哈希: N/A

## TASK-DEP-09
- TASK-ID: TASK-DEP-09
- 状态: completed
- 改动文件: `manga_translator/server/cloudrun_compute_main.py`, `packaging/Dockerfile`, `/etc/systemd/system/manga-translator.service`（82 远端）
- 接口影响: 无外部 API 契约变更；Cloud Run 改为 compute-only 启动（仅 `/internal/translate/*` + `/` 健康），显式排除 scraper 模块加载
- 验证命令: `gcloud auth list --filter=status:ACTIVE`、`gcloud run services describe manga-translator-compute --region europe-west1`、`curl https://manga-translator-compute-olzq5mxmza-ew.a.run.app/`、`systemctl status manga-translator.service`（82）
- 验证结果: pass（active account=`juniya1314@gmail.com`；Cloud Run revision `manga-translator-compute-00004-wq6` Ready=True；82 服务已切换 `MANGA_TRANSLATE_EXECUTION_BACKEND=cloudrun`）
- 提交哈希: N/A

## TASK-DEP-10
- TASK-ID: TASK-DEP-10
- 状态: completed
- 改动文件: `.gcloudignore`, `manga_translator/server/core/config_manager.py`, `tests/test_runtime_gpu_lazy_init.py`
- 接口影响: 无外部 API 契约变更；修复 Cloud Build 源上传遗漏模块导致 Cloud Run 启动失败；补齐默认配置回退与配置路径覆盖能力
- 验证命令: `pytest -q tests/test_runtime_gpu_lazy_init.py tests/test_v1_translate_concurrency.py`、`gcloud beta builds log --stream 57767ad8-aadd-4b58-807c-c52173924869`
- 验证结果: pass（测试 `10 passed`；镜像 `20260211-164747-gcloudignore-fix` 构建并推送成功）
- 提交哈希: f5dfabe

## TASK-DEP-11
- TASK-ID: TASK-DEP-11
- 状态: completed
- 改动文件: `docs/deployment/2026-02-11-82-cloudrun-hybrid.md`, `docs/2026-02-10-project-audit.md`, `/etc/systemd/system/manga-translator.service`（82 远端）
- 接口影响: 无外部 API 契约变更；Cloud Run 资源从 `2Gi` 升级到 `4Gi` 完成首轮 OOM 收敛与链路连通验证；82 云执行地址固定到新服务域名
- 验证命令: `gcloud run services update manga-translator-compute --region=europe-west1 --memory=4Gi --cpu=2 --concurrency=1`、`curl https://manga-translator-compute-177058129447.europe-west1.run.app/`、`curl -F image=@... https://.../internal/translate/page`（82 远端）
- 验证结果: pass（revision `manga-translator-compute-00011-wqp` Ready；`GET /` 200；82->Cloud Run 小图请求 `HTTP 200`）
- 提交哈希: f5dfabe

## TASK-DEP-12
- TASK-ID: TASK-DEP-12
- 状态: completed
- 改动文件: `manga_translator/translators/gemini.py`, `manga_translator/translators/gemini_hq.py`, `manga_translator/translators/keys.py`, `manga_translator/translators/common.py`, `docs/deployment/2026-02-11-82-cloudrun-hybrid.md`, `docs/2026-02-10-project-audit.md`
- 接口影响: 无外部 API 契约变更；修复默认 Gemini 模型失效（`404 model not found`）并将 Cloud Run 计算实例规格升级到 `8Gi/4CPU/900s` 以收敛实图 OOM/503
- 验证命令: `gcloud run services update manga-translator-compute --region=europe-west1 --update-env-vars GEMINI_MODEL=gemini-2.0-flash`、`gcloud run services update manga-translator-compute --region=europe-west1 --memory=8Gi --cpu=4 --concurrency=1 --timeout=900`、`gcloud logging read ... revision=manga-translator-compute-00014-5qf`
- 验证结果: pass（revision `manga-translator-compute-00014-5qf` Ready；`GET /` 200；OOM 告警消失）
- 提交哈希: 83c7669

## TASK-DEP-13
- TASK-ID: TASK-DEP-13
- 状态: completed
- 改动文件: `.gcloudignore`, `manga_translator/server/routes/v1_translate.py`, `tests/test_v1_routes.py`, `docs/deployment/2026-02-11-82-cloudrun-hybrid.md`, `docs/2026-02-10-project-audit.md`
- 接口影响: 无端点增删；`POST /internal/translate/page` 响应头改为 ASCII 安全编码（非拉丁文本编码后传输）并在 CloudRun executor 侧解码，修复 Unicode header 导致的 500
- 验证命令: `pytest -q tests/test_v1_routes.py -k 'internal_translate_page_requires_internal_token or internal_translate_page_encodes_non_latin_headers'`、`gcloud builds submit ... be5dcc38-...`、`gcloud run services update ... --image ...:20260211-181400-headerfix`、`gcloud run services describe manga-translator-compute --region=europe-west1`
- 验证结果: pass（新增测试通过；Cloud Run revision `manga-translator-compute-00016-x5x` Ready；`GEMINI_MODEL=gemini-2.0-flash` 生效）
- 提交哈希: d3b0fef
