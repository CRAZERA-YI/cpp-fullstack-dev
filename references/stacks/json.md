# JSON 序列化与边界校验规范

适用范围：CMake（`nlohmann_json::nlohmann_json`、`simdjson::simdjson`、`glaze::glaze` 及与 Drogon 共存时的 `jsoncpp`）。

## 1. 库选型对比

| 库 | 适用定位 | 关键注意事项 |
| --- | --- | --- |
| **`nlohmann/json`** | 通用配置、中等载荷 DTO、读写直观灵活 | 易出现无符号整数溢出、非 const `operator[]` 写脏键及大报文分配开销。 |
| **`simdjson`** | 高吞吐、大体积只读 JSON 解析（日志/行情/网关） | 必须保证 `simdjson::padded_string` 在整个 `ondemand::document` 生命周期存活；`ondemand` 为单遍顺序迭代器，**不可回头重复访问同一个字段或脱离当前文档作用域持有 `ondemand::value`**。 |
| **`Glaze`** | C++20/23 零样板代码编译期反射直出 JSON / BEVE | 显式定义 struct 默认值与字段校验策略；需现代编译器（GCC 11+ / Clang 15+ / MSVC 19.34+），未在 schema 声明的多余未知键默认行为（`error_on_unknown_keys`）需与客户端兼容契约对齐。 |
| **`jsoncpp`** | Drogon 原生 HTTP JSON 生态（见 [Drogon 指南](drogon.md)） | 用 `isObject()`/`isMember()`/`isNull()`/`isInt64()`/`isUInt64()` 严查，勿直接 `.asInt()`。 |

## 2. `nlohmann/json` 严格边界校验（修复无符号大整数溢出陷阱）

在 `nlohmann::json` 中，直接读字段最容易踩以下两个坑：
1. **无符号整数溢出**：`is_number_integer()` 对 `[2^63, 2^64-1]` 的超大无符号整数也会返回 `true`！直接调用 `get<std::int64_t>()` 会发生静默回绕变负数。必须先区分 `is_number_unsigned()` 还是有符号整数。
2. **非 const `operator[]` 插入脏键**：对可修改 `nlohmann::json` 调用 `doc["missing"]` 会静默插入 `null` 键；读取字段一律用 `find()` / `contains()`。

```cpp
if (!document.is_object()) {
    return makeInvalidDocumentError();
}

const auto countIt = document.find("count");
if (countIt == document.end()) {
    return makeMissingFieldError("count");
}
if (!countIt->is_number_integer()) {
    return makeInvalidTypeError("count");
}

std::int64_t safeCount = 0;
if (countIt->is_number_unsigned()) {
    const auto rawUnsigned = countIt->get<std::uint64_t>();
    if (rawUnsigned > static_cast<std::uint64_t>(kMaximumCount)) {
        return makeOutOfRangeError("count");
    }
    safeCount = static_cast<std::int64_t>(rawUnsigned);
} else {
    const auto rawSigned = countIt->get<std::int64_t>();
    if (rawSigned < 0 || rawSigned > kMaximumCount) {
        return makeOutOfRangeError("count");
    }
    safeCount = rawSigned;
}
```

## 3. 其他边界约束

- **禁止滥用 `value(key, default)`**：它会把“键缺失”和“类型错误/为 `null`”混在一起（或直接抛 `type_error`）；必须先用 `find()` 判断存在性，再区分 `is_null()` 与类型，仅对契约明确允许缺省的可选字段套用默认值。
- **关闭异常模式（`-fno-exceptions` / `allow_exceptions=false`）**：`nlohmann::json::parse(..., /*allow_exceptions=*/false)` 失败时返回 `discarded` 状态；读取前必须先检查 `if (document.is_discarded())`，否则后续所有字段访问行为均无效。
- **`simdjson` 所有权与重复访问**：切勿传入未保留尾部填充（`SIMDJSON_PADDING`）的裸 `std::string_view` 给 `ondemand::parser::iterate`；若需要跨函数传递已解析结果，立即把字段物化（materialize）进工程 DTO 结构体。

## 4. 验证要点

- 覆盖 6 类边界输入测试：非法 JSON 语法、`{}` 缺键、`{"count": null}`、`{"count": "3"}`、负数与超出 `int64_t` 上限的整数（如 `18446744073709551615`）及合法往返；有历史版本样本时一并回放校验。
