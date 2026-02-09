# 2026-02-10 Cleanup Manifest

## 目标
- 先清理无用文件再重构。
- 留存“未被引用”证据命令。

## 证据与执行

### Candidate A
- 文件: `manga_translator/server/static/js/admin/i18n.js`
- 引用证据命令: `rg -n "js/admin/i18n.js|AdminI18n" manga_translator/server/static manga_translator/server`
- 执行结论: 仅自引用，未被页面入口挂载
- 动作: 已删除

### Candidate B
- 文件: `manga_translator/server/static/js/admin/modules/permissions.js`
- 引用证据命令: `rg -n "modules/permissions.js|PermissionsModule|permissions-table-body" manga_translator/server/static manga_translator/server`
- 执行结论: 未被页面入口挂载
- 动作: 已删除

### Legacy Static UI
- 删除清单:
  - `manga_translator/server/static/index.html`
  - `manga_translator/server/static/login.html`
  - `manga_translator/server/static/admin-new.html`
  - `manga_translator/server/static/style.css`
  - `manga_translator/server/static/script.js`
  - `manga_translator/server/static/js/history-gallery.js`
  - `manga_translator/server/static/js/i18n.js`
  - `manga_translator/server/static/admin/css/admin.css`
  - `manga_translator/server/static/js/admin/**`
- 验证命令: `find manga_translator/server/static -maxdepth 4 -type f | rg -v 'manga_translator/server/static/dist/' | rg 'admin-new|index.html|login.html|style.css|script.js|history-gallery.js|js/i18n.js|js/admin'`
- 验证结果: pass（无匹配）

### Runtime Artifacts
- 目标:
  - 全仓库 `__pycache__/`
  - `result/log_*.txt`
- 验证命令:
  - `find . -type d -name '__pycache__'`
  - `ls result/log_*.txt`
- 验证结果:
  - `__pycache__`: 已清理
  - `result/log_*.txt`: 当前无匹配文件

## 备注
- `manga_translator/server/static/favicon.ico` 保留。
- `manga_translator/server/static/dist/**` 为本地构建产物，已在 `.gitignore` 忽略，不入库。
