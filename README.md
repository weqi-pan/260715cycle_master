# Cycle Master v2

Cycle Master 的全栈 TypeScript 重构版本。当前版本使用 pnpm monorepo、Node 22、TypeScript strict、Node 原生 HTTP、Zod、better-sqlite3 和 Vue 3。

## 运行环境

- 操作系统：Linux。
- Node.js：22 或更高版本。
- 包管理器：pnpm 11 或更高版本。
- 浏览器：Chrome / Edge 等现代 Chromium 浏览器。
- 前端只交付浏览器可运行的静态资源，不做 Windows 桌面兼容。

## 常用命令

```bash
pnpm install
pnpm story:compile -- --strict
pnpm test
pnpm typecheck
pnpm build
pnpm dev
```

默认后端监听 `127.0.0.1:8000`，前端开发服务监听 `127.0.0.1:5173`。可通过 `HOST`、`PORT`、`DATABASE_FILE`、`STORY_SOURCE_ROOT`、`STORY_BUILD_ROOT` 覆盖。

## 项目结构

- `packages/story-schema`：Story v3 校验、编译、诊断、快照发布。
- `packages/game-runtime`：与 HTTP 无关的纯游戏运行时。
- `packages/api-contract`：Zod API 契约与错误码。
- `apps/server`：Node HTTP 服务、SQLite 存档和静态资源。
- `apps/web`：Vue 3 播放器。
- `content/story_v3`：剧情创作源。
- `tests`：核心、服务端与前端逻辑回归。

## 存档与恢复

页面刷新或后端重启后不自动恢复进度。只能通过手动存档恢复。存档使用剧情内容指纹和 `stateSchemaVersion` 校验；不兼容时拒读并保留原档。

## 当前实现说明

原计划中的 Fastify 和 Drizzle ORM 尚未引入。当前服务端使用 Node 原生 `node:http` 和 better-sqlite3，这是在无网络安装依赖情况下的现实偏差。后续如引入 Fastify 或 Drizzle，需要同步更新这里的说明。
