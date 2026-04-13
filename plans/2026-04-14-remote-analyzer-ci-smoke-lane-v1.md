# Remote Analyzer CI Smoke Lane v1

## Goal

把 remote analyzer 的成功链与失败链验收脚本收敛成一套最小 CI / smoke lane 草案，形成稳定、可维护的自动回归入口。

## Scope

- 新增最小 GitHub Actions workflow
- 明确哪些检查必跑，哪些检查推荐跑，哪些保持可选
- 同步 `README.md` 与 `docs/project_status.md`

## Must Run

- root platform tests
- `log-analyzer-service` tests
- remote analyzer success smoke script
- remote analyzer failure smoke script

## Optional

- Carbone render verification

原因：

- 成功链 smoke 脚本已经把 render 验证做成 optional
- Carbone 依赖 Docker image 与运行时，不适合作为默认必跑项

## Workflow Shape

- `unit-tests`
  - root `pytest`
  - analyzer subtree `pytest`
- `remote-analyzer-smoke-success`
  - 执行 `scripts/verify_remote_analyzer_integration.sh`
  - `VERIFY_RENDER=false`
- `remote-analyzer-smoke-failure`
  - 执行 `scripts/verify_remote_analyzer_failure_modes.sh`

## Environment Assumptions

- Ubuntu runner
- Python 3.12
- root requirements 安装到同一个虚拟环境
- 再额外安装 `log-analyzer-service/requirements.txt`

## Non-Goals

- 不把 Carbone 接成默认必跑 CI
- 不改 parser
- 不改主流程
- 不引入更重的矩阵或部署步骤
