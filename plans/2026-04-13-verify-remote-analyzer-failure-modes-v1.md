# Remote Analyzer Failure Verification v1

## Goal

把 remote analyzer 失败链固化成一条可重复执行的 smoke test / 验收脚本，覆盖最关键的失败模式，并验证平台侧失败诊断是否稳定。

## Scope

- 新增 `scripts/verify_remote_analyzer_failure_modes.sh`
- 最小同步 `README.md`
- 最小同步 `docs/project_status.md`

## Failure Modes

v1 覆盖以下三类：

- analyzer 不可达
- analyzer 返回结构化错误
  - `unsupported_source_type`
  - `source_not_found`
- analyzer 返回非 JSON 500

## Approach

- 使用临时 mock analyzer 服务制造可控错误
- 不改平台主流程
- 不改 analyzer 正式服务实现
- 每个场景单独启动平台实例，避免状态和日志互相污染

## Validation

每个场景至少校验：

- `POST /api/tasks` 失败响应稳定
- task 被记录为 `analyze_failed`
- `GET /api/tasks/{task_id}` 返回 `error.code` / `error.message` / `error.details`

## Non-Goals

- 不改 parser
- 不改成功链
- 不开始 archive source
- 不把脚本接入 CI
