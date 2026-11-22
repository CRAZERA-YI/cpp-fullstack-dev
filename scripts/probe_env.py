#!/usr/bin/env python3
"""Read-only toolchain and runtime probe for cpp-fullstack-dev."""

from __future__ import annotations

import argparse
import json
import locale
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SHIM_MARKERS = (
    "no module named",
    "xcode-select: note: no developer tools",
    "microsoft store",
    "is not recognized as an internal or external command",
    "不是内部或外部命令",
)


def _decode_output(raw: bytes) -> str:
    """Decode subprocess bytes as UTF-8, falling back to OS native encodings."""
    if not raw:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raw_candidates: list[str | None] = [
            locale.getpreferredencoding(False),
            getattr(locale, "getencoding", lambda: None)(),
            "mbcs" if os.name == "nt" else None,
        ]
        candidates: list[str] = []
        seen: set[str] = set()
        for enc in raw_candidates:
            if not enc:
                continue
            norm = enc.lower().replace("_", "-")
            if norm in {"utf-8", "utf8"} or norm in seen:
                continue
            seen.add(norm)
            candidates.append(enc)
        for enc in candidates:
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return raw.decode(candidates[0] if candidates else "utf-8", errors="replace")


def _is_broken_shim(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in SHIM_MARKERS)


def run_version(
    cmd: list[str],
    timeout: float = 5.0,
    *,
    require_zero_exit: bool = True,
    join_lines: bool = False,
    prefer_stderr: bool = False,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run a command safely and extract version text while checking exit status."""
    candidate = Path(cmd[0])
    exe_path = cmd[0] if (candidate.is_absolute() and candidate.is_file()) else shutil.which(cmd[0])
    if not exe_path:
        return {"found": False, "path": None, "version": None}

    actual_cmd = [exe_path, *cmd[1:]]
    is_python_module = len(cmd) >= 3 and cmd[1] == "-m"
    run_env = {**os.environ, **env_overrides} if env_overrides else None

    try:
        proc = subprocess.run(
            actual_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            env=run_env,
        )
        stdout_text = _decode_output(proc.stdout or b"")
        stderr_text = _decode_output(proc.stderr or b"")
        if prefer_stderr:
            combined = f"{stderr_text}\n{stdout_text}".strip()
        else:
            combined = f"{stdout_text}\n{stderr_text}".strip()
        lines = [line.strip() for line in combined.splitlines() if line.strip()]
        version_text = " | ".join(lines[:3]) if join_lines else (lines[0] if lines else None)

        if _is_broken_shim(combined):
            return {"found": False, "path": None, "version": None}

        if proc.returncode != 0:
            if is_python_module:
                return {"found": False, "path": None, "version": None}
            if require_zero_exit:
                return {
                    "found": False,
                    "path": exe_path,
                    "version": None,
                    "returncode": proc.returncode,
                    "error": version_text,
                }

        return {
            "found": True,
            "path": exe_path,
            "version": version_text,
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "found": False,
            "path": exe_path,
            "version": None,
            "error": str(exc),
        }


def _infer_sibling_qt_version(tool_path: str) -> str | None:
    parent = Path(tool_path).resolve().parent
    for name in ("qmake6.exe", "qmake6", "qmake.exe", "qmake"):
        sibling = parent / name
        if sibling.is_file():
            res = run_version([str(sibling), "-v"], join_lines=True)
            if res.get("found") and res.get("version"):
                return str(res["version"])
    return None


def _query_qmake_props(qmake_path: str | None) -> dict[str, str | None]:
    """Query key Qt installation properties via a single `qmake -query` call."""
    empty: dict[str, str | None] = {
        "qmakeInstallPrefix": None,
        "qmakeSpec": None,
        "qmakeQtVersion": None,
    }
    if not qmake_path:
        return empty
    try:
        proc = subprocess.run(
            [qmake_path, "-query"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5.0,
            check=False,
        )
        if proc.returncode != 0:
            return empty
        props: dict[str, str] = {}
        for line in _decode_output(proc.stdout or b"").splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                props[key.strip()] = value.strip()
        return {
            "qmakeInstallPrefix": props.get("QT_INSTALL_PREFIX") or None,
            "qmakeSpec": props.get("QMAKE_SPEC") or None,
            "qmakeQtVersion": props.get("QT_VERSION") or None,
        }
    except (OSError, subprocess.SubprocessError):
        return empty


def probe_qt_deploy_tool(name: str) -> dict[str, Any]:
    """Probe windeployqt(6) or macdeployqt(6) safely without treating Usage text as a version."""
    exe_path = shutil.which(name)
    if not exe_path and name in {"windeployqt", "macdeployqt"}:
        exe_path = shutil.which(f"{name}6")
    if not exe_path:
        return {"found": False, "path": None, "version": None}

    if name == "windeployqt":
        try:
            proc = subprocess.run(
                [exe_path, "--version"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5.0,
                check=False,
            )
            combined = (
                f"{_decode_output(proc.stdout or b'')}\n"
                f"{_decode_output(proc.stderr or b'')}"
            ).strip()
            first_line = next((l.strip() for l in combined.splitlines() if l.strip()), None)
            if (
                proc.returncode == 0
                and first_line
                and not first_line.lower().startswith("usage:")
            ):
                return {"found": True, "path": exe_path, "version": first_line}
        except (OSError, subprocess.SubprocessError):
            pass

        qt_ver = _infer_sibling_qt_version(exe_path)
        version_note = (
            f"{qt_ver} (via sibling qmake)"
            if qt_ver
            else "<installed; --version unsupported (Qt5)>"
        )
        return {"found": True, "path": exe_path, "version": version_note}

    # macdeployqt has no portable -version flag; infer from sibling qmake if present.
    qt_ver = _infer_sibling_qt_version(exe_path)
    return {
        "found": True,
        "path": exe_path,
        "version": f"{qt_ver} (via sibling qmake)" if qt_ver else "<installed>",
    }


def _first_existing_file(*candidates: Path) -> str | None:
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def _version_sort_key(ver: Any) -> tuple[int, ...]:
    if not isinstance(ver, str):
        return ()
    parts: list[int] = []
    for seg in ver.split("."):
        try:
            parts.append(int(seg))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def probe_windows_vs() -> dict[str, Any]:
    """Locate Visual Studio installations via vswhere.exe on Windows."""
    if platform.system() != "Windows":
        return {"supported": False, "installations": []}

    candidates = []
    for env_key in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env_key)
        if base:
            candidates.append(
                Path(base) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
            )

    vswhere = next((p for p in candidates if p.is_file()), None)
    if not vswhere:
        return {"supported": True, "vswhere": None, "installations": []}

    try:
        proc = subprocess.run(
            [
                str(vswhere),
                "-all",
                "-products",
                "*",
                "-format",
                "json",
                "-utf8",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5.0,
            check=False,
        )
        stdout_text = _decode_output(proc.stdout or b"")
        if proc.returncode != 0 or not stdout_text.strip():
            return {"supported": True, "vswhere": str(vswhere), "installations": []}
        raw = json.loads(stdout_text)
        installs = []
        for item in raw:
            install_path = item.get("installationPath")
            if not install_path:
                continue
            root = Path(install_path)
            vsdevcmd = root / "Common7" / "Tools" / "VsDevCmd.bat"
            vcvars64 = root / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
            vcvarsarm64 = root / "VC" / "Auxiliary" / "Build" / "vcvarsarm64.bat"
            vcvarsall = root / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat"
            bundled_ninja = (
                root
                / "Common7"
                / "IDE"
                / "CommonExtensions"
                / "Microsoft"
                / "CMake"
                / "Ninja"
                / "ninja.exe"
            )
            bundled_cmake = (
                root
                / "Common7"
                / "IDE"
                / "CommonExtensions"
                / "Microsoft"
                / "CMake"
                / "CMake"
                / "bin"
                / "cmake.exe"
            )
            vcpkg_dir = root / "VC" / "vcpkg"
            vcpkg_toolchain = vcpkg_dir / "scripts" / "buildsystems" / "vcpkg.cmake"
            bundled_vcpkg = str(vcpkg_dir) if vcpkg_toolchain.is_file() else None
            bundled_clang_format = _first_existing_file(
                root / "VC" / "Tools" / "Llvm" / "x64" / "bin" / "clang-format.exe",
                root / "VC" / "Tools" / "Llvm" / "bin" / "clang-format.exe",
            )
            bundled_clang_tidy = _first_existing_file(
                root / "VC" / "Tools" / "Llvm" / "x64" / "bin" / "clang-tidy.exe",
                root / "VC" / "Tools" / "Llvm" / "bin" / "clang-tidy.exe",
            )
            if not any(
                (
                    vcvars64.is_file(),
                    vcvarsarm64.is_file(),
                    vcvarsall.is_file(),
                    vsdevcmd.is_file(),
                    bundled_cmake.is_file(),
                    bundled_ninja.is_file(),
                    bundled_vcpkg,
                )
            ):
                continue
            installs.append(
                {
                    "displayName": item.get("displayName"),
                    "installationVersion": item.get("installationVersion"),
                    "installationPath": str(root),
                    "vsDevCmd": str(vsdevcmd) if vsdevcmd.is_file() else None,
                    "vcvars64": str(vcvars64) if vcvars64.is_file() else None,
                    "vcvarsArm64": str(vcvarsarm64) if vcvarsarm64.is_file() else None,
                    "bundledNinja": str(bundled_ninja) if bundled_ninja.is_file() else None,
                    "bundledCmake": str(bundled_cmake) if bundled_cmake.is_file() else None,
                    "bundledVcpkg": bundled_vcpkg,
                    "bundledClangFormat": bundled_clang_format,
                    "bundledClangTidy": bundled_clang_tidy,
                }
            )
        installs.sort(
            key=lambda inst: (
                bool(inst.get("vcvars64") or inst.get("vcvarsArm64")),
                _version_sort_key(inst.get("installationVersion")),
            ),
            reverse=True,
        )
        return {"supported": True, "vswhere": str(vswhere), "installations": installs}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return {
            "supported": True,
            "vswhere": str(vswhere),
            "installations": [],
            "error": str(exc),
        }


def probe_vcpkg() -> dict[str, Any]:
    """Detect vcpkg CLI and VCPKG_ROOT toolchain file."""
    vcpkg_root = os.environ.get("VCPKG_ROOT")
    cli = run_version(
        ["vcpkg", "version"],
        timeout=15.0,
        env_overrides={"VCPKG_DISABLE_METRICS": "1"},
    )
    toolchain = None
    root_exists = False
    inferred_root = None

    if vcpkg_root:
        root_path = Path(vcpkg_root)
        root_exists = root_path.is_dir()
        candidate = root_path / "scripts" / "buildsystems" / "vcpkg.cmake"
        if candidate.is_file():
            toolchain = str(candidate)
        if not cli["found"]:
            cli_name = "vcpkg.exe" if os.name == "nt" else "vcpkg"
            root_cli = root_path / cli_name
            if root_cli.is_file():
                cli = run_version(
                    [str(root_cli), "version"],
                    timeout=15.0,
                    env_overrides={"VCPKG_DISABLE_METRICS": "1"},
                )

    if not toolchain and cli["found"] and cli["path"]:
        cli_dir = Path(cli["path"]).resolve().parent
        candidate = cli_dir / "scripts" / "buildsystems" / "vcpkg.cmake"
        if candidate.is_file():
            inferred_root = str(cli_dir)
            toolchain = str(candidate)

    return {
        "vcpkgRoot": vcpkg_root,
        "vcpkgRootExists": root_exists,
        "inferredVcpkgRoot": inferred_root,
        "toolchainFile": toolchain,
        "cli": cli,
    }


def probe_python_tools() -> dict[str, Any]:
    """Probe Python packaging, lint, type-check, and test runners."""
    pytest_info = run_version(["pytest", "--version"])
    if not pytest_info["found"]:
        fallback = run_version([sys.executable, "-m", "pytest", "--version"])
        if fallback["found"]:
            pytest_info = {
                "found": True,
                "path": f"{sys.executable} -m pytest",
                "version": fallback["version"],
            }

    return {
        "pip": run_version([sys.executable, "-m", "pip", "--version"]),
        "pytest": pytest_info,
        "uv": run_version(["uv", "--version"]),
        "ruff": run_version(["ruff", "--version"]),
        "mypy": run_version(["mypy", "--version"]),
    }


def is_wsl() -> bool:
    """Return True when executing inside Windows Subsystem for Linux."""
    if platform.system() != "Linux":
        return False
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        proc_ver = Path("/proc/version").read_text(encoding="utf-8", errors="replace")
        return "microsoft" in proc_ver.lower()
    except OSError:
        return False


def build_hints(report: dict[str, Any]) -> list[str]:
    """Generate actionable hints from probe results."""
    hints: list[str] = []
    sys_name = report["platform"]["system"]
    vs_installs = report["visualStudio"].get("installations", [])

    if sys_name == "Windows":
        cl_found = report["compilers"]["cl"]["found"]
        has_any_compiler = (
            cl_found
            or report["compilers"]["clang-cl"]["found"]
            or report["compilers"]["g++"]["found"]
            or report["compilers"]["clang++"]["found"]
        )
        if not cl_found and vs_installs:
            cpp_install = next(
                (inst for inst in vs_installs if inst.get("vcvars64") or inst.get("vcvarsArm64")),
                None,
            )
            if cpp_install:
                vcvars = cpp_install.get("vcvars64") or cpp_install.get("vcvarsArm64")
                hints.append(
                    "cl.exe is not in PATH. For Ninja+MSVC builds in PowerShell, initialize "
                    f"the MSVC environment first via: {vcvars}"
                )
            else:
                vsdev = next(
                    (inst.get("vsDevCmd") for inst in vs_installs if inst.get("vsDevCmd")),
                    None,
                )
                if vsdev:
                    hints.append(
                        "cl.exe is not in PATH and no vcvars64.bat/vcvarsarm64.bat was found "
                        "(Visual Studio C++ Desktop workload may not be installed); only "
                        f"VsDevCmd.bat was detected at {vsdev}."
                    )
        elif not has_any_compiler and not vs_installs:
            hints.append("No MSVC, clang-cl, clang++, or MinGW g++ compiler detected on PATH.")

        if not report["buildTools"]["cmake"]["found"]:
            bundled_cmake = next(
                (inst.get("bundledCmake") for inst in vs_installs if inst.get("bundledCmake")),
                None,
            )
            if bundled_cmake:
                hints.append(
                    "cmake.exe is not in PATH, but Visual Studio bundles CMake at "
                    f"{bundled_cmake} (automatically added to PATH when running vcvars64.bat/VsDevCmd.bat)."
                )

        if not report["buildTools"]["ninja"]["found"]:
            bundled = next(
                (inst.get("bundledNinja") for inst in vs_installs if inst.get("bundledNinja")),
                None,
            )
            if bundled:
                hints.append(
                    "ninja.exe is not in PATH, but Visual Studio bundles Ninja at "
                    f"{bundled} (automatically added to PATH when running vcvars64.bat/VsDevCmd.bat)."
                )

        quality_tools = report.get("qualityTools", {})
        if not quality_tools.get("clang-format", {}).get("found"):
            bundled_cf = next(
                (inst.get("bundledClangFormat") for inst in vs_installs if inst.get("bundledClangFormat")),
                None,
            )
            if bundled_cf:
                hints.append(
                    "clang-format is not in PATH, but Visual Studio bundles it at "
                    f"{bundled_cf} (not added to PATH automatically by vcvars64.bat/VsDevCmd.bat)."
                )
        if not quality_tools.get("clang-tidy", {}).get("found"):
            bundled_ct = next(
                (inst.get("bundledClangTidy") for inst in vs_installs if inst.get("bundledClangTidy")),
                None,
            )
            if bundled_ct:
                hints.append(
                    "clang-tidy is not in PATH, but Visual Studio bundles it at "
                    f"{bundled_ct} (not added to PATH automatically by vcvars64.bat/VsDevCmd.bat)."
                )

        qmake_spec = (report.get("qtEnv") or {}).get("qmakeSpec") or ""
        if "msvc" in qmake_spec.lower() and report["compilers"]["g++"]["found"] and not cl_found:
            hints.append(
                f"Detected qmake uses an MSVC kit ({qmake_spec}), while MinGW g++ is on PATH and "
                "cl.exe is not; activate MSVC (vcvars64.bat) for Qt builds and do not mix MinGW with MSVC Qt."
            )

    vcpkg = report["packageManagers"]["vcpkg"]
    if not vcpkg["vcpkgRoot"]:
        if vcpkg.get("inferredVcpkgRoot"):
            hints.append(
                "VCPKG_ROOT is not set, but vcpkg CLI was found; set VCPKG_ROOT="
                f"{vcpkg['inferredVcpkgRoot']} if using CMakePresets.json."
            )
        else:
            bundled_vcpkg = next(
                (inst.get("bundledVcpkg") for inst in vs_installs if inst.get("bundledVcpkg")),
                None,
            )
            if bundled_vcpkg:
                hints.append(
                    "VCPKG_ROOT is not set, but Visual Studio bundles vcpkg at "
                    f"{bundled_vcpkg}. Note: vcvars64.bat/VsDevCmd.bat adds vcpkg.exe to PATH "
                    f"but does NOT set VCPKG_ROOT; set VCPKG_ROOT={bundled_vcpkg} explicitly "
                    "when using vcpkg CMake presets."
                )
            else:
                hints.append(
                    "VCPKG_ROOT is not set. Set VCPKG_ROOT if building projects that use vcpkg CMake presets."
                )
    elif not vcpkg["toolchainFile"]:
        hints.append(
            f"VCPKG_ROOT ({vcpkg['vcpkgRoot']}) does not contain scripts/buildsystems/vcpkg.cmake."
        )

    if sys_name == "Linux" and report["platform"]["isWsl"]:
        hints.append(
            "Running inside WSL: use Linux CMake/vcpkg presets rather than Windows presets."
        )

    return hints


def collect_env() -> dict[str, Any]:
    """Collect full environment report."""
    qmake_info = run_version(["qmake", "-v"], join_lines=True)
    qmake6_info = run_version(["qmake6", "-v"], join_lines=True)
    active_qmake = (
        qmake6_info["path"]
        if qmake6_info.get("found")
        else (qmake_info["path"] if qmake_info.get("found") else None)
    )
    qmake_props = _query_qmake_props(active_qmake)

    report: dict[str, Any] = {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "pythonVersion": platform.python_version(),
            "pythonExecutable": sys.executable,
            "isWsl": is_wsl(),
        },
        "compilers": {
            "cl": run_version(["cl"], prefer_stderr=True),
            "clang-cl": run_version(["clang-cl", "--version"]),
            "g++": run_version(["g++", "--version"]),
            "clang++": run_version(["clang++", "--version"]),
        },
        "visualStudio": probe_windows_vs(),
        "buildTools": {
            "cmake": run_version(["cmake", "--version"]),
            "ninja": run_version(["ninja", "--version"]),
            "ctest": run_version(["ctest", "--version"]),
            "qmake": qmake_info,
            "qmake6": qmake6_info,
            "windeployqt": probe_qt_deploy_tool("windeployqt"),
            "macdeployqt": probe_qt_deploy_tool("macdeployqt"),
            "meson": run_version(["meson", "--version"]),
            "pkg-config": run_version(["pkg-config", "--version"]),
            "protoc": run_version(["protoc", "--version"]),
            "ccache": run_version(["ccache", "--version"]),
            "sccache": run_version(["sccache", "--version"]),
            "make": run_version(["make", "--version"]),
            "mingw32-make": run_version(["mingw32-make", "--version"]),
            "nmake": run_version(["nmake", "/?"], prefer_stderr=True),
        },
        "qtEnv": {
            "Qt6_DIR": os.environ.get("Qt6_DIR"),
            "Qt5_DIR": os.environ.get("Qt5_DIR"),
            "CMAKE_PREFIX_PATH": os.environ.get("CMAKE_PREFIX_PATH"),
            **qmake_props,
        },
        "packageManagers": {
            "vcpkg": probe_vcpkg(),
            "conan": run_version(["conan", "--version"]),
        },
        "webTools": {
            "node": run_version(["node", "--version"]),
            "npm": run_version(["npm", "--version"]),
            "pnpm": run_version(["pnpm", "--version"]),
            "yarn": run_version(["yarn", "--version"]),
            "bun": run_version(["bun", "--version"]),
        },
        "pythonTools": probe_python_tools(),
        "qualityTools": {
            "clang-format": run_version(["clang-format", "--version"]),
            "clang-tidy": run_version(["clang-tidy", "--version"]),
        },
        "vcs": {
            "git": run_version(["git", "--version"]),
        },
        "debuggers": {
            "gdb": run_version(["gdb", "--version"]),
            "lldb": run_version(["lldb", "--version"]),
            "cdb": run_version(["cdb", "-version"]),
        },
    }
    if platform.system() == "Linux":
        report["linuxDisplay"] = {
            "DISPLAY": os.environ.get("DISPLAY"),
            "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY"),
            "xvfbRun": run_version(["xvfb-run", "--help"]),
        }
    report["hints"] = build_hints(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only local C++ full-stack toolchain and runtime probe."
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Emit single-line compact JSON instead of indented JSON.",
    )
    args = parser.parse_args()

    report = collect_env()
    print(json.dumps(report, indent=None if args.compact else 2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
