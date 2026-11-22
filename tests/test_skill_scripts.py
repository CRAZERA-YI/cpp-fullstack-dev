#!/usr/bin/env python3
"""Zero-dependency unittest suite for cpp-fullstack-dev scripts."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import extract_theme as et  # noqa: E402
import inspect_project as ip  # noqa: E402
import probe_env as pe  # noqa: E402
import validate_skill as vs  # noqa: E402


class InspectProjectTests(unittest.TestCase):
    def test_pure_cpp_with_libcurl_not_misclassified_as_qt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CMakeLists.txt").write_text(
                "project(http_daemon)\nfind_package(CURL REQUIRED)\nadd_executable(daemon main.cpp)\n",
                encoding="utf-8",
            )
            (root / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
            res = ip.inspect_repo(root)
            inferred = res["inferred"]
            self.assertEqual(inferred["architecture"], "cpp-core")
            self.assertEqual(inferred["detectedLayers"], ["cpp"])
            self.assertNotIn("qt", inferred["detectedLayers"])
            self.assertIn("qt-network-client", inferred["catalogStackTags"])

    def test_pure_cpp_with_helper_py_not_misclassified_as_python(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CMakeLists.txt").write_text(
                "project(core_lib)\nadd_library(core src/core.cpp)\n",
                encoding="utf-8",
            )
            (root / "src").mkdir()
            (root / "src" / "core.cpp").write_text("int add(int a, int b) { return a + b; }\n", encoding="utf-8")
            (root / "scripts").mkdir()
            (root / "scripts" / "codegen.py").write_text("print('ok')\n", encoding="utf-8")
            res = ip.inspect_repo(root)
            inferred = res["inferred"]
            self.assertEqual(inferred["architecture"], "cpp-core")
            self.assertNotIn("python", inferred["detectedLayers"])

    def test_cpp_python_via_pyproject_and_nanobind_cmake(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CMakeLists.txt").write_text(
                "project(fast_ext)\n"
                "find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)\n"
                "nanobind_add_module(_ext src/bind.cpp)\n",
                encoding="utf-8",
            )
            (root / "pyproject.toml").write_text(
                '[build-system]\nbuild-backend = "scikit_build_core.build"\n'
                'dependencies = ["nanobind"]\n',
                encoding="utf-8",
            )
            (root / "src").mkdir()
            (root / "src" / "bind.cpp").write_text("// binding\n", encoding="utf-8")
            res = ip.inspect_repo(root)
            inferred = res["inferred"]
            self.assertEqual(inferred["architecture"], "cpp-python")
            self.assertIn("python", inferred["detectedLayers"])
            self.assertIn("python-bindings", inferred["catalogStackTags"])
            self.assertIn("_ext", res["buildSystems"]["cmake"][0]["libraries"])

    def test_cmake_find_package_stops_at_paths_keyword(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CMakeLists.txt").write_text(
                "project(qt_app)\n"
                "find_package(Qt6 REQUIRED COMPONENTS Widgets PATHS /opt/qt NO_DEFAULT_PATH)\n",
                encoding="utf-8",
            )
            res = ip.inspect_repo(root)
            cmake_entry = res["buildSystems"]["cmake"][0]
            self.assertEqual(cmake_entry["qtComponents"], ["qt::Widgets"])
            self.assertEqual(res["inferred"]["unmappedPackages"], [])

    def test_cmake_modern_qt_macros_and_bracket_comments(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CMakeLists.txt").write_text(
                "#[[ Ignored comment:\nfind_package(FakePkg REQUIRED)\n]]\n"
                "project(qml_app)\n"
                "find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS Widgets)\n"
                "qt_add_executable(desktop_app main.cpp)\n"
                "qt_add_qml_module(qml_mod URI Demo VERSION 1.0)\n",
                encoding="utf-8",
            )
            res = ip.inspect_repo(root)
            cmake_entry = res["buildSystems"]["cmake"][0]
            self.assertNotIn("FakePkg", cmake_entry["packages"])
            self.assertIn("desktop_app", cmake_entry["executables"])
            self.assertIn("qml_mod", cmake_entry["libraries"])
            self.assertIn("qt::Widgets", cmake_entry["qtComponents"])
            self.assertIn("qt::Quick", cmake_entry["qtComponents"])
            self.assertEqual(res["inferred"]["architecture"], "cpp-qt")

    def test_qmake_multiline_comments_and_minus_equals(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "app.pro").write_text(
                "# QT += sql\n"
                "TEMPLATE = app\n"
                "QT += core \\\n"
                "      gui \\ # inline comment\n"
                "      widgets # final comment\n"
                "QT -= gui\n",
                encoding="utf-8",
            )
            res = ip.inspect_repo(root)
            qmake_entry = res["buildSystems"]["qmake"][0]
            self.assertEqual(qmake_entry["template"], "app")
            self.assertEqual(qmake_entry["qtModules"], ["core", "widgets"])
            self.assertEqual(res["inferred"]["architecture"], "cpp-qt")
            self.assertEqual(res["inferred"]["catalogStackTags"], ["qt-widgets"])

    def test_vcpkg_feature_dependencies_detected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "vcpkg.json").write_text(
                json.dumps(
                    {
                        "name": "sample",
                        "dependencies": ["fmt"],
                        "features": {
                            "sqlite": {
                                "description": "sqlite support",
                                "dependencies": ["sqlite3"],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            res = ip.inspect_repo(root)
            vcpkg_entry = res["dependencyManifests"]["vcpkg"][0]
            self.assertEqual(vcpkg_entry["featureDependencies"], ["sqlite3"])
            self.assertIn("sqlite", res["inferred"]["catalogStackTags"])

    def test_docs_manifests_do_not_misclassify_pure_cpp(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CMakeLists.txt").write_text(
                "project(pure_cpp)\nadd_executable(app main.cpp)\n",
                encoding="utf-8",
            )
            (root / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "requirements.txt").write_text("sphinx>=7.0\n", encoding="utf-8")
            (root / "docs" / "package.json").write_text(
                json.dumps({"name": "docs-site", "dependencies": {"vite": "^5.0", "react": "^18.0"}}),
                encoding="utf-8",
            )
            res = ip.inspect_repo(root)
            self.assertEqual(res["inferred"]["architecture"], "cpp-core")
            self.assertEqual(res["inferred"]["detectedLayers"], ["cpp"])
            self.assertEqual(res["inferred"]["catalogStackTags"], [])

    def test_vcpkg_qt_cmake_modules_modular_boost_and_split_qt5(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CMakeLists.txt").write_text(
                "project(qt_srv)\ninclude(cmake/Deps.cmake)\nadd_executable(app main.cpp)\n",
                encoding="utf-8",
            )
            (root / "cmake").mkdir()
            (root / "cmake" / "Deps.cmake").write_text(
                "find_package(boost_asio CONFIG REQUIRED)\n",
                encoding="utf-8",
            )
            (root / "vcpkg.json").write_text(
                json.dumps({"name": "qt-srv", "dependencies": ["qtbase", "qtdeclarative"]}),
                encoding="utf-8",
            )
            (root / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
            res = ip.inspect_repo(root)
            self.assertEqual(len(res["buildSystems"]["cmakeModules"]), 1)
            self.assertEqual(res["inferred"]["architecture"], "cpp-qt")
            self.assertEqual(res["inferred"]["unmappedPackages"], [])
            self.assertIn("qt-quick", res["inferred"]["catalogStackTags"])
            self.assertIn("boost-asio-beast", res["inferred"]["catalogStackTags"])

        with tempfile.TemporaryDirectory() as td2:
            root2 = Path(td2)
            (root2 / "CMakeLists.txt").write_text(
                "project(legacy_qt)\nfind_package(Qt5Widgets REQUIRED)\nadd_executable(gui main.cpp)\n",
                encoding="utf-8",
            )
            res2 = ip.inspect_repo(root2)
            self.assertEqual(res2["buildSystems"]["cmake"][0]["qtComponents"], ["qt::Widgets"])
            self.assertEqual(res2["inferred"]["architecture"], "cpp-qt")
            self.assertEqual(res2["inferred"]["catalogStackTags"], ["qt-widgets"])
            self.assertEqual(res2["inferred"]["unmappedPackages"], [])

    def test_cmake_alias_excluded_and_hash_inside_string_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CMakeLists.txt").write_text(
                'project(demo)\n'
                'add_library(core src/core.cpp)\n'
                'add_library(demo::core ALIAS core)\n'
                'set(ACCENT "#ff0000")\n'
                'find_package(nlohmann_json CONFIG REQUIRED) # trailing comment\n',
                encoding="utf-8",
            )
            res = ip.inspect_repo(root)
            cmake_entry = res["buildSystems"]["cmake"][0]
            self.assertEqual(cmake_entry["libraries"], ["core"])
            self.assertEqual(cmake_entry["packages"], ["nlohmann_json"])
            self.assertIn("json", res["inferred"]["catalogStackTags"])

    def test_utf8_bom_manifests_pyproject_comments_and_conventions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CMakeLists.txt").write_text(
                "project(hybrid_app)\nadd_executable(app main.cpp)\n",
                encoding="utf-8",
            )
            (root / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
            (root / "vcpkg.json").write_bytes(
                b"\xef\xbb\xbf" + json.dumps({"name": "bom-app", "dependencies": ["fmt"]}).encode("utf-8")
            )
            (root / "cpp-stack.json").write_bytes(
                b"\xef\xbb\xbf"
                + json.dumps(
                    {
                        "schemaVersion": 1,
                        "components": {"app": {"path": ".", "stack": ["cpp-core-utils"]}},
                    }
                ).encode("utf-8")
            )
            (root / "pyproject.toml").write_text(
                '[build-system]\n'
                'requires = ["scikit_build_core>=0.9", "nanobind>=2.0"]\n'
                'build-backend = "scikit_build_core.build"\n'
                '[project]\n'
                'name = "demo"\n'
                'description = "not using fastapi or grpcio"\n'
                '# dependencies = ["pytest"]\n',
                encoding="utf-8",
            )
            (root / ".clang-format").write_text("BasedOnStyle: LLVM\n", encoding="utf-8")
            (root / ".clang-tidy").write_text("Checks: '-*,bugprone-*'\n", encoding="utf-8")
            (root / "AGENTS.md").write_text("# rules\n", encoding="utf-8")
            (root / "docs" / "tasks").mkdir(parents=True)
            (root / "docs" / "tasks" / "t1.md").write_text("# handoff\n", encoding="utf-8")
            (root / "migrations").mkdir()
            (root / "migrations" / "001_init.py").write_text("def upgrade(): pass\n", encoding="utf-8")
            (root / "migrations" / "README.md").write_text("# migrations\n", encoding="utf-8")

            res = ip.inspect_repo(root)
            self.assertNotIn("error", res["dependencyManifests"]["vcpkg"][0])
            self.assertTrue(res["cppStackJson"]["valid"])
            self.assertEqual(
                res["buildSystems"]["python"][0]["markers"],
                ["scikit-build-core", "nanobind"],
            )
            self.assertEqual(
                res["projectConventions"],
                [".clang-format", ".clang-tidy", "AGENTS.md", "docs/tasks/t1.md"],
            )
            self.assertEqual(res["interfacesAndData"]["sqlOrMigrationFiles"], ["migrations/001_init.py"])
            self.assertEqual(res["interfacesAndData"]["sqlOrMigrationFilesCount"], 1)

    def test_cmake_bracket_arg_with_odd_quote_imported_and_python_embed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CMakeLists.txt").write_text(
                'project(embed_demo)\n'
                'set(CMAKE_CXX_STANDARD 20)\n'
                'set(HELP [[ odd quote " inside bracket arg ]])\n'
                '# find_package(FakeCommentedPkg REQUIRED)\n'
                'find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Embed)\n'
                'add_library(ext::foo SHARED IMPORTED)\n'
                'add_executable(app main.cpp)\n',
                encoding="utf-8",
            )
            (root / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
            res = ip.inspect_repo(root)
            cm = res["buildSystems"]["cmake"][0]
            self.assertNotIn("FakeCommentedPkg", cm["packages"])
            self.assertNotIn("ext::foo", cm["libraries"])
            self.assertEqual(cm["executables"], ["app"])
            self.assertTrue(cm["pythonBindingHint"])
            self.assertEqual(cm["cxxStandards"], ["c++20"])
            self.assertEqual(res["inferred"]["architecture"], "cpp-python")
            self.assertIn("python-bindings", res["inferred"]["catalogStackTags"])

    def test_qmake_chained_scopes_and_non_qt_qtoml_not_misclassified(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "app.pro").write_text(
                "win32:debug: QT += widgets\n"
                "greaterThan(QT_MAJOR_VERSION, 4):unix: QT += network\n",
                encoding="utf-8",
            )
            res = ip.inspect_repo(root)
            self.assertEqual(res["buildSystems"]["qmake"][0]["qtModules"], ["widgets", "network"])
            self.assertEqual(res["inferred"]["architecture"], "cpp-qt")
            self.assertIn("qt-widgets", res["inferred"]["catalogStackTags"])
            self.assertIn("qt-network-client", res["inferred"]["catalogStackTags"])

        with tempfile.TemporaryDirectory() as td2:
            root2 = Path(td2)
            (root2 / "CMakeLists.txt").write_text(
                "project(cfg)\nfind_package(qtoml REQUIRED)\nadd_executable(cfg main.cpp)\n",
                encoding="utf-8",
            )
            (root2 / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
            res2 = ip.inspect_repo(root2)
            self.assertEqual(res2["inferred"]["architecture"], "cpp-core")
            self.assertNotIn("qt", res2["inferred"]["detectedLayers"])

    def test_boost_header_only_vcpkg_requirements_conan_meson_and_ci(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CMakeLists.txt").write_text(
                "project(net_srv)\nfind_package(Boost REQUIRED)\nadd_executable(srv main.cpp)\n",
                encoding="utf-8",
            )
            (root / "vcpkg.json").write_text(
                json.dumps({"name": "net-srv", "dependencies": ["boost-asio", "boost-beast"]}),
                encoding="utf-8",
            )
            (root / "requirements.txt").write_text(
                "# web gateway deps\nfastapi>=0.115\nuvicorn[standard]>=0.30\npytest\n",
                encoding="utf-8",
            )
            (root / "conanfile.txt").write_text(
                "[requires]\nspdlog/1.14.1\n",
                encoding="utf-8",
            )
            (root / "meson.build").write_text(
                "dep = dependency('sqlite3')\n",
                encoding="utf-8",
            )
            (root / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
            (root / "GEMINI.md").write_text("# rules\n", encoding="utf-8")
            (root / "CLAUDE.md").write_text("# rules\n", encoding="utf-8")
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "workflows" / "ci.yml").write_text("name: CI\n", encoding="utf-8")
            (root / "Dockerfile").write_text("FROM ubuntu:24.04\n", encoding="utf-8")

            res = ip.inspect_repo(root)
            inferred = res["inferred"]
            self.assertEqual(inferred["architecture"], "cpp-python")
            self.assertEqual(inferred["unmappedPackages"], [])
            for tag in (
                "boost-asio-beast",
                "python-service-stack",
                "observability-security",
                "sqlite",
                "testing",
            ):
                self.assertIn(tag, inferred["catalogStackTags"])
            self.assertIn("GEMINI.md", res["projectConventions"])
            self.assertIn("CLAUDE.md", res["projectConventions"])
            self.assertEqual(res["ciAndContainers"], [".github/workflows/ci.yml", "Dockerfile"])

    def test_malformed_non_object_json_manifests_do_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CMakePresets.json").write_text(
                '{"version": 4, "configurePresets": null}',
                encoding="utf-8",
            )
            (root / "vcpkg.json").write_text("[]", encoding="utf-8")
            (root / "package.json").write_text("[]", encoding="utf-8")
            res = ip.inspect_repo(root)
            self.assertEqual(res["buildSystems"]["cmakePresets"][0]["configurePresets"], [])
            self.assertIn("error", res["dependencyManifests"]["vcpkg"][0])
            self.assertIn("error", res["buildSystems"]["web"][0])

    def test_agent_skill_dirs_are_pruned_from_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for agent_dir in (".agents", ".claude", ".codex"):
                tpl_dir = root / agent_dir / "skills" / "cpp-fullstack-dev" / "assets" / "templates"
                tpl_dir.mkdir(parents=True)
                (tpl_dir / "CMakeLists.txt").write_text(
                    "project(template_app)\nadd_executable(app main.cpp)\n",
                    encoding="utf-8",
                )
                (tpl_dir / "vcpkg.json").write_text(
                    json.dumps({"name": "tpl", "dependencies": ["sqlite3", "spdlog"]}),
                    encoding="utf-8",
                )
            res = ip.inspect_repo(root)
            self.assertEqual(res["buildSystems"]["cmake"], [])
            self.assertEqual(res["dependencyManifests"]["vcpkg"], [])
            self.assertEqual(res["inferred"]["architecture"], "unknown")
            self.assertEqual(res["inferred"]["detectedLayers"], [])


class CppStackJsonValidationTests(unittest.TestCase):
    def test_rejects_bool_schema_version_unknown_keys_and_bad_ui(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "cpp-stack.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": True,
                        "extraRoot": 1,
                        "ui": "not-an-object",
                        "components": {
                            "app": {
                                "path": ".",
                                "stack": ["drogon"],
                                "unknownField": "x",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            res = ip.validate_cpp_stack_json(root, ip.KNOWN_CATALOG_SLUGS)
            self.assertFalse(res["valid"])
            joined = "\n".join(res["errors"])
            self.assertIn("schemaVersion", joined)
            self.assertIn("extraRoot", joined)
            self.assertIn("'ui' must be an object", joined)
            self.assertIn("unknownField", joined)

    def test_cycle_detection_format_and_self_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "cpp-stack.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "components": {
                            "a": {"path": ".", "stack": ["drogon"], "dependsOn": ["b"]},
                            "b": {"path": ".", "stack": ["sqlite"], "dependsOn": ["a"]},
                            "c": {"path": ".", "stack": ["json"], "dependsOn": ["c"]},
                        },
                    }
                ),
                encoding="utf-8",
            )
            res = ip.validate_cpp_stack_json(root, ip.KNOWN_CATALOG_SLUGS)
            self.assertFalse(res["valid"])
            cycle_errors = [e for e in res["errors"] if "Dependency cycle detected" in e]
            self.assertEqual(len(cycle_errors), 2)
            joined = "\n".join(cycle_errors)
            self.assertIn("a -> b -> a.", joined)
            self.assertNotIn("a -> b -> a -> a", joined)
            self.assertIn("c -> c.", joined)
            self.assertNotIn("c -> c -> c", joined)

    def test_ui_theme_source_escape_absolute_empty_and_missing_component_warning(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for bad_source in ("../secret/DESIGN.md", str(root / "DESIGN.md"), ""):
                (root / "cpp-stack.json").write_text(
                    json.dumps(
                        {
                            "schemaVersion": 1,
                            "components": {
                                "app": {"path": "missing_dir", "stack": ["drogon"]}
                            },
                            "ui": {
                                "theme": {
                                    "mode": "custom",
                                    "source": bad_source,
                                }
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                res = ip.validate_cpp_stack_json(root, ip.KNOWN_CATALOG_SLUGS)
                self.assertFalse(res["valid"])
                self.assertTrue(
                    any("missing_dir" in w for w in res["warnings"]),
                    f"Expected missing component path warning, got {res['warnings']}",
                )
                self.assertFalse(
                    any("ui.theme.source does not exist" in w for w in res["warnings"]),
                    f"Invalid/escaping source must not emit disk-existence warning: {res['warnings']}",
                )

    def test_minimal_template_validates_cleanly(self) -> None:
        tpl_path = SKILL_ROOT / "assets" / "templates" / "cpp-stack.json"
        data = json.loads(tpl_path.read_text(encoding="utf-8"))
        res = ip.validate_cpp_stack_data(
            data,
            tpl_path.parent,
            ip.KNOWN_CATALOG_SLUGS,
            skill_root=SKILL_ROOT,
        )
        self.assertTrue(res["valid"], msg=f"Template errors: {res.get('errors')}")
        self.assertEqual(res["errors"], [])

    def test_rejects_anchored_paths_and_preset_without_id_and_warns_unknown_custom_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bad_paths = ["/etc/passwd", "\\\\server\\share\\x"]
            if os.name == "nt":
                bad_paths.append("C:foo")
            for bad_path in bad_paths:
                res = ip.validate_cpp_stack_data(
                    {
                        "schemaVersion": 1,
                        "components": {"app": {"path": bad_path, "stack": ["drogon"]}},
                    },
                    root,
                    ip.KNOWN_CATALOG_SLUGS,
                    skill_root=SKILL_ROOT,
                )
                self.assertFalse(res["valid"], msg=f"Expected rejection for path {bad_path!r}")

            missing_id = ip.validate_cpp_stack_data(
                {
                    "schemaVersion": 1,
                    "components": {"app": {"path": ".", "stack": ["drogon"]}},
                    "ui": {"theme": {"mode": "preset"}},
                },
                root,
                ip.KNOWN_CATALOG_SLUGS,
                skill_root=SKILL_ROOT,
            )
            self.assertFalse(missing_id["valid"])
            self.assertTrue(any("missing" in e for e in missing_id["errors"]))

            unknown_custom = ip.validate_cpp_stack_data(
                {
                    "schemaVersion": 1,
                    "components": {"app": {"path": ".", "stack": ["drogon"]}},
                    "ui": {"theme": {"mode": "custom", "id": "nonexistent-custom-theme"}},
                },
                root,
                ip.KNOWN_CATALOG_SLUGS,
                skill_root=SKILL_ROOT,
            )
            self.assertTrue(unknown_custom["valid"])
            self.assertTrue(
                any("nonexistent-custom-theme" in w for w in unknown_custom["warnings"])
            )

    def test_rejects_unhashable_types_float_version_backslashes_and_theme_contradictions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            invalid_payloads = [
                {
                    "schemaVersion": 1.0,
                    "components": {"app": {"path": ".", "stack": []}},
                },
                {
                    "schemaVersion": 1,
                    "architecture": [],
                    "stackMode": {},
                    "components": {
                        "app": {
                            "path": "apps\\desktop",
                            "role": [],
                            "platforms": [{}],
                            "stack": [],
                        }
                    },
                    "ui": {"theme": {"mode": []}},
                },
                {
                    "schemaVersion": 1,
                    "components": {"app": {"path": "C:/abs/path", "stack": []}},
                },
                {
                    "schemaVersion": 1,
                    "components": {"app": {"path": "C:rel", "stack": []}},
                },
                {
                    "schemaVersion": 1,
                    "components": {"app": {"path": ".", "stack": []}},
                    "ui": {"theme": {"id": "linear"}},
                },
                {
                    "schemaVersion": 1,
                    "components": {"app": {"path": ".", "stack": []}},
                    "ui": {"theme": {"mode": "native", "source": "DESIGN.md"}},
                },
                {
                    "schemaVersion": 1,
                    "components": {"app": {"path": ".", "stack": []}},
                    "ui": {"theme": {"mode": "preset", "id": "linear", "source": "DESIGN.md"}},
                },
            ]
            for payload in invalid_payloads:
                res = ip.validate_cpp_stack_data(
                    payload, root, ip.KNOWN_CATALOG_SLUGS, skill_root=SKILL_ROOT
                )
                self.assertFalse(res["valid"], msg=f"Expected invalid for {payload!r}")
                self.assertTrue(res["errors"])


class ProbeEnvTests(unittest.TestCase):
    def test_run_version_nonzero_exit_and_join_lines(self) -> None:
        fail_res = pe.run_version(
            [sys.executable, "-c", "import sys; print('err text'); sys.exit(2)"],
            require_zero_exit=True,
        )
        self.assertFalse(fail_res["found"])
        self.assertEqual(fail_res.get("returncode"), 2)

        multi_res = pe.run_version(
            [sys.executable, "-c", "print('line1'); print('line2')"],
            join_lines=True,
        )
        self.assertTrue(multi_res["found"])
        self.assertEqual(multi_res["version"], "line1 | line2")

    def test_prefer_stderr_decode_fallback_shim_markers_and_hints(self) -> None:
        stderr_res = pe.run_version(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdout.write('Usage: tool\\n'); "
                "sys.stderr.write('Compiler Version 19.44\\n')",
            ],
            prefer_stderr=True,
        )
        self.assertTrue(stderr_res["found"])
        self.assertIn("Version 19.44", stderr_res["version"])

        gbk_bytes = "用法: NMAKE @commandfile".encode("gbk")
        with mock.patch.object(pe.locale, "getpreferredencoding", return_value="gbk"):
            decoded = pe._decode_output(gbk_bytes)
        self.assertIn("用法", decoded)
        self.assertIn("NMAKE", decoded)

        nmake_gbk = "Microsoft (R) 程序维护实用工具".encode("gbk")
        with (
            mock.patch.object(pe.locale, "getpreferredencoding", return_value="utf-8"),
            mock.patch.object(pe.locale, "getencoding", return_value="gbk", create=True),
        ):
            decoded_utf8_mode = pe._decode_output(nmake_gbk)
        self.assertIn("程序维护实用工具", decoded_utf8_mode)
        self.assertNotIn("\ufffd", decoded_utf8_mode)

        self.assertTrue(pe._is_broken_shim("'foo' 不是内部或外部命令"))
        self.assertTrue(pe._is_broken_shim("Install from the Microsoft Store"))

        fake_report_clang = {
            "platform": {"system": "Windows", "isWsl": False},
            "compilers": {
                "cl": {"found": False},
                "clang-cl": {"found": False},
                "g++": {"found": False},
                "clang++": {"found": True},
            },
            "visualStudio": {"installations": []},
            "buildTools": {"cmake": {"found": True}, "ninja": {"found": True}},
            "packageManagers": {"vcpkg": {"vcpkgRoot": "C:\\vcpkg", "toolchainFile": "C:\\vcpkg\\scripts\\buildsystems\\vcpkg.cmake"}},
        }
        hints_clang = pe.build_hints(fake_report_clang)
        self.assertFalse(any("No MSVC" in h for h in hints_clang))

        fake_report_vs = {
            "platform": {"system": "Windows", "isWsl": False},
            "compilers": {
                "cl": {"found": False},
                "clang-cl": {"found": False},
                "g++": {"found": False},
                "clang++": {"found": False},
            },
            "visualStudio": {
                "installations": [
                    {
                        "vcvars64": "X:\\vcvars64.bat",
                        "bundledCmake": "X:\\cmake.exe",
                        "bundledNinja": "X:\\ninja.exe",
                        "bundledVcpkg": "X:\\vcpkg",
                    }
                ]
            },
            "buildTools": {"cmake": {"found": False}, "ninja": {"found": False}},
            "packageManagers": {"vcpkg": {"vcpkgRoot": None, "toolchainFile": None}},
        }
        hints_vs = pe.build_hints(fake_report_vs)
        joined_hints = "\n".join(hints_vs)
        self.assertIn("X:\\vcvars64.bat", joined_hints)
        self.assertIn("X:\\cmake.exe", joined_hints)
        self.assertIn("X:\\ninja.exe", joined_hints)
        self.assertIn("X:\\vcpkg", joined_hints)
        self.assertIn("does NOT set VCPKG_ROOT", joined_hints)

    def test_vs_hints_prefer_cpp_install_clang_tools_and_qt_abi_mismatch(self) -> None:
        fake_report = {
            "platform": {"system": "Windows", "isWsl": False},
            "compilers": {
                "cl": {"found": False},
                "clang-cl": {"found": False},
                "g++": {"found": True},
                "clang++": {"found": False},
            },
            "visualStudio": {
                "installations": [
                    {
                        "vsDevCmd": "D:\\VS_DotNetOnly\\VsDevCmd.bat",
                        "vcvars64": None,
                        "bundledClangFormat": "D:\\VS_Cpp\\clang-format.exe",
                        "bundledClangTidy": "D:\\VS_Cpp\\clang-tidy.exe",
                    },
                    {
                        "vsDevCmd": "D:\\VS_Cpp\\VsDevCmd.bat",
                        "vcvars64": "D:\\VS_Cpp\\vcvars64.bat",
                    },
                ]
            },
            "buildTools": {"cmake": {"found": True}, "ninja": {"found": True}},
            "qualityTools": {
                "clang-format": {"found": False},
                "clang-tidy": {"found": False},
            },
            "qtEnv": {"qmakeSpec": "win32-msvc"},
            "packageManagers": {"vcpkg": {"vcpkgRoot": "C:\\vcpkg", "toolchainFile": "C:\\vcpkg\\scripts\\buildsystems\\vcpkg.cmake"}},
        }
        hints = "\n".join(pe.build_hints(fake_report))
        self.assertIn("D:\\VS_Cpp\\vcvars64.bat", hints)
        self.assertNotIn("D:\\VS_DotNetOnly\\VsDevCmd.bat", hints)
        self.assertIn("D:\\VS_Cpp\\clang-format.exe", hints)
        self.assertIn("D:\\VS_Cpp\\clang-tidy.exe", hints)
        self.assertIn("do not mix MinGW with MSVC Qt", hints)


class ValidateSkillTests(unittest.TestCase):
    def test_cmake_presets_catches_hidden_ref_and_bad_inherits(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tpl_dir = root / "assets" / "templates"
            tpl_dir.mkdir(parents=True)
            (tpl_dir / "CMakePresets.json").write_text(
                json.dumps(
                    {
                        "version": 4,
                        "cmakeMinimumRequired": {"major": 3, "minor": 23, "patch": 0},
                        "configurePresets": [
                            {"name": "base", "hidden": True},
                            {"name": "bad", "inherits": "missing-parent"},
                        ],
                        "buildPresets": [
                            {"name": "use-hidden", "configurePreset": "base"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            errors: list[str] = []
            vs.check_cmake_presets_template(root, errors)
            joined = "\n".join(errors)
            self.assertIn("inherits unknown preset 'missing-parent'", joined)
            self.assertIn("references hidden configurePreset 'base'", joined)

    def test_markdown_links_catches_broken_escaping_and_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            root = parent / "skill"
            (root / "references").mkdir(parents=True)
            (parent / "outside.md").write_text("# outside\n", encoding="utf-8")
            (root / "references" / "linked.md").write_text("# ok\n", encoding="utf-8")
            (root / "references" / "orphan.md").write_text("# unused\n", encoding="utf-8")
            (root / "SKILL.md").write_text(
                "[ok](references/linked.md)\n"
                "[missing](references/missing.md)\n"
                "[escape](../outside.md)\n",
                encoding="utf-8",
            )
            errors: list[str] = []
            vs.check_markdown_links(root, errors)
            joined = "\n".join(errors)
            self.assertIn("Broken link", joined)
            self.assertIn("Link escapes skill root", joined)
            self.assertIn("Orphaned reference document", joined)
            self.assertIn("orphan.md", joined)

    def test_markdown_links_catches_backtick_links_circular_and_readme_only_orphans(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "references").mkdir()
            (root / "references" / "a.md").write_text("[b](b.md)\n", encoding="utf-8")
            (root / "references" / "b.md").write_text("[a](a.md)\n", encoding="utf-8")
            (root / "references" / "readme_only.md").write_text("# readme only\n", encoding="utf-8")
            (root / "README.md").write_text("[ro](references/readme_only.md)\n", encoding="utf-8")
            (root / "SKILL.md").write_text(
                "---\nname: cpp-fullstack-dev\ndescription: demo\n---\n"
                "[`.clang-format`](assets/missing.txt)\n"
                "Inline example `[ignored](definitely_missing.md)` should be ignored.\n",
                encoding="utf-8",
            )
            errors: list[str] = []
            vs.check_markdown_links(root, errors)
            joined = "\n".join(errors)
            self.assertIn("assets/missing.txt", joined)
            self.assertNotIn("definitely_missing.md", joined)
            self.assertIn("references/a.md", joined)
            self.assertIn("references/b.md", joined)
            self.assertIn("references/readme_only.md", joined)

    def test_cmake_presets_duplicates_cycles_and_inherited_configure_preset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tpl_dir = root / "assets" / "templates"
            tpl_dir.mkdir(parents=True)
            (tpl_dir / "CMakePresets.json").write_text(
                json.dumps(
                    {
                        "version": 6,
                        "cmakeMinimumRequired": {"major": 3, "minor": 25, "patch": 0},
                        "configurePresets": [
                            {"name": "ok-cfg"},
                            {"name": "dup"},
                            {"name": "dup"},
                            {"name": "cyc-a", "inherits": "cyc-b"},
                            {"name": "cyc-b", "inherits": "cyc-a"},
                        ],
                        "buildPresets": [
                            {"name": "base-build", "hidden": True, "configurePreset": "ok-cfg"},
                            {"name": "child-build", "inherits": "base-build"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            errors: list[str] = []
            vs.check_cmake_presets_template(root, errors)
            joined = "\n".join(errors)
            self.assertIn("duplicate preset name 'dup'", joined)
            self.assertIn("cyclic inherits", joined)
            self.assertNotIn("child-build", joined)

    def test_frontmatter_rejects_empty_quoted_and_overlong_description(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skill_md = root / "SKILL.md"
            skill_md.write_text('---\nname: cpp-fullstack-dev\ndescription: ""\n---\n', encoding="utf-8")
            errs1: list[str] = []
            vs.check_skill_frontmatter(skill_md, errs1)
            self.assertTrue(any("non-empty 'description'" in e for e in errs1))

            skill_md.write_text(
                f'---\nname: cpp-fullstack-dev\ndescription: "{"x" * 1025}"\n---\n',
                encoding="utf-8",
            )
            errs2: list[str] = []
            vs.check_skill_frontmatter(skill_md, errs2)
            self.assertTrue(any("1024-char" in e for e in errs2))


class ExtractThemeTests(unittest.TestCase):
    def test_extract_all_builtin_presets_template_and_rejects_traversal(self) -> None:
        listed = et.list_themes(SKILL_ROOT)
        self.assertEqual(listed["presets"], ["cursor", "linear", "notion", "stripe", "vercel"])

        for preset in listed["presets"]:
            path, theme_id = et.resolve_theme_target(preset, SKILL_ROOT)
            extracted = et.extract_theme_from_file(path, theme_id=theme_id)
            self.assertEqual(extracted["id"], preset)
            self.assertIn("bg.canvas", extracted["semanticTokens"])
            self.assertIn("accent.primary", extracted["semanticTokens"])
            self.assertIn("--bg-canvas", extracted["cssVariables"])

        tpl_path = SKILL_ROOT / "assets" / "templates" / "DESIGN.md"
        tpl_extracted = et.extract_theme_from_file(tpl_path)
        self.assertEqual(tpl_extracted["missingRecommendedTokens"], [])
        self.assertEqual(tpl_extracted["semanticTokens"]["bg.canvas"], "#0f1115")

        with self.assertRaises(FileNotFoundError):
            et.resolve_theme_target("../SKILL.md", SKILL_ROOT)


if __name__ == "__main__":
    unittest.main()
