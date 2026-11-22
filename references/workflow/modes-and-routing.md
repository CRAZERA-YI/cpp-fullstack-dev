# 开发模式与项目路由

## 1. 模式判断

| 模式 | 触发特征 | 首要动作 |
| --- | --- | --- |
| **从零开发** | 新建空目录、新产品或从零立项 | 先确定全栈形态（`cpp-web` / `cpp-qt` / `cpp-python` / `cpp-core`）与技术栈获取方式（用户指定 vs AI 规划），确认首批可验收链路。 |
| **存量维护** | 在已有仓库修复缺陷、新增模块或重构 | 先运行 `python <skill_dir>/scripts/inspect_project.py [project_root]`（Linux/macOS 用 `python3`），再用根/子目录构建配置确认真实目标、依赖与调用方，不凭空重写既有结构。 |
| **续做任务** | 提到“继续上次”、接手交接文档或未完成分支 | 检查交接记录（如 `docs/tasks/<task-id>.md`）、Git 分支、未提交/已暂存改动与已有测试；原样保留用户工作区未提交修改，只重跑仍受影响的验证。 |

仅当存在会实质改变架构、接口契约或交付形态的歧义时才向用户澄清；局部细节按工程已有习惯推进。

## 2. 项目画像与 `cpp-stack.json` 关系

- **默认自动探测**：绝大多数项目无需额外配置，直接用 `<skill_dir>/scripts/inspect_project.py` 从 `CMakeLists.txt`、`CMakePresets.json`、`vcpkg.json`、`.pro`、`pyproject.toml`、`package.json` 自动生成项目画像。
- **`cpp-stack.json` 为可选显式声明**：仅在多组件大型仓库需要明确组件边界、`dependsOn` 拓扑或 `ui.theme` 绑定，且用户希望落盘路由时才创建或更新；格式见 [Schema](../../assets/schemas/cpp-stack.schema.json) 与 [最小模板](../../assets/templates/cpp-stack.json)。
- **最小模板结构**：模板初始即包含 `"app": { "path": ".", "role": "app", "stack": [] }` 作为单组件起点（并非空对象）；多组件接入时按真实构建目录拆分并删去不适用的占位项。

| 关键字段 | 说明 |
| --- | --- |
| `schemaVersion` | 必填，当前为 `1`。 |
| `architecture` | 可选，`cpp-web` / `cpp-qt` / `cpp-python` / `cpp-core` / `hybrid`。 |
| `stackMode` | 可选，`user-provided`（用户自供）或 `ai-planned`（AI 规划）。 |
| `components.<id>` | 必填对象：`path`（相对根路径`/`分隔）、`stack`（开放字符串数组，允许填规范仓库未收录的自定义库），可选 `role`、`target`、`dependsOn`、`platforms`。 |
| `ui.theme` / `ui.windows` | 可选，绑定主题（`preset` / `custom` / `native`）与窗口布局选型。 |

## 3. 冲突裁决优先级

当各来源描述不一致时，按以下顺序裁决，不以过期元数据覆盖代码事实：

1. **用户本轮明确指令**（例如指定迁移到新库或更换布局/主题）。
2. **真实构建文件与源码**（`CMakeLists.txt`、`.pro`、`vcpkg.json`、`pyproject.toml`、`package.json` 与实际调用链）。
3. **项目级 `cpp-stack.json` 与交接文档**（若与构建文件冲突，按构建文件执行并提示或按范围同步 `cpp-stack.json`）。
4. **Skill 默认指南**（仅补足工程未作约定的空白）。

`inspect_project.py` 若报出 `dependsOn` 缺失或环依赖，需先修复或沿真实代码边界核实影响范围。
