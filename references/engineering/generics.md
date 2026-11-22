# C++ 泛型与模板编程规范

适用于现代 C++17/20 泛型组件、策略组合（Policy-Based Design）、编译期约束与零成本抽象设计。

## 1. 编译期多态（模板 / `variant`）vs 运行期多态（虚接口）

| 机制 | 适用场景 | 不适用场景 / 风险 |
| --- | --- | --- |
| **模板 / Concepts** | 热路径算子、容器/分配器策略组合、编译期静态分发 | **严禁跨 DLL/SO 插件 ABI 边界**；过度嵌套导致编译耗时激增与报错天书。 |
| **`std::variant` + `std::visit`** | 闭合、有限且固定的状态/AST/命令集合（值语义，无堆分配） | 需要外部模块无重新编译即可动态扩展新类型时。 |
| **虚基类 / 类型擦除** | 模块边界依赖倒置（DI）、插件扩展、隔离头文件依赖、隐藏实现 | 极高频每像素/每元素内层循环（此时避免虚函数表跳转）。 |

## 2. 约束优先使用 C++20 `concepts`

- 新代码在 C++20 下**优先用 `concept` 与 `requires` 替代晦涩的 `std::enable_if` / SFINAE**，让类型错误在调用点立刻给出清晰诊断，而不是深入三层嵌套模板内部才报错。
- C++17 存量工程需约束模板时，优先用 `if constexpr` + `static_assert`（附清晰错误文本），仅在参与重载决议时才用 `std::enable_if_t`。

## 3. 完美转发与万能引用（Forwarding Reference）陷阱

1. **`std::forward<T>` 仅用于形参本身且同一路径只转发一次**：绝对不要把同一个参数在两条语句先后 `std::forward` 两次（第一次已可能将其移动掏空）；只有模板推导出的 `T&&` 才是万能引用，类模板参数 `C<T>` 的成员函数里的 `T&&` 只是普通右值引用！
2. **模板转发构造函数必须排除自身拷贝/移动重载（极高频坑！）**：
   - `template <typename T> explicit Wrapper(T&& value)` 在遇到非 `const` 左值 `Wrapper copy(w);` 时，模板实例化的 `Wrapper(Wrapper&)` 比常规 `Wrapper(const Wrapper&)` **匹配度更高**，会意外劫持拷贝构造函数导致编译错或递归！
   - 必须用 `requires (!std::same_as<std::remove_cvref_t<T>, Wrapper>)`（C++17 用 `std::enable_if_t`）显式屏蔽自身类型。

```cpp
template <typename T>
concept Serializable = requires(const T& item) {
    { item.serialize() } -> std::convertible_to<std::string>;
};

class MessageEnvelope {
public:
    MessageEnvelope(const MessageEnvelope&) = default;
    MessageEnvelope(MessageEnvelope&&) = default;

    template <typename T>
        requires (!std::same_as<std::remove_cvref_t<T>, MessageEnvelope>)
        && Serializable<std::remove_cvref_t<T>>
    explicit MessageEnvelope(T&& payload)
        : m_bytes(std::forward<T>(payload).serialize()) {}

private:
    std::string m_bytes;
};
```

## 4. 类型推导与视图生命周期陷阱

- **`auto` 会剥离顶层 `const` 与引用**：需要保持引用避免意外大对象拷贝时显式写 `const auto&` 或 `auto&`；使用 `decltype(auto)` 返回值时严禁 `return (localVar);`（多一对括号变成返回局部悬空引用）。
- **非拥有视图（`std::string_view` / `std::span`）**：仅作函数只读入参或局部短生命周期切片；**绝不将函数入参的 `string_view` 长期存入类成员或跨异步回调捕获**（传入临时 `std::string` 后在分号处立即悬空）。
- **惰性表达式模板的 `auto` 悬空**：如 [Eigen 规范](../stacks/cpp-core-utils.md) 所述，返回代理/表达式模板的库不可用 `auto` 保存中间运算结果。

## 5. 控制代码膨胀与编译耗时

- **逻辑提升（Code Hoisting）**：把模板类/函数中与模板参数 `T` 无关的逻辑（例如缓冲管理、字节级操作、校验函数）下沉到非模板基类或内部 `.cpp` 辅助函数，防止每实例化一个 `T` 复制一份机器码。
- **高频组合显式实例化**：对少数已知固定特化（如 `float` / `double`），可用 `extern template class Matrix<double>;` 并在单一 `.cpp` 显式实例化，大幅缩短全工程重编译时间。
