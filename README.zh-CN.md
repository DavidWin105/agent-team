[English](README.md) · **简体中文** · [မြန်မာ](README.my.md)

# agent-team

一个 Claude Code 插件：由 AI 智能体组成的团队，每个角色使用各自的模型，一套从计划到拉取请求（PR）的统一流程，只有负责人才能执行的步骤，以及用于终端的 `team-status` 命令。

![实时视图示意图](docs/media/live-view-preview-cards.png)

*实时视图（team-status 的 `--watch` 模式）的示意图，数据为虚构，并非真实运行的截图。*

设计文档见 `docs/specs/2026-11-17-agent-team-plugin-design.md`。

## 安装（每台机器一次）

在 Claude Code 中：

```
/plugin marketplace add DavidWin105/agent-team
/plugin install agent-team@agent-team-local
```

## 在项目中使用

1. `/team-init` 会写入 `.claude/team.json`。
2. 让 lead（负责人智能体）为任务制定计划；批准计划；再让它执行计划。
3. 运行 `/team-status`，或者在本仓库的克隆目录旁的任意终端中运行：`python3 -I agent-team/scripts/team-status <project-dir>`。

### 实时查看

1. 在 Claude Code 中运行 `/team-watch`。它会输出一行命令，其中已填入真实的插件目录和你的项目目录。
2. 打开第二个终端，粘贴这一行。命令的样子如下，它每秒刷新一次，直到你按下 Ctrl+C：

```bash
python3 -I <plugin folder>/scripts/team-status --watch <project folder>
```

如果你有本仓库的克隆，可以在任意终端中运行：`python3 -I agent-team/scripts/team-status --watch <project-dir>`。终端宽度达到 100 列或更宽时会显示卡片；更窄时显示表格。`/team-status`（不带实时查看）只输出一次快照。

### 实时视图显示什么、不显示什么

它显示每个团队智能体的角色、任务项、状态、正在做什么以及工具调用次数，这些信息由钩子（hooks）记录。它只记录工具名称、相对于项目（或相对于 builder 的工作树）的文件路径，以及 Bash 命令的第一个词（绝不记录文件内容、命令的其余部分或输出；以 `VAR=value` 开头的命令不会记录命令名）。钩子无法判断智能体是否失败，所以已停止的智能体会显示为完成；失败的工具调用会显示为类似 `Bash (failed)` 的形式。钩子的字段名来自文档，尚未在真实运行中验证。

### 检查实时视图

作者尚未实际运行过。你可以这样自己检查：

1. 在一个临时的 git 仓库中安装插件，并运行 `/team-init`。
2. 在第二个终端中运行 `python3 -I <path-to>/agent-team/scripts/team-status --watch <scratch-dir>`。
3. 在第一个终端中，让 lead 制定并执行一个包含两项任务的计划（例如，在不同文件中分别实现 `subtract` 和 `multiply` 函数）。
4. 检查每个智能体是否出现，是否显示它正在做什么，最后是否变为完成状态。

## 测试

```bash
cd tests && PYTHONPATH=../scripts python3 -m unittest discover -v
```

## 许可证

MIT。详见 `LICENSE`。
