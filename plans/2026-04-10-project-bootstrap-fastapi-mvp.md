# 项目初始化 + 开发规约落地 + FastAPI 最小骨架

## 背景
- 当前仓库为空目录，需要先建立“日志解析与巡检报告生成平台”的后端最小闭环基础。
- 第一阶段仅实现可运行的 FastAPI 服务与健康检查，为后续上传日志包、解析、报告生成能力提供稳定入口。
- 项目需要从一开始就固化开发规约，包括 `plans/` 流程、文档、目录结构与基础环境约定。

## 目标
- 初始化 Git 项目与基础目录结构。
- 提供可运行的 FastAPI 最小骨架。
- 实现 `GET /health` 健康检查接口。
- 补齐基础工程文件与文档，确保后续需求可在该骨架上持续演进。

## 范围
### 做什么
- 创建规定的目录结构。
- 创建 FastAPI 应用入口、路由注册、基础配置。
- 实现 `GET /health` 返回服务可用状态。
- 提供 `README.md`、`.gitignore`、`.env.example`、`docs/architecture.md`、`docs/project_status.md`。
- 本地验证服务可启动且接口可访问。
- 完成本次需求的 git commit 与 push。

### 不做什么
- 不实现 `POST /api/tasks`。
- 不实现 zip 上传与解压。
- 不接入数据库。
- 不接入前端。
- 不接入 Carbone、AI 分析、统一解析 JSON 输出的业务实现。

## 影响文件
- `plans/2026-04-10-project-bootstrap-fastapi-mvp.md`
- `README.md`
- `.gitignore`
- `.env.example`
- `requirements.txt`
- `app/**`
- `docs/architecture.md`
- `docs/project_status.md`
- `tests/**`

## 接口/数据结构
### 接口
- `GET /health`

### 返回结构
```json
{
  "status": "ok",
  "service": "inspection-report-platform"
}
```

### 说明
- 当前仅提供最小健康检查结构，后续可扩展版本号、环境信息、依赖状态等字段。

## 实现步骤
1. 创建 `plans/` 目录并落地本 plan 文档。
2. 初始化 Git 仓库与远程仓库配置。
3. 创建项目目录结构与必要的 `__init__.py`。
4. 创建 FastAPI 应用入口、路由层、配置层和健康检查 schema。
5. 补充基础工程文件和文档。
6. 安装依赖并本地运行服务。
7. 调用 `GET /health` 验证接口。
8. 更新项目状态文档，完成 commit 与 push。

## 风险点
- 本地 Python 环境与依赖安装可能存在版本差异。
- GitHub push 依赖本机凭证配置，若无权限会导致 push 失败。
- 当前只实现最小骨架，若目录分层不够清晰会影响后续扩展。

## 验收标准
- 仓库内存在要求的基础目录。
- FastAPI 服务可以本地启动成功。
- `GET /health` 返回 HTTP 200 与预期 JSON。
- 基础工程文件与文档齐全。
- 已完成 git commit。
- 已尝试 push 到指定 GitHub 仓库并记录结果。

## 回滚方案
- 若本次初始化存在问题，可基于本次 commit 使用 `git revert <commit>` 进行整体回滚。
- 若仅文档或结构有误，可在后续独立需求中通过新的 plan 文档按小闭环修正。
