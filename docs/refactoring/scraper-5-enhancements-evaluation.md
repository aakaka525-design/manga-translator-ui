# Scraper 5 项前后端优化方案评估（执行态）

> 日期：2026-02-16  
> 分支：`codex/scraper-5-enhancements-20260216`  
> 基线：`codex/scraper-v2-refactor-20260215`

## 结论

本轮按 P1+P2 一次性落地，5 项均已实施并通过门禁回归。

## 实施结果对照

1. Provider Schema 自描述：已完成。
- `ProviderAdapter` 新增 `features/form_schema/image_cache_public`。
- `/api/v1/scraper/providers` 已返回新增可选字段。

2. 前端动态表单渲染：已完成。
- 站点下拉改为动态读取 provider 列表。
- `form_schema` 字段可驱动表单项渲染并写回 store。

3. 数据归一化 DTO：已完成。
- `MangaItem` 扩展 `author/status/source`。
- `ChapterItem` 扩展 `number/date/language`。
- 路由返回保持向后兼容（仅新增可选字段）。

4. 异常指令化（Actionable Errors）：已完成。
- 后端错误 detail 支持 `action/payload`。
- challenge 场景返回 `PROMPT_USER_COOKIE`。
- 新增 `POST /api/v1/scraper/inject_cookies`，前端支持弹窗注入并自动重试。

5. 后端图片代理增强：已完成。
- `/api/v1/scraper/image` 切换统一 `ScraperHttpClient.fetch_binary`。
- challenge 场景支持 actionable error。
- 缓存策略：默认 `private, max-age=3600`，provider 可配置 public。

## 风险与已知限制

1. challenge 注入默认强依赖 `cf_clearance`，适配了主流 Cloudflare 场景；站点若要求额外 cookie，需要在注入 header 中同时提供。
2. `form_schema` 当前用于配置驱动和可视化扩展，复杂交互（如 OAuth）仍需独立前端流程。

## 验证证据

- 后端：`pytest -q tests/test_v1_routes.py tests/test_v1_scraper_phase2.py tests/test_v1_scraper_phase3.py tests/test_v1_scraper_phase4.py` -> `84 passed`
- 前端：`cd frontend && npm test -- --run` -> `53 passed`
- 构建：`cd frontend && npm run build` -> `success`

## 后续建议

1. 将 `form_schema` 的字段映射进一步标准化到 composable 层，减少 `ScraperConfig.vue` 视图逻辑。
2. 为 `/api/v1/scraper/image` 增加大图 streaming 响应策略（按文件大小阈值切换）。
