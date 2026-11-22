#!/usr/bin/env python3
"""Read-only repository inspector and optional cpp-stack.json validator."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "out",
    "build",
    "vcpkg_installed",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "target",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".cache",
    "_deps",
    "CMakeFiles",
    ".vs",
    ".vscode",
    ".idea",
    ".agents",
    ".agent",
    "_agents",
    "_agent",
    ".claude",
    ".codex",
    ".cursor",
    ".windsurf",
    ".conan2",
    ".next",
    ".nuxt",
    ".svelte-kit",
    "third_party",
    "3rdparty",
    "external",
    "extern",
    "vendor",
}

HELPER_PY_DIRS = {
    "scripts",
    "script",
    "tools",
    "tool",
    "ci",
    "cmake",
    "docs",
    "doc",
    "examples",
    "example",
    "benchmarks",
    "benchmark",
    "assets",
}

CMAKE_FIND_PACKAGE_STOP_KEYWORDS = {
    "REQUIRED",
    "QUIET",
    "CONFIG",
    "MODULE",
    "NO_MODULE",
    "EXACT",
    "HINTS",
    "PATHS",
    "NAMES",
    "CONFIGS",
    "PATH_SUFFIXES",
    "NO_POLICY_SCOPE",
    "NO_DEFAULT_PATH",
    "NO_CMAKE_ENVIRONMENT_PATH",
    "NO_CMAKE_PATH",
    "NO_SYSTEM_ENVIRONMENT_PATH",
    "NO_CMAKE_PACKAGE_REGISTRY",
    "NO_CMAKE_BUILDS_PATH",
    "NO_CMAKE_SYSTEM_PATH",
    "NO_CMAKE_SYSTEM_PACKAGE_REGISTRY",
    "CMAKE_FIND_ROOT_PATH_BOTH",
    "ONLY_CMAKE_FIND_ROOT_PATH",
    "NO_CMAKE_FIND_ROOT_PATH",
    "GLOBAL",
    "BYPASS_PROVIDER",
    "REGISTRY_VIEW",
}

CATALOG_ALIASES: dict[str, str] = {
    # Qt & GUI
    "qt-widgets": "qt-widgets",
    "qt5::widgets": "qt-widgets",
    "qt6::widgets": "qt-widgets",
    "qt::widgets": "qt-widgets",
    "qt-quick": "qt-quick",
    "qt5::quick": "qt-quick",
    "qt6::quick": "qt-quick",
    "qt::quick": "qt-quick",
    "qt5::qml": "qt-quick",
    "qt6::qml": "qt-quick",
    "qt::qml": "qt-quick",
    "qt5::quickcontrols2": "qt-quick",
    "qt6::quickcontrols2": "qt-quick",
    "qt::quickcontrols2": "qt-quick",
    "qml": "qt-quick",
    "qtdeclarative": "qt-quick",
    "qt5-declarative": "qt-quick",
    "qt6-declarative": "qt-quick",
    "qt-network-client": "qt-network-client",
    "qt5::network": "qt-network-client",
    "qt6::network": "qt-network-client",
    "qt::network": "qt-network-client",
    "qt5::websockets": "qt-network-client",
    "qt6::websockets": "qt-network-client",
    "qt::websockets": "qt-network-client",
    "qtwebsockets": "qt-network-client",
    "qt5-websockets": "qt-network-client",
    "qt6-websockets": "qt-network-client",
    "libcurl": "qt-network-client",
    "curl": "qt-network-client",
    "cpr": "qt-network-client",
    "dear-imgui": "dear-imgui",
    "imgui": "dear-imgui",
    "imgui-docking": "dear-imgui",
    # Networking & Backend Services
    "drogon": "drogon",
    "cpp-http-lightweight": "cpp-http-lightweight",
    "cpp-httplib": "cpp-http-lightweight",
    "httplib": "cpp-http-lightweight",
    "crow": "cpp-http-lightweight",
    "oatpp": "cpp-http-lightweight",
    "oatpp-swagger": "cpp-http-lightweight",
    "boost-asio-beast": "boost-asio-beast",
    "boost-asio": "boost-asio-beast",
    "boost-beast": "boost-asio-beast",
    "boost::asio": "boost-asio-beast",
    "boost::beast": "boost-asio-beast",
    "boost_asio": "boost-asio-beast",
    "boost_beast": "boost-asio-beast",
    "asio": "boost-asio-beast",
    "grpc": "grpc-protobuf",
    "grpc-protobuf": "grpc-protobuf",
    "grpcio": "grpc-protobuf",
    "protobuf": "grpc-protobuf",
    "messaging-zmq-mqtt": "messaging-zmq-mqtt",
    "zeromq": "messaging-zmq-mqtt",
    "cppzmq": "messaging-zmq-mqtt",
    "libzmq": "messaging-zmq-mqtt",
    "zmq": "messaging-zmq-mqtt",
    "paho-mqtt": "messaging-zmq-mqtt",
    "paho-mqtt-c": "messaging-zmq-mqtt",
    "eclipse-paho-mqtt-c": "messaging-zmq-mqtt",
    "paho-mqtt3a": "messaging-zmq-mqtt",
    "paho-mqtt3as": "messaging-zmq-mqtt",
    "paho-mqtt3c": "messaging-zmq-mqtt",
    "paho-mqtt3cs": "messaging-zmq-mqtt",
    "paho-mqttpp3": "messaging-zmq-mqtt",
    "pahomqttcpp": "messaging-zmq-mqtt",
    "amqp-cpp": "messaging-zmq-mqtt",
    "amqpcpp": "messaging-zmq-mqtt",
    # Contracts & JSON
    "openapi": "openapi",
    "nlohmann-json": "json",
    "nlohmann_json": "json",
    "jsoncpp": "json",
    "simdjson": "json",
    "glaze": "json",
    "json": "json",
    # Data, Cache & Analytics
    "sqlite": "sqlite",
    "sqlite3": "sqlite",
    "sqlitecpp": "sqlite",
    "unofficial-sqlite3": "sqlite",
    "qt5::sql": "sqlite",
    "qt6::sql": "sqlite",
    "qt::sql": "sqlite",
    "postgresql": "postgresql-libpqxx",
    "libpq": "postgresql-libpqxx",
    "libpqxx": "postgresql-libpqxx",
    "pqxx": "postgresql-libpqxx",
    "postgresql-libpqxx": "postgresql-libpqxx",
    "mysql-mariadb": "mysql-mariadb",
    "boost-mysql": "mysql-mariadb",
    "boost::mysql": "mysql-mariadb",
    "boost_mysql": "mysql-mariadb",
    "libmysql": "mysql-mariadb",
    "libmysqlclient": "mysql-mariadb",
    "libmariadb": "mysql-mariadb",
    "unofficial-libmariadb": "mysql-mariadb",
    "mariadb": "mysql-mariadb",
    "mysql": "mysql-mariadb",
    "mysql-connector-cpp": "mysql-mariadb",
    "redis-cache": "redis-cache",
    "redis-plus-plus": "redis-cache",
    "redis++": "redis-cache",
    "hiredis": "redis-cache",
    "duckdb-analytics": "duckdb-analytics",
    "duckdb": "duckdb-analytics",
    "arrow": "duckdb-analytics",
    "pyarrow": "duckdb-analytics",
    "parquet": "duckdb-analytics",
    # C++ Core Utils, Observability & Testing
    "cpp-core-utils": "cpp-core-utils",
    "fmt": "cpp-core-utils",
    "cli11": "cpp-core-utils",
    "yaml-cpp": "cpp-core-utils",
    "tomlplusplus": "cpp-core-utils",
    "toml++": "cpp-core-utils",
    "openssl": "cpp-core-utils",
    "eigen3": "cpp-core-utils",
    "eigen": "cpp-core-utils",
    "opencv": "cpp-core-utils",
    "opencv4": "cpp-core-utils",
    "opencv-python": "cpp-core-utils",
    "opencv_python": "cpp-core-utils",
    "spdlog": "observability-security",
    "observability-security": "observability-security",
    "googletest": "testing",
    "gtest": "testing",
    "catch2": "testing",
    "benchmark": "testing",
    "google-benchmark": "testing",
    "qt-test": "testing",
    "qt5::test": "testing",
    "qt6::test": "testing",
    "qt::test": "testing",
    "qt::testlib": "testing",
    "testlib": "testing",
    "testing": "testing",
    "pytest": "testing",
    "vitest": "testing",
    "playwright": "testing",
    # Web & Python Companion Stacks
    "web-frontend-stack": "web-frontend-stack",
    "react": "web-frontend-stack",
    "vue": "web-frontend-stack",
    "svelte": "web-frontend-stack",
    "next": "web-frontend-stack",
    "vite": "web-frontend-stack",
    "typescript": "web-frontend-stack",
    "tailwindcss": "web-frontend-stack",
    "openapi-typescript": "web-frontend-stack",
    "orval": "web-frontend-stack",
    "axios": "web-frontend-stack",
    "@tanstack/react-query": "web-frontend-stack",
    "@tanstack/vue-query": "web-frontend-stack",
    "pinia": "web-frontend-stack",
    "zustand": "web-frontend-stack",
    "python-bindings": "python-bindings",
    "scikit-build-core": "python-bindings",
    "scikit_build_core": "python-bindings",
    "pybind11": "python-bindings",
    "nanobind": "python-bindings",
    "numpy": "python-bindings",
    "cffi": "python-bindings",
    "python-service-stack": "python-service-stack",
    "fastapi": "python-service-stack",
    "pydantic": "python-service-stack",
    "uvicorn": "python-service-stack",
    "httpx": "python-service-stack",
}

DEFAULT_CATALOG_SLUGS = {
    "qt-widgets",
    "qt-quick",
    "qt-network-client",
    "dear-imgui",
    "drogon",
    "cpp-http-lightweight",
    "boost-asio-beast",
    "grpc-protobuf",
    "messaging-zmq-mqtt",
    "openapi",
    "json",
    "sqlite",
    "postgresql-libpqxx",
    "mysql-mariadb",
    "redis-cache",
    "duckdb-analytics",
    "cpp-core-utils",
    "observability-security",
    "testing",
    "web-frontend-stack",
    "python-bindings",
    "python-service-stack",
}

QT_ONLY_STACK_TAGS = {"qt-widgets", "qt-quick"}
QT_UMBRELLA_PACKAGES = {
    "qtbase",
    "qt5-base",
    "qt6-base",
    "qttools",
    "qt5-tools",
    "qt6-tools",
    "qtsvg",
    "qt5-svg",
    "qt6-svg",
    "qtcharts",
    "qt5-charts",
    "qt6-charts",
    "qtmultimedia",
    "qt5-multimedia",
    "qt6-multimedia",
    "qtshadertools",
    "qt6-shadertools",
    "qtimageformats",
    "qt5-imageformats",
    "qt6-imageformats",
}
QT_STANDARD_EXTRA_MODULES = {
    "core",
    "gui",
    "svg",
    "svgwidgets",
    "concurrent",
    "multimedia",
    "multimediawidgets",
    "opengl",
    "openglwidgets",
    "charts",
    "printsupport",
    "xml",
    "dbus",
    "linguisttools",
    "help",
    "uitools",
    "designer",
    "statemachine",
    "scxml",
    "serialport",
    "bluetooth",
    "positioning",
    "sensors",
}

PYPROJECT_MARKERS = (
    "scikit-build-core",
    "pybind11",
    "nanobind",
    "cffi",
    "fastapi",
    "uvicorn",
    "httpx",
    "pydantic",
    "pytest",
    "grpcio",
    "duckdb",
    "pyarrow",
    "numpy",
    "opencv-python",
)


def load_catalog_slugs() -> set[str]:
    """Discover stack slugs dynamically from references/stacks/*.md."""
    stacks_dir = Path(__file__).resolve().parent.parent / "references" / "stacks"
    if stacks_dir.is_dir():
        discovered = {
            p.stem for p in stacks_dir.glob("*.md") if p.name != "catalog.md"
        }
        if discovered:
            return discovered
    return set(DEFAULT_CATALOG_SLUGS)


KNOWN_CATALOG_SLUGS = load_catalog_slugs()

VALID_ARCHITECTURES = {"cpp-web", "cpp-qt", "cpp-python", "cpp-core", "hybrid"}
VALID_STACK_MODES = {"user-provided", "ai-planned"}
VALID_ROLES = {
    "app",
    "backend",
    "frontend",
    "desktop",
    "python-binding",
    "library",
    "tests",
}
VALID_PLATFORMS = {"windows", "linux", "macos"}
VALID_THEME_MODES = {"preset", "custom", "native"}

CPP_STACK_ROOT_KEYS = {
    "$schema",
    "schemaVersion",
    "architecture",
    "stackMode",
    "components",
    "ui",
}
CPP_STACK_COMPONENT_KEYS = {
    "path",
    "role",
    "stack",
    "target",
    "dependsOn",
    "platforms",
}
CPP_STACK_UI_KEYS = {"theme", "windows"}
CPP_STACK_THEME_KEYS = {"mode", "id", "source"}
CPP_STACK_WINDOW_KEYS = {"layout", "theme"}


def _is_in_helper_dir(rel: str) -> bool:
    parent_parts = Path(rel).parts[:-1]
    return any(part.lower() in HELPER_PY_DIRS for part in parent_parts)


def _is_absolute_or_anchored_path(raw: str) -> bool:
    path = Path(raw)
    return (
        path.is_absolute()
        or bool(path.anchor)
        or raw.startswith(("/", "\\"))
        or bool(re.match(r"^[A-Za-z]:", raw))
    )


def walk_repo(root: Path) -> list[Path]:
    """Walk repository files while pruning heavy/generated directories."""
    collected: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d
            for d in dirnames
            if d not in SKIP_DIRS
            and not d.startswith(("build-", "build_", "cmake-build-", ".venv", "venv_"))
        )
        for name in sorted(filenames):
            collected.append(Path(dirpath) / name)
    return collected


def read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def strip_cmake_comments(text: str) -> str:
    """Strip CMake bracket (#[[...]]) and line (#...) comments while respecting quotes and bracket args."""
    out: list[str] = []
    n = len(text)
    i = 0
    in_quote = False
    bracket_comment_re = re.compile(r"#\[(=*)\[")
    bracket_arg_re = re.compile(r"\[(=*)\[")

    while i < n:
        ch = text[i]
        if in_quote:
            if ch == "\\" and i + 1 < n:
                out.append(text[i : i + 2])
                i += 2
                continue
            if ch == '"':
                in_quote = False
            out.append(ch)
            i += 1
            continue

        if ch == '"':
            in_quote = True
            out.append(ch)
            i += 1
            continue

        if ch == "[":
            ba_match = bracket_arg_re.match(text, i)
            if ba_match:
                eq = ba_match.group(1)
                close_tok = f"]{eq}]"
                end_idx = text.find(close_tok, ba_match.end())
                if end_idx == -1:
                    out.append(text[i:])
                    break
                out.append(text[i : end_idx + len(close_tok)])
                i = end_idx + len(close_tok)
                continue

        if ch == "#":
            b_match = bracket_comment_re.match(text, i)
            if b_match:
                eq = b_match.group(1)
                close_tok = f"]{eq}]"
                end_idx = text.find(close_tok, b_match.end())
                if end_idx == -1:
                    break
                out.append(" ")
                i = end_idx + len(close_tok)
                continue
            nl_idx = text.find("\n", i)
            if nl_idx == -1:
                break
            i = nl_idx
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def parse_cmake_file(path: Path, root: Path) -> dict[str, Any]:
    raw = strip_cmake_comments(read_text_safe(path))

    def extract_first_tokens(*cmds: str, skip_alias: bool = False) -> list[str]:
        alt = "|".join(re.escape(c) for c in cmds)
        pattern = re.compile(rf"\b(?:{alt})\s*\(([^)]*)\)", re.IGNORECASE | re.DOTALL)
        out: list[str] = []
        for match in pattern.finditer(raw):
            tokens = match.group(1).strip().split()
            if tokens:
                if skip_alias and any(
                    t.upper() in {"ALIAS", "IMPORTED"} for t in tokens[1:4]
                ):
                    continue
                token = tokens[0].strip('"').strip("'")
                if token and token not in out:
                    out.append(token)
        return out

    def append_unique_ci(items: list[str], seen: set[str], value: str) -> None:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            items.append(value)

    qt_components: list[str] = []
    qt_seen: set[str] = set()
    boost_components: list[str] = []
    boost_seen: set[str] = set()
    python_binding_hint = False

    for match in re.finditer(r"\bfind_package\s*\(([^)]*)\)", raw, re.IGNORECASE | re.DOTALL):
        tokens = [t.strip('"').strip("'") for t in match.group(1).strip().split()]
        if not tokens:
            continue
        first = tokens[0]
        split_qt_match = re.match(r"^Qt([56])([A-Za-z0-9_]+)$", first)
        if split_qt_match:
            append_unique_ci(qt_components, qt_seen, f"qt::{split_qt_match.group(2)}")
            continue
        is_qt = bool(re.match(r"^Qt(?:[56]|\$\{[^}]+\})?$", first, re.IGNORECASE))
        is_boost = first.lower() == "boost"
        is_python = bool(re.match(r"^Python[23]?$", first, re.IGNORECASE))
        if not (is_qt or is_boost or is_python):
            continue

        in_components = False
        for tok in tokens[1:]:
            upper = tok.upper()
            if upper in {"COMPONENTS", "OPTIONAL_COMPONENTS"}:
                in_components = True
                continue
            if upper in CMAKE_FIND_PACKAGE_STOP_KEYWORDS:
                in_components = False
                continue
            if in_components and not tok.startswith("$"):
                if is_qt:
                    append_unique_ci(qt_components, qt_seen, f"qt::{tok}")
                elif is_boost:
                    append_unique_ci(boost_components, boost_seen, f"boost::{tok}")
                elif is_python and tok.lower() in {
                    "development",
                    "development.module",
                    "development.embed",
                }:
                    python_binding_hint = True

    for match in re.finditer(r"\bQt(?:[56]|\$\{[^}]+\})?::([A-Za-z0-9_]+)\b", raw):
        append_unique_ci(qt_components, qt_seen, f"qt::{match.group(1)}")
    for match in re.finditer(r"\bBoost::([A-Za-z0-9_]+)\b", raw):
        append_unique_ci(boost_components, boost_seen, f"boost::{match.group(1)}")

    packages = extract_first_tokens("find_package")
    if re.search(r"\bqt6?_add_qml_module\s*\(", raw, re.IGNORECASE):
        append_unique_ci(qt_components, qt_seen, "qt::Quick")
    if re.search(r"\bnanobind_add_module\s*\(", raw, re.IGNORECASE):
        if "nanobind" not in {p.lower() for p in packages}:
            packages.append("nanobind")
        python_binding_hint = True
    if re.search(r"\bpybind11_add_module\s*\(", raw, re.IGNORECASE):
        if "pybind11" not in {p.lower() for p in packages}:
            packages.append("pybind11")
        python_binding_hint = True

    cxx_standards: list[str] = []
    for match in re.finditer(
        r"\bset\s*\(\s*CMAKE_CXX_STANDARD\s+([0-9]{2})\b", raw, re.IGNORECASE
    ):
        std_val = f"c++{match.group(1)}"
        if std_val not in cxx_standards:
            cxx_standards.append(std_val)
    for match in re.finditer(r"\bcxx_std_([0-9]{2})\b", raw, re.IGNORECASE):
        std_val = f"c++{match.group(1)}"
        if std_val not in cxx_standards:
            cxx_standards.append(std_val)

    return {
        "file": path.relative_to(root).as_posix(),
        "projects": extract_first_tokens("project"),
        "subdirectories": extract_first_tokens("add_subdirectory"),
        "executables": extract_first_tokens(
            "add_executable",
            "qt_add_executable",
            "qt6_add_executable",
            "qt5_add_executable",
            skip_alias=True,
        ),
        "libraries": extract_first_tokens(
            "add_library",
            "qt_add_library",
            "qt6_add_library",
            "qt5_add_library",
            "qt_add_qml_module",
            "qt6_add_qml_module",
            "nanobind_add_module",
            "pybind11_add_module",
            skip_alias=True,
        ),
        "packages": packages,
        "fetchContent": extract_first_tokens("FetchContent_Declare"),
        "qtComponents": qt_components,
        "boostComponents": boost_components,
        "pythonBindingHint": python_binding_hint,
        "cxxStandards": cxx_standards,
    }


def parse_cmake_presets(path: Path, root: Path) -> dict[str, Any]:
    try:
        data = json.loads(read_text_safe(path))
    except json.JSONDecodeError as exc:
        return {"file": path.relative_to(root).as_posix(), "error": str(exc)}
    if not isinstance(data, dict):
        return {
            "file": path.relative_to(root).as_posix(),
            "error": "Root JSON value must be an object.",
        }

    def _visible_names(section: str) -> list[str]:
        items = data.get(section)
        if not isinstance(items, list):
            return []
        return [
            p.get("name")
            for p in items
            if isinstance(p, dict) and isinstance(p.get("name"), str) and not p.get("hidden")
        ]

    return {
        "file": path.relative_to(root).as_posix(),
        "version": data.get("version"),
        "configurePresets": _visible_names("configurePresets"),
        "buildPresets": _visible_names("buildPresets"),
        "testPresets": _visible_names("testPresets"),
        "packagePresets": _visible_names("packagePresets"),
        "workflowPresets": _visible_names("workflowPresets"),
    }


def parse_qmake_file(path: Path, root: Path) -> dict[str, Any]:
    text = read_text_safe(path)
    logical_lines: list[str] = []
    buf: list[str] = []

    for raw_line in text.splitlines():
        no_comment = raw_line.split("#", 1)[0].rstrip()
        if buf and not no_comment and raw_line.lstrip().startswith("#"):
            continue
        if no_comment.endswith("\\"):
            buf.append(no_comment[:-1].strip())
            continue
        buf.append(no_comment.strip())
        joined = " ".join(part for part in buf if part).strip()
        if joined:
            logical_lines.append(joined)
        buf.clear()

    if buf:
        joined = " ".join(part for part in buf if part).strip()
        if joined:
            logical_lines.append(joined)

    qt_modules: list[str] = []
    template_val: str | None = None

    for line in logical_lines:
        qt_match = re.match(r"^(?:[^=\n]*:\s*)?QT\s*(\+=|-=|=)\s*(.*)$", line)
        if qt_match:
            op, rhs = qt_match.group(1), qt_match.group(2)
            mods = [m.strip() for m in rhs.split() if m.strip()]
            if op == "=":
                qt_modules = []
                for mod in mods:
                    if mod not in qt_modules:
                        qt_modules.append(mod)
            elif op == "+=":
                for mod in mods:
                    if mod not in qt_modules:
                        qt_modules.append(mod)
            elif op == "-=":
                remove_set = set(mods)
                qt_modules = [m for m in qt_modules if m not in remove_set]
            continue

        tpl_match = re.match(r"^\s*TEMPLATE\s*=\s*(\S+)", line)
        if tpl_match:
            template_val = tpl_match.group(1)

    return {
        "file": path.relative_to(root).as_posix(),
        "template": template_val,
        "qtModules": qt_modules,
    }


def _extract_vcpkg_dep_names(dep_list: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(dep_list, list):
        return names
    for item in dep_list:
        if isinstance(item, str) and item not in names:
            names.append(item)
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            dep_name = item["name"]
            if dep_name not in names:
                names.append(dep_name)
    return names


def parse_vcpkg_json(path: Path, root: Path) -> dict[str, Any]:
    try:
        data = json.loads(read_text_safe(path))
    except json.JSONDecodeError as exc:
        return {"file": path.relative_to(root).as_posix(), "error": str(exc)}
    if not isinstance(data, dict):
        return {
            "file": path.relative_to(root).as_posix(),
            "error": "Root JSON value must be an object.",
        }
    deps = _extract_vcpkg_dep_names(data.get("dependencies", []))
    features_obj = data.get("features")
    features: list[str] = []
    feature_deps: list[str] = []
    if isinstance(features_obj, dict):
        features = list(features_obj.keys())
        for feat_body in features_obj.values():
            if isinstance(feat_body, dict):
                for dep_name in _extract_vcpkg_dep_names(feat_body.get("dependencies", [])):
                    if dep_name not in feature_deps:
                        feature_deps.append(dep_name)
    return {
        "file": path.relative_to(root).as_posix(),
        "name": data.get("name"),
        "dependencies": deps,
        "features": features,
        "featureDependencies": feature_deps,
    }


def parse_package_json(path: Path, root: Path) -> dict[str, Any]:
    try:
        data = json.loads(read_text_safe(path))
    except json.JSONDecodeError as exc:
        return {"file": path.relative_to(root).as_posix(), "error": str(exc)}
    if not isinstance(data, dict):
        return {
            "file": path.relative_to(root).as_posix(),
            "error": "Root JSON value must be an object.",
        }
    deps = set()
    for key in ("dependencies", "devDependencies"):
        section = data.get(key)
        if isinstance(section, dict):
            deps.update(section.keys())
    hints = sorted(
        pkg
        for pkg in (
            "react",
            "vue",
            "svelte",
            "next",
            "vite",
            "typescript",
            "tailwindcss",
            "openapi-typescript",
            "orval",
            "axios",
            "@tanstack/react-query",
            "@tanstack/vue-query",
            "pinia",
            "zustand",
            "vitest",
            "playwright",
        )
        if pkg in deps
    )
    return {
        "file": path.relative_to(root).as_posix(),
        "name": data.get("name"),
        "frameworkHints": hints,
        "dependencyCount": len(deps),
    }


def _extract_pyproject_dep_strings(data: dict[str, Any]) -> list[str]:
    entries: list[str] = []

    build_sys = data.get("build-system")
    if isinstance(build_sys, dict):
        backend = build_sys.get("build-backend")
        if isinstance(backend, str):
            entries.append(backend)
        for key in ("requires", "dependencies"):
            items = build_sys.get(key)
            if isinstance(items, list):
                entries.extend(item for item in items if isinstance(item, str))

    project = data.get("project")
    if isinstance(project, dict):
        deps = project.get("dependencies")
        if isinstance(deps, list):
            entries.extend(item for item in deps if isinstance(item, str))
        opt_deps = project.get("optional-dependencies")
        if isinstance(opt_deps, dict):
            for group_items in opt_deps.values():
                if isinstance(group_items, list):
                    entries.extend(item for item in group_items if isinstance(item, str))

    dep_groups = data.get("dependency-groups")
    if isinstance(dep_groups, dict):
        for group_items in dep_groups.values():
            if isinstance(group_items, list):
                entries.extend(item for item in group_items if isinstance(item, str))

    tool = data.get("tool")
    poetry = tool.get("poetry") if isinstance(tool, dict) else None
    if isinstance(poetry, dict):
        for key in ("dependencies", "dev-dependencies"):
            deps_map = poetry.get(key)
            if isinstance(deps_map, dict):
                entries.extend(k for k in deps_map if isinstance(k, str))
        groups = poetry.get("group")
        if isinstance(groups, dict):
            for group_body in groups.values():
                if isinstance(group_body, dict) and isinstance(group_body.get("dependencies"), dict):
                    entries.extend(k for k in group_body["dependencies"] if isinstance(k, str))

    return entries


def parse_pyproject(path: Path, root: Path) -> dict[str, Any]:
    text = read_text_safe(path)
    haystack_entries: list[str] | None = None

    if path.suffix.lower() == ".toml":
        try:
            import tomllib  # Python 3.11+

            data = tomllib.loads(text)
            if isinstance(data, dict):
                haystack_entries = _extract_pyproject_dep_strings(data)
        except (ImportError, ValueError):
            haystack_entries = None

    if haystack_entries is not None:
        normalized_pool = [entry.lower().replace("_", "-") for entry in haystack_entries]
        markers = [
            m
            for m in PYPROJECT_MARKERS
            if any(
                re.search(rf"(?<![a-z0-9-]){re.escape(m)}(?![a-z0-9-])", entry)
                for entry in normalized_pool
            )
        ]
    else:
        no_comments = re.sub(r"#[^\n]*", "", text).lower().replace("_", "-")
        markers = [
            m
            for m in PYPROJECT_MARKERS
            if re.search(rf"(?<![a-z0-9-]){re.escape(m)}(?![a-z0-9-])", no_comments)
        ]

    return {"file": path.relative_to(root).as_posix(), "markers": markers}


def parse_requirements_markers(path: Path) -> list[str]:
    """Extract known Python stack markers from a requirements*.txt file."""
    text = read_text_safe(path)
    entries: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "--")):
            continue
        # Strip version specifiers, extras, markers, and direct URLs
        pkg_match = re.match(r"^([A-Za-z0-9_.-]+)", line)
        if pkg_match:
            entries.append(pkg_match.group(1).lower().replace("_", "-"))
    return [
        m
        for m in PYPROJECT_MARKERS
        if any(
            re.search(rf"(?<![a-z0-9-]){re.escape(m)}(?![a-z0-9-])", entry)
            for entry in entries
        )
    ]


def parse_conanfile_deps(path: Path) -> list[str]:
    """Extract top-level package names from conanfile.txt [requires] or conanfile.py."""
    text = read_text_safe(path)
    deps: list[str] = []
    if path.name == "conanfile.txt":
        in_requires = False
        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                in_requires = line.lower() in {"[requires]", "[tool_requires]", "[test_requires]"}
                continue
            if in_requires:
                pkg = line.split("/", 1)[0].strip()
                if pkg and pkg not in deps:
                    deps.append(pkg)
    else:
        for match in re.finditer(
            r'\bself\.(?:requires|test_requires|tool_requires)\s*\(\s*["\']([A-Za-z0-9_.-]+)/',
            text,
        ):
            pkg = match.group(1)
            if pkg and pkg not in deps:
                deps.append(pkg)
    return deps


def parse_meson_deps(path: Path) -> list[str]:
    """Extract dependency('name', ...) names from meson.build."""
    text = re.sub(r"#[^\n]*", "", read_text_safe(path))
    deps: list[str] = []
    for match in re.finditer(r"""\bdependency\s*\(\s*['"]([^'"]+)['"]""", text):
        pkg = match.group(1).strip()
        if pkg and pkg not in deps:
            deps.append(pkg)
    return deps


def _discover_theme_presets(skill_root: Path | None = None) -> set[str]:
    base = skill_root or Path(__file__).resolve().parent.parent
    presets_dir = base / "references" / "ui" / "themes" / "presets"
    if not presets_dir.is_dir():
        return set()
    return {p.name for p in presets_dir.iterdir() if p.is_dir()}


def _discover_custom_themes(skill_root: Path | None = None) -> set[str]:
    base = skill_root or Path(__file__).resolve().parent.parent
    custom_dir = base / "references" / "ui" / "themes" / "custom"
    if not custom_dir.is_dir():
        return set()
    return {
        p.name
        for p in custom_dir.iterdir()
        if p.is_dir() and (p / "DESIGN.md").is_file()
    }


def validate_cpp_stack_data(
    data: Any,
    root: Path,
    skill_stacks: set[str],
    skill_root: Path | None = None,
) -> dict[str, Any]:
    """Validate parsed cpp-stack.json data against cpp-stack.schema.json rules."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict):
        return {
            "present": True,
            "valid": False,
            "errors": ["Root JSON value must be an object."],
            "warnings": [],
        }

    for unknown_key in sorted(k for k in data if k not in CPP_STACK_ROOT_KEYS):
        errors.append(f"Unknown property at root: {unknown_key!r}.")

    if "$schema" in data and not isinstance(data["$schema"], str):
        errors.append("'$schema' must be a string.")

    ver = data.get("schemaVersion")
    if type(ver) is not int or ver != 1:
        errors.append(f"Unsupported or missing schemaVersion: {ver!r} (expected integer 1).")

    if "architecture" in data:
        arch = data["architecture"]
        if not isinstance(arch, str) or arch not in VALID_ARCHITECTURES:
            errors.append(f"Invalid architecture: {arch!r}.")

    if "stackMode" in data:
        stack_mode = data["stackMode"]
        if not isinstance(stack_mode, str) or stack_mode not in VALID_STACK_MODES:
            errors.append(f"Invalid stackMode: {stack_mode!r}.")

    components = data.get("components")
    if not isinstance(components, dict) or not components:
        errors.append("'components' must be a non-empty object.")
        components = {}

    catalog_matched: set[str] = set()
    custom_unlisted: set[str] = set()
    root_resolved = root.resolve()

    for comp_id, comp in components.items():
        if not isinstance(comp, dict):
            errors.append(f"Component '{comp_id}' must be an object.")
            continue

        for unknown_key in sorted(k for k in comp if k not in CPP_STACK_COMPONENT_KEYS):
            errors.append(f"Component '{comp_id}' has unknown property: {unknown_key!r}.")

        rel_path = comp.get("path")
        if not isinstance(rel_path, str) or not rel_path.strip():
            errors.append(f"Component '{comp_id}' is missing a valid 'path'.")
        else:
            if _is_absolute_or_anchored_path(rel_path):
                errors.append(f"Component '{comp_id}' path must be relative: {rel_path!r}.")
            elif "\\" in rel_path:
                errors.append(
                    f"Component '{comp_id}' path must use forward slashes ('/'): {rel_path!r}."
                )
            else:
                norm_path = Path(rel_path)
                resolved = (root / norm_path).resolve()
                try:
                    resolved.relative_to(root_resolved)
                except ValueError:
                    errors.append(f"Component '{comp_id}' path escapes repository root: {rel_path!r}.")
                else:
                    if not resolved.exists():
                        warnings.append(
                            f"Component '{comp_id}' path does not exist on disk: {rel_path!r}."
                        )

        if "role" in comp:
            role = comp["role"]
            if not isinstance(role, str) or role not in VALID_ROLES:
                errors.append(f"Component '{comp_id}' has invalid role: {role!r}.")

        if "target" in comp:
            target = comp["target"]
            if not isinstance(target, str) or not target.strip():
                errors.append(f"Component '{comp_id}' 'target' must be a non-empty string.")

        if "platforms" in comp:
            platforms = comp["platforms"]
            if not isinstance(platforms, list) or any(
                not isinstance(p, str) or p not in VALID_PLATFORMS for p in platforms
            ):
                errors.append(f"Component '{comp_id}' has invalid platforms: {platforms!r}.")
            elif len(set(platforms)) != len(platforms):
                errors.append(f"Component '{comp_id}' 'platforms' contains duplicate entries.")

        stack = comp.get("stack")
        if not isinstance(stack, list) or any(not isinstance(s, str) or not s.strip() for s in stack):
            errors.append(f"Component '{comp_id}' must have a 'stack' array of non-empty strings.")
        else:
            for item in stack:
                norm = item.strip().lower()
                mapped = CATALOG_ALIASES.get(norm, norm)
                if mapped in skill_stacks:
                    catalog_matched.add(mapped)
                else:
                    custom_unlisted.add(item)

        if "dependsOn" in comp:
            depends_on = comp["dependsOn"]
            if not isinstance(depends_on, list) or any(
                not isinstance(d, str) or not d.strip() for d in depends_on
            ):
                errors.append(
                    f"Component '{comp_id}' 'dependsOn' must be an array of component IDs."
                )
            else:
                if len(set(depends_on)) != len(depends_on):
                    errors.append(f"Component '{comp_id}' 'dependsOn' contains duplicate entries.")
                for dep_id in depends_on:
                    if dep_id not in components:
                        errors.append(
                            f"Component '{comp_id}' dependsOn unknown component '{dep_id}'."
                        )

    # Cycle detection via DFS (reports distinct cycles found during DFS without duplicating closing node)
    visiting: set[str] = set()
    visited: set[str] = set()
    reported_cycles: set[tuple[str, ...]] = set()

    def dfs(node: str, trail: list[str]) -> None:
        if node in visited:
            return
        if node in visiting:
            cycle_nodes = trail[trail.index(node) :]
            core = (
                cycle_nodes[:-1]
                if len(cycle_nodes) > 1 and cycle_nodes[0] == cycle_nodes[-1]
                else cycle_nodes
            )
            if core:
                min_idx = min(range(len(core)), key=lambda idx: core[idx])
                canon = tuple(core[min_idx:] + core[:min_idx])
            else:
                canon = tuple(cycle_nodes)
            if canon not in reported_cycles:
                reported_cycles.add(canon)
                errors.append(
                    f"Dependency cycle detected in dependsOn: {' -> '.join(cycle_nodes)}."
                )
            return
        visiting.add(node)
        comp = components.get(node)
        if isinstance(comp, dict) and isinstance(comp.get("dependsOn"), list):
            for dep in comp["dependsOn"]:
                if isinstance(dep, str) and dep in components:
                    dfs(dep, trail + [dep])
        visiting.remove(node)
        visited.add(node)

    for comp_id in components:
        dfs(comp_id, [comp_id])

    # UI theme and window checks
    if "ui" in data:
        ui = data["ui"]
        if not isinstance(ui, dict):
            errors.append("'ui' must be an object.")
        else:
            for unknown_key in sorted(k for k in ui if k not in CPP_STACK_UI_KEYS):
                errors.append(f"'ui' has unknown property: {unknown_key!r}.")

            if "theme" in ui:
                theme = ui["theme"]
                if not isinstance(theme, dict):
                    errors.append("'ui.theme' must be an object.")
                else:
                    for unknown_key in sorted(k for k in theme if k not in CPP_STACK_THEME_KEYS):
                        errors.append(f"'ui.theme' has unknown property: {unknown_key!r}.")

                    mode = theme.get("mode")
                    if "mode" not in theme:
                        errors.append("'ui.theme.mode' is required.")
                    elif not isinstance(mode, str) or mode not in VALID_THEME_MODES:
                        errors.append(f"Invalid ui.theme.mode: {mode!r}.")

                    theme_id = theme.get("id")
                    if "id" in theme and (not isinstance(theme_id, str) or not theme_id.strip()):
                        errors.append("'ui.theme.id' must be a non-empty string.")
                    elif mode == "preset" and "id" not in theme:
                        errors.append("ui.theme.mode is 'preset' but 'id' is missing.")
                    elif mode == "preset" and isinstance(theme_id, str) and theme_id.strip():
                        known_presets = _discover_theme_presets(skill_root)
                        if known_presets and theme_id not in known_presets:
                            errors.append(f"Unknown ui.theme.id preset: {theme_id!r}.")

                    if mode == "preset" and "source" in theme:
                        errors.append("ui.theme.mode is 'preset' and must not specify 'source'.")
                    if mode == "native" and ("id" in theme or "source" in theme):
                        errors.append(
                            "ui.theme.mode is 'native' and must not specify 'id' or 'source'."
                        )

                    if mode == "custom":
                        if not theme.get("id") and not theme.get("source"):
                            warnings.append("ui.theme.mode is 'custom' without 'id' or 'source'.")
                        elif (
                            isinstance(theme_id, str)
                            and theme_id.strip()
                            and "source" not in theme
                        ):
                            known_custom = _discover_custom_themes(skill_root)
                            if theme_id not in known_custom:
                                warnings.append(
                                    f"Unknown skill-level custom ui.theme.id without 'source': {theme_id!r}."
                                )

                    if "source" in theme:
                        source = theme["source"]
                        if not isinstance(source, str) or not source.strip():
                            errors.append("'ui.theme.source' must be a non-empty string.")
                        elif _is_absolute_or_anchored_path(source):
                            errors.append(f"ui.theme.source must be relative: {source!r}.")
                        elif "\\" in source:
                            errors.append(
                                f"ui.theme.source must use forward slashes ('/'): {source!r}."
                            )
                        else:
                            src_path = (root / source).resolve()
                            try:
                                src_path.relative_to(root_resolved)
                            except ValueError:
                                errors.append(
                                    f"ui.theme.source escapes repository root: {source!r}."
                                )
                            else:
                                if not src_path.is_file():
                                    warnings.append(
                                        f"ui.theme.source does not exist on disk: {source!r}."
                                    )

            if "windows" in ui:
                windows = ui["windows"]
                if not isinstance(windows, dict):
                    errors.append("'ui.windows' must be an object.")
                else:
                    for win_name, win_cfg in windows.items():
                        if not isinstance(win_cfg, dict):
                            errors.append(f"ui.windows['{win_name}'] must be an object.")
                            continue
                        for unknown_key in sorted(
                            k for k in win_cfg if k not in CPP_STACK_WINDOW_KEYS
                        ):
                            errors.append(
                                f"ui.windows['{win_name}'] has unknown property: {unknown_key!r}."
                            )
                        for field in ("layout", "theme"):
                            if field in win_cfg and (
                                not isinstance(win_cfg[field], str)
                                or not win_cfg[field].strip()
                            ):
                                errors.append(
                                    f"ui.windows['{win_name}'].{field} must be a non-empty string."
                                )

    return {
        "present": True,
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "catalogMatchedStacks": sorted(catalog_matched),
        "customUnlistedStacks": sorted(custom_unlisted),
    }


def validate_cpp_stack_json(root: Path, skill_stacks: set[str]) -> dict[str, Any]:
    cfg_path = root / "cpp-stack.json"
    if not cfg_path.is_file():
        return {"present": False}

    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"present": True, "valid": False, "errors": [f"Failed to parse JSON: {exc}"]}

    return validate_cpp_stack_data(data, root, skill_stacks)


def infer_project_profile(
    has_cpp: bool,
    cmake_info: list[dict[str, Any]],
    qmake_info: list[dict[str, Any]],
    vcpkg_info: list[dict[str, Any]],
    pkg_json_info: list[dict[str, Any]],
    pyproject_info: list[dict[str, Any]],
    proto_files: list[str],
    openapi_files: list[str],
    sql_files: list[str],
    py_files: list[str],
    qml_files: list[str],
    conan_files: list[str],
    meson_files: list[str],
    requirements_files: list[str] = (),
    has_python_package: bool = False,
    cmake_modules_info: list[dict[str, Any]] = (),
    qt_ui_files: list[str] = (),
    requirements_markers: list[str] = (),
    extra_cpp_packages: list[str] = (),
) -> dict[str, Any]:
    raw_packages: set[str] = set()
    has_boost_components = False
    for c in [*cmake_info, *cmake_modules_info]:
        for p in c["packages"]:
            raw_packages.add(p)
            if p.strip().lower().startswith(("boost_", "boost-")):
                has_boost_components = True
        for qc in c.get("qtComponents", []):
            raw_packages.add(qc)
        for bc in c.get("boostComponents", []):
            raw_packages.add(bc)
            has_boost_components = True
        if c.get("pythonBindingHint"):
            raw_packages.add("python-bindings")
        for fc in c.get("fetchContent", []):
            if fc.strip().lower() in CATALOG_ALIASES:
                raw_packages.add(fc)
    for v in vcpkg_info:
        for d in (*v.get("dependencies", []), *v.get("featureDependencies", [])):
            raw_packages.add(d)
            if d.strip().lower().startswith(("boost-", "boost_")):
                has_boost_components = True
    for ep in extra_cpp_packages:
        raw_packages.add(ep)
        if ep.strip().lower().startswith(("boost-", "boost_")):
            has_boost_components = True
    for q in qmake_info:
        for m in q.get("qtModules", []):
            raw_packages.add(f"qt::{m}")

    non_helper_pyproject = [
        p for p in pyproject_info if not _is_in_helper_dir(str(p.get("file", "")))
    ]
    non_helper_web = [
        w for w in pkg_json_info if not _is_in_helper_dir(str(w.get("file", "")))
    ]
    non_helper_reqs = [r for r in requirements_files if not _is_in_helper_dir(r)]

    for p in non_helper_pyproject:
        for m in p.get("markers", []):
            raw_packages.add(m)
    for m in requirements_markers:
        raw_packages.add(m)
    for w in non_helper_web:
        for h in w.get("frameworkHints", []):
            raw_packages.add(h)

    if proto_files:
        raw_packages.add("protobuf")
    if openapi_files:
        raw_packages.add("openapi")
    if qml_files:
        raw_packages.add("qt-quick")

    matched_tags: set[str] = set()
    unmapped: set[str] = set()
    for pkg in raw_packages:
        norm = pkg.strip().lower()
        if norm in CATALOG_ALIASES:
            matched_tags.add(CATALOG_ALIASES[norm])
        elif re.match(r"^qt(?:[56]|\$\{[^}]+\})?$", norm):
            # Umbrella Qt package
            continue
        elif (
            (qt_mod_match := re.match(r"^qt(?:[56]|\$\{[^}]+\})?::([a-z0-9_]+)$", norm))
            and qt_mod_match.group(1) in QT_STANDARD_EXTRA_MODULES
        ):
            # Built-in Qt foundation/secondary modules without dedicated stack guides
            continue
        elif norm in QT_UMBRELLA_PACKAGES or re.match(r"^qt[56](?:[a-z0-9_]+|-[a-z0-9_-]+)$", norm):
            # vcpkg Qt foundation ports or split Qt5/Qt6 CMake package (mapped via qtComponents)
            continue
        elif has_boost_components and norm in {
            "boost",
            "boost::system",
            "boost::thread",
            "boost_system",
            "boost_thread",
            "boost-system",
            "boost-thread",
        }:
            # Umbrella Boost package or common Boost runtime helpers
            continue
        elif norm in {"threads", "pkgconfig"} or re.match(r"^python[23]?$", norm):
            continue
        else:
            unmapped.add(pkg)

    has_qt = bool(
        qmake_info
        or qml_files
        or qt_ui_files
        or any(t in QT_ONLY_STACK_TAGS for t in matched_tags)
        or any(
            p.strip().lower() in QT_UMBRELLA_PACKAGES
            or re.match(r"^qt(?:[56]|\$\{[^}]+\})?(?:::|$)", p.strip(), re.IGNORECASE)
            or re.match(r"^qt[56](?:[a-z0-9_]+|-[a-z0-9_-]+)$", p.strip(), re.IGNORECASE)
            for p in raw_packages
        )
    )
    has_web = bool(non_helper_web)
    has_python = bool(
        non_helper_pyproject
        or non_helper_reqs
        or has_python_package
        or "python-bindings" in matched_tags
        or "python-service-stack" in matched_tags
    )

    layers = []
    if has_cpp or cmake_info or qmake_info or meson_files or vcpkg_info or conan_files:
        layers.append("cpp")
    if has_qt:
        layers.append("qt")
    if has_web:
        layers.append("web")
    if has_python:
        layers.append("python")

    frontend_kinds = [x for x in ("qt", "web", "python") if x in layers]
    if "cpp" in layers:
        if len(frontend_kinds) > 1:
            architecture = "hybrid"
        elif frontend_kinds == ["web"]:
            architecture = "cpp-web"
        elif frontend_kinds == ["qt"]:
            architecture = "cpp-qt"
        elif frontend_kinds == ["python"]:
            architecture = "cpp-python"
        else:
            architecture = "cpp-core"
    else:
        architecture = "unknown"

    return {
        "architecture": architecture,
        "detectedLayers": layers,
        "catalogStackTags": sorted(matched_tags),
        "unmappedPackages": sorted(unmapped),
        "hasSqlOrMigrations": bool(sql_files),
    }


def _has_cmake_signals(cm: dict[str, Any]) -> bool:
    return bool(
        cm.get("pythonBindingHint")
        or any(
            cm.get(k)
            for k in (
                "projects",
                "subdirectories",
                "executables",
                "libraries",
                "packages",
                "fetchContent",
                "qtComponents",
                "boostComponents",
            )
        )
    )


def inspect_repo(root: Path) -> dict[str, Any]:
    root = root.resolve()
    files = walk_repo(root)

    cmake_files: list[dict[str, Any]] = []
    cmake_module_files: list[dict[str, Any]] = []
    preset_files: list[dict[str, Any]] = []
    qmake_files: list[dict[str, Any]] = []
    vcpkg_files: list[dict[str, Any]] = []
    conan_files: list[str] = []
    meson_files: list[str] = []
    other_build_files: list[str] = []
    pyproject_files: list[dict[str, Any]] = []
    package_json_files: list[dict[str, Any]] = []
    requirements_files: list[str] = []
    requirements_markers: list[str] = []
    extra_cpp_packages: list[str] = []
    proto_files: list[str] = []
    openapi_files: list[str] = []
    sql_files: list[str] = []
    qml_files: list[str] = []
    qt_ui_files: list[str] = []
    py_files: list[str] = []
    has_cpp = False
    has_python_package = False

    custom_themes: list[str] = []
    project_conventions: list[str] = []
    ci_and_containers: list[str] = []

    for f in files:
        rel = f.relative_to(root).as_posix()
        name_lower = f.name.lower()
        suffix_lower = f.suffix.lower()

        if f.name == "CMakeLists.txt":
            cmake_files.append(parse_cmake_file(f, root))
        elif suffix_lower == ".cmake":
            cm = parse_cmake_file(f, root)
            if _has_cmake_signals(cm):
                cmake_module_files.append(cm)
        elif f.name in {"CMakePresets.json", "CMakeUserPresets.json"}:
            preset_files.append(parse_cmake_presets(f, root))
        elif suffix_lower in {".pro", ".pri"}:
            qmake_files.append(parse_qmake_file(f, root))
        elif f.name == "vcpkg.json":
            vcpkg_files.append(parse_vcpkg_json(f, root))
        elif f.name in {"conanfile.txt", "conanfile.py"}:
            conan_files.append(rel)
            extra_cpp_packages.extend(parse_conanfile_deps(f))
        elif f.name == "meson.build":
            meson_files.append(rel)
            extra_cpp_packages.extend(parse_meson_deps(f))
        elif suffix_lower in {".sln", ".vcxproj"} or f.name in {
            "Makefile",
            "GNUmakefile",
            "xmake.lua",
            "BUILD.bazel",
            "MODULE.bazel",
            "WORKSPACE",
            "WORKSPACE.bazel",
        }:
            other_build_files.append(rel)
        elif f.name in {"pyproject.toml", "setup.py"}:
            pyproject_files.append(parse_pyproject(f, root))
        elif f.name == "package.json":
            package_json_files.append(parse_package_json(f, root))
        elif re.match(r"^requirements.*\.txt$", name_lower):
            requirements_files.append(rel)
            if not _is_in_helper_dir(rel):
                requirements_markers.extend(parse_requirements_markers(f))
        elif suffix_lower == ".proto":
            proto_files.append(rel)
        elif re.match(r"^(openapi|swagger).*\.(ya?ml|json)$", name_lower):
            openapi_files.append(rel)
        elif suffix_lower == ".qml":
            qml_files.append(rel)
        elif suffix_lower in {".ui", ".qrc"}:
            qt_ui_files.append(rel)
        elif suffix_lower == ".py":
            py_files.append(rel)
            if f.name == "__init__.py" and not _is_in_helper_dir(rel):
                has_python_package = True
        elif suffix_lower in {
            ".c",
            ".cpp",
            ".cc",
            ".cxx",
            ".hpp",
            ".hh",
            ".hxx",
            ".h",
            ".inl",
            ".ixx",
            ".cppm",
            ".mm",
            ".m",
            ".cu",
            ".cuh",
        }:
            has_cpp = True

        if suffix_lower == ".sql" or (
            "migrations/" in rel.lower()
            and suffix_lower not in {".md", ".txt", ".rst"}
        ):
            sql_files.append(rel)

        if rel in {"DESIGN.md", "docs/DESIGN.md", "theme.json"}:
            custom_themes.append(rel)

        if (
            f.name
            in {
                ".clang-format",
                ".clang-tidy",
                ".editorconfig",
                "AGENTS.md",
                "GEMINI.md",
                "CLAUDE.md",
            }
            or rel == ".github/copilot-instructions.md"
            or (rel.startswith("docs/tasks/") and suffix_lower == ".md")
        ):
            project_conventions.append(rel)

        if (
            (rel.startswith(".github/workflows/") and suffix_lower in {".yml", ".yaml"})
            or name_lower == "dockerfile"
            or name_lower.startswith("dockerfile.")
            or re.match(r"^(docker-)?compose.*\.ya?ml$", name_lower)
        ):
            ci_and_containers.append(rel)

    inferred = infer_project_profile(
        has_cpp=has_cpp,
        cmake_info=cmake_files,
        qmake_info=qmake_files,
        vcpkg_info=vcpkg_files,
        pkg_json_info=package_json_files,
        pyproject_info=pyproject_files,
        proto_files=proto_files,
        openapi_files=openapi_files,
        sql_files=sql_files,
        py_files=py_files,
        qml_files=qml_files,
        conan_files=conan_files,
        meson_files=meson_files,
        requirements_files=requirements_files,
        has_python_package=has_python_package,
        cmake_modules_info=cmake_module_files,
        qt_ui_files=qt_ui_files,
        requirements_markers=requirements_markers,
        extra_cpp_packages=extra_cpp_packages,
    )

    cpp_stack_validation = validate_cpp_stack_json(root, KNOWN_CATALOG_SLUGS)

    return {
        "projectRoot": str(root),
        "buildSystems": {
            "cmake": cmake_files,
            "cmakeModules": cmake_module_files,
            "cmakePresets": preset_files,
            "qmake": qmake_files,
            "meson": meson_files,
            "other": sorted(other_build_files),
            "python": pyproject_files,
            "web": package_json_files,
        },
        "dependencyManifests": {
            "vcpkg": vcpkg_files,
            "conan": conan_files,
            "requirements": requirements_files,
        },
        "interfacesAndData": {
            "protoFiles": proto_files,
            "openapiFiles": openapi_files,
            "sqlOrMigrationFiles": sql_files[:25],
            "sqlOrMigrationFilesCount": len(sql_files),
            "qmlFilesCount": len(qml_files),
        },
        "customThemes": sorted(custom_themes),
        "projectConventions": sorted(project_conventions),
        "ciAndContainers": sorted(ci_and_containers),
        "cppStackJson": cpp_stack_validation,
        "inferred": inferred,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only inspection of a C++ full-stack repository and optional cpp-stack.json."
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=".",
        help="Path to the project root (defaults to current working directory).",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Emit compact JSON.",
    )
    args = parser.parse_args()

    root = Path(args.project_root)
    if not root.is_dir():
        print(
            json.dumps({"error": f"Project root does not exist: {root}"}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1

    result = inspect_repo(root)
    print(json.dumps(result, indent=None if args.compact else 2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
