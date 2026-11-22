# Qt Quick (QML) 规范

适用范围：Qt5 / Qt6 · CMake（`qt_add_qml_module`）或存量 qmake（`.qrc` + `qmlRegisterType`）。

## 1. 接入与 C++/QML 边界

- **模块注册**：Qt6 优先采用工程约定的 `qt_add_qml_module`（核对 URI、版本号与资源前缀）；Qt5 沿用 `.qrc` 与显式类型注册。
- **清晰的所有权**：从 C++ 暴露给 QML 的 `QObject*` 默认由 C++ 父对象/管理器拥有（在 Qt5 中明确 `QQmlEngine::setObjectOwnership(..., QQmlEngine::CppOwnership)` 或 Qt6 `QML_SINGLETON`），绝不允许 C++ 与 QML 引擎同时尝试析构同一对象。
- **应用入口职责**：`QQmlApplicationEngine` 创立、监听 `objectCreated` 加载失败（空 root object 时立即退出或报错）属于应用入口层。

## 2. 高频踩坑（反模式 vs 正解）

1. **破坏声明式 Binding**：在 QML JS 处理器里直接给原本有绑定表达式的属性赋值（如 `label.text = "..."`）会永久覆盖绑定；应始终修改上游数据源或使用 `Binding` 元素控制切换。
2. **父布局与 `anchors` 抢占同一方向**：处于 `RowLayout` / `ColumnLayout` / `GridLayout` 内的子项必须用 `Layout.fillWidth`、`Layout.preferredWidth`、`implicitWidth` 控制尺寸，禁止同时在被布局管控的轴上设置 `anchors.left`/`right` 或固定 `width`。

```qml
Text {
    text: noteModel.title
    Layout.fillWidth: true
    wrapMode: Text.Wrap
}
```

3. **高频无效 `NOTIFY` 与全量重置模型**：`Q_PROPERTY` 只在值真正变化时 `emit titleChanged()`；列表数据变更使用 `QAbstractItemModel` 的 `beginInsertRows`/`endInsertRows` 或 `dataChanged`，不要每次刷新整体重置模型导致滚动条与焦点丢失。role 名称即公开 API，修改 role 需同步全局搜索所有 `.qml` 使用处。
4. **开发机能运行、安装后找不到 QML 模块**：永远不要依赖构建机环境变量或源码目录的 QML import path；按 [平台部署文档](../build/platforms/windows.md) 传 `--qmldir` / 使用 `qt_generate_deploy_qml_app_script()`，并在干净 staging 目录测试。

## 3. 验证要点

- 在安装后的 staging 目录启动，测试窗口极限缩窄（检查换行与滚动/折叠策略）、中文长文本、页面卸载期间异步 C++ 回调不写入已销毁对象。
