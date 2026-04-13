# Remote Analyzer Verification Script

## Goal

固化一条可重复执行的 remote analyzer 联调验收脚本，覆盖：

- `log-analyzer-service` 健康检查
- 平台 remote 模式健康检查
- 上传符合 `input_bundle_spec_v1` 的样例压缩包
- 校验 `unified.json` / `report_payload.json` 落盘
- 校验版本字段
- 在 Carbone 可用时可选校验 `report.docx`

## Scope

- 新增 `scripts/verify_remote_analyzer_integration.sh`
- 最小同步 `README.md`
- 最小同步 `docs/project_status.md`

## Assumptions

- 根仓库 `.venv` 已安装平台与 analyzer 子项目所需依赖
- `log-analyzer-service` 继续复用根仓库 `.venv`
- 样例输入优先使用 `tests/fixtures/input_bundle_spec_v1`
- 报告渲染检查为可选项，不强依赖本机 Carbone

## Implementation Notes

- 脚本自行启动 analyzer 与 platform，避免手工前置步骤
- 平台固定使用 `ANALYZER_MODE=remote`
- 通过临时 zip 组装 fixture，不新增二进制样例包
- 失败时输出 analyzer/platform 日志，便于定位

## Validation

- 运行脚本并确认：
  - analyzer `/health` 通过
  - platform `/health` 通过
  - 上传成功并返回 `task_id`
  - `unified.json` 与 `report_payload.json` 存在
  - 版本字段正确
  - Carbone 可用时 `report.docx` 有效
