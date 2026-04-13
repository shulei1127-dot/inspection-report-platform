# Analyzer Error Propagation v1

## Goal

增强平台在 `ANALYZER_MODE=remote` 下对 analyzer 非 200 响应的解析与透传能力，让失败链路保留更原始的 analyzer 错误语义。

## Scope

- 解析 analyzer 非 200 JSON 错误体中的 `code` / `message` / `details`
- 对非 JSON 错误体保底记录 HTTP 状态码和文本摘要
- 保留网络异常与超时映射：
  - `analyzer_unavailable`
  - `analyzer_timeout`
- 将错误详情落入任务记录，并在任务详情/列表中可见

## Minimal Contract Adjustment

对现有平台任务结果做一个加性扩展：

- `TaskResultData.error: TaskError | None`

这是向后兼容扩展，不改变现有成功字段和主流程。

数据库最小扩展：

- 在 `tasks` 表增加 `error_details TEXT`
- 以 JSON 字符串方式存储结构化错误详情

## Non-Goals

- 不改 parser
- 不改成功链路
- 不改 archive source
- 不引入 shared package
- 不重构平台主流程

## Validation

- `unsupported_source_type` 可在平台侧保留原始错误码
- `source_not_found` 可在平台侧保留原始错误码
- analyzer 非 JSON 500 时平台仍产生稳定错误
- analyzer 超时仍映射为 `analyzer_timeout`
