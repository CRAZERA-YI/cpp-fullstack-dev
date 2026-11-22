#!/usr/bin/env python3
"""Self-validation script for the cpp-fullstack-dev skill."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import importlib.util
import io
import json
import re
import unittest
from pathlib import Path
from typing import Any


def strip_code_spans(text: str) -> str:
    """Remove fenced code blocks and replace inline code spans with a safe placeholder.

    Replacing inline code with 'CODE' preserves backtick-wrapped link labels such as
    ``[`.clang-format`](path)`` while still ignoring example links inside inline code.
    """
    no_fences = re.sub(
        r"(^|\n)[ \t]*([`~]{3,})[^\n]*\n.*?\n[ \t]*\2[ \t]*(?=\n|$)",
        r"\1",
        text,
        flags=re.DOTALL,
    )
    no_fences = re.sub(r"```.*?```", "", no_fences, flags=re.DOTALL)
    return re.sub(r"`[^`\n]+`", "CODE", no_fences)


def _extract_md_link_targets(text: str) -> list[str]:
    link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    targets: list[str] = []
    for match in link_re.finditer(strip_code_spans(text)):
        raw_target = match.group(1).strip()
        if raw_target.startswith("<") and ">" in raw_target:
            target = raw_target[1 : raw_target.index(">")].strip()
        else:
            target = raw_target.split()[0] if raw_target else ""
        if target:
            targets.append(target)
    return targets


def check_skill_frontmatter(skill_md: Path, errors: list[str]) -> None:
    if not skill_md.is_file():
        errors.append("Missing SKILL.md at skill root.")
        return
    text = skill_md.read_text(encoding="utf-8-sig")
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        errors.append("SKILL.md is missing YAML frontmatter block.")
        return
    fm = match.group(1)
    if not re.search(r"^name:\s*cpp-fullstack-dev\s*$", fm, re.MULTILINE):
        errors.append("SKILL.md frontmatter must declare 'name: cpp-fullstack-dev'.")

    desc_match = re.search(r"^description:\s*(.*)$", fm, re.MULTILINE)
    if not desc_match:
        errors.append("SKILL.md frontmatter must declare a non-empty 'description'.")
        return
    raw_desc = desc_match.group(1).strip()
    if raw_desc in {">", ">-", "|", "|-"}:
        # Collect indented continuation lines of YAML block scalar
        lines = fm[desc_match.end() :].splitlines()
        block_lines: list[str] = []
        for line in lines:
            if line and not line[0].isspace():
                break
            if line.strip():
                block_lines.append(line.strip())
        desc_val = " ".join(block_lines)
    else:
        desc_val = raw_desc.strip('"').strip("'").strip()

    if not desc_val:
        errors.append("SKILL.md frontmatter must declare a non-empty 'description'.")
    elif len(desc_val) > 1024:
        errors.append(
            f"SKILL.md frontmatter 'description' is {len(desc_val)} chars (exceeds 1024-char cross-platform limit)."
        )


def check_version_file(root: Path, errors: list[str]) -> None:
    version_path = root / "VERSION"
    if not version_path.is_file():
        errors.append("Missing VERSION file at skill root.")
        return
    ver = version_path.read_text(encoding="utf-8-sig").strip()
    if not re.match(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$", ver):
        errors.append(f"VERSION must contain a valid SemVer string, got {ver!r}.")


def check_openai_yaml(root: Path, errors: list[str]) -> None:
    yaml_path = root / "agents" / "openai.yaml"
    if not yaml_path.is_file():
        errors.append("Missing agents/openai.yaml.")
        return
    text = yaml_path.read_text(encoding="utf-8-sig")
    if not re.search(r"^\s*interface\s*:\s*$", text, re.MULTILINE):
        errors.append("agents/openai.yaml must declare 'interface:' section.")
    for key in ("display_name", "short_description", "default_prompt"):
        m = re.search(rf"^\s+{key}\s*:\s*(.+)$", text, re.MULTILINE)
        val = m.group(1).strip().strip('"').strip("'") if m else ""
        if not val:
            errors.append(f"agents/openai.yaml must declare non-empty '{key}'.")
        elif key == "default_prompt" and "$cpp-fullstack-dev" not in val:
            errors.append("agents/openai.yaml 'default_prompt' should reference '$cpp-fullstack-dev'.")


def check_markdown_links(root: Path, errors: list[str]) -> int:
    root_resolved = root.resolve()
    refs_dir = root / "references"
    md_files = sorted(
        list(root.glob("SKILL.md"))
        + list(root.glob("README*.md"))
        + (list(refs_dir.rglob("*.md")) if refs_dir.is_dir() else [])
        + (list((root / "assets").rglob("*.md")) if (root / "assets").is_dir() else [])
    )
    checked = 0
    adjacency: dict[Path, set[Path]] = {}
    for md in md_files:
        md_resolved = md.resolve()
        neighbors = adjacency.setdefault(md_resolved, set())
        text = md.read_text(encoding="utf-8-sig")
        for target in _extract_md_link_targets(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            checked += 1
            resolved = (md.parent / path_part).resolve()
            try:
                resolved.relative_to(root_resolved)
            except ValueError:
                rel_md = md.relative_to(root).as_posix()
                errors.append(f"Link escapes skill root in {rel_md}: ({target})")
                continue
            if not resolved.exists():
                rel_md = md.relative_to(root).as_posix()
                errors.append(f"Broken link in {rel_md}: ({target})")
            elif resolved.is_file():
                neighbors.add(resolved)

    if refs_dir.is_dir():
        skill_md = (root / "SKILL.md").resolve()
        reachable: set[Path] = set()
        if skill_md.is_file():
            queue: list[Path] = [skill_md]
            while queue:
                current = queue.pop(0)
                if current in reachable:
                    continue
                reachable.add(current)
                for nxt in adjacency.get(current, ()):
                    if nxt not in reachable:
                        queue.append(nxt)

        presets_dir = (refs_dir / "ui" / "themes" / "presets").resolve()
        custom_dir = (refs_dir / "ui" / "themes" / "custom").resolve()
        for ref_md in sorted(refs_dir.rglob("*.md")):
            resolved_ref = ref_md.resolve()
            if resolved_ref.is_relative_to(presets_dir) or resolved_ref.is_relative_to(custom_dir):
                continue
            if resolved_ref not in reachable:
                rel_ref = ref_md.relative_to(root).as_posix()
                errors.append(
                    f"Orphaned reference document (not reachable from SKILL.md): {rel_ref}"
                )

    return checked


def check_cmake_presets_template(root: Path, errors: list[str]) -> None:
    presets_path = root / "assets" / "templates" / "CMakePresets.json"
    if not presets_path.is_file():
        errors.append("Missing assets/templates/CMakePresets.json.")
        return
    try:
        data = json.loads(presets_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return
    if not isinstance(data, dict):
        errors.append("assets/templates/CMakePresets.json root JSON value must be an object.")
        return

    version = data.get("version")
    min_ver_map = {
        1: (3, 19),
        2: (3, 20),
        3: (3, 21),
        4: (3, 23),
        5: (3, 24),
        6: (3, 25),
        7: (3, 27),
        8: (3, 28),
        9: (3, 30),
        10: (3, 31),
    }
    cm_req = data.get("cmakeMinimumRequired")
    if isinstance(version, int) and version in min_ver_map and isinstance(cm_req, dict):
        major = cm_req.get("major", 0)
        minor = cm_req.get("minor", 0)
        if isinstance(major, int) and isinstance(minor, int):
            req_major, req_minor = min_ver_map[version]
            if (major, minor) < (req_major, req_minor):
                errors.append(
                    f"assets/templates/CMakePresets.json version {version} requires CMake >= "
                    f"{req_major}.{req_minor}, but cmakeMinimumRequired is {major}.{minor}."
                )

    all_sections = (
        "configurePresets",
        "buildPresets",
        "testPresets",
        "packagePresets",
        "workflowPresets",
    )
    section_maps: dict[str, dict[str, dict[str, Any]]] = {}
    for section in all_sections:
        presets_map: dict[str, dict[str, Any]] = {}
        raw_section = data.get(section, [])
        if raw_section is None:
            raw_section = []
        if not isinstance(raw_section, list):
            errors.append(f"assets/templates/CMakePresets.json '{section}' must be an array.")
            section_maps[section] = presets_map
            continue
        for preset in raw_section:
            if isinstance(preset, dict) and isinstance(preset.get("name"), str):
                name = preset["name"]
                if name in presets_map:
                    errors.append(
                        f"assets/templates/CMakePresets.json {section} has duplicate preset name '{name}'."
                    )
                presets_map[name] = preset
        section_maps[section] = presets_map

    def _get_parents(preset: dict[str, Any]) -> list[str]:
        inherits = preset.get("inherits")
        if isinstance(inherits, str):
            return [inherits]
        if isinstance(inherits, list):
            return [p for p in inherits if isinstance(p, str)]
        return []

    for section in ("configurePresets", "buildPresets", "testPresets", "packagePresets"):
        known_names = section_maps[section]
        for preset in data.get(section, []) if isinstance(data.get(section), list) else []:
            if not isinstance(preset, dict) or "inherits" not in preset:
                continue
            inherits = preset["inherits"]
            if isinstance(inherits, str):
                parents: list[Any] = [inherits]
            elif isinstance(inherits, list):
                parents = inherits
            else:
                errors.append(
                    f"assets/templates/CMakePresets.json {section} '{preset.get('name')}' "
                    "has invalid 'inherits' type."
                )
                continue
            for parent in parents:
                if not isinstance(parent, str) or parent not in known_names:
                    errors.append(
                        f"assets/templates/CMakePresets.json {section} '{preset.get('name')}' "
                        f"inherits unknown preset '{parent}'."
                    )

        # Detect cyclic inherits within each section
        visiting: set[str] = set()
        visited: set[str] = set()
        reported_cycles: set[tuple[str, ...]] = set()

        def _dfs_inherits(node: str, trail: list[str]) -> None:
            if node in visited:
                return
            if node in visiting:
                cyc = trail[trail.index(node) :]
                canon = tuple(sorted(set(cyc)))
                if canon not in reported_cycles:
                    reported_cycles.add(canon)
                    errors.append(
                        f"assets/templates/CMakePresets.json {section} has cyclic inherits: "
                        f"{' -> '.join(cyc)}."
                    )
                return
            visiting.add(node)
            for parent in _get_parents(known_names[node]):
                if parent in known_names:
                    _dfs_inherits(parent, trail + [parent])
            visiting.remove(node)
            visited.add(node)

        for name in known_names:
            _dfs_inherits(name, [name])

    def _resolve_configure_preset(
        section: str, name: str, seen: set[str] | None = None
    ) -> str | None:
        if seen is None:
            seen = set()
        if name in seen or name not in section_maps[section]:
            return None
        seen.add(name)
        preset = section_maps[section][name]
        cfg = preset.get("configurePreset")
        if isinstance(cfg, str):
            return cfg
        for parent in _get_parents(preset):
            inherited = _resolve_configure_preset(section, parent, seen)
            if inherited is not None:
                return inherited
        return None

    configure_map = section_maps["configurePresets"]
    for section in ("buildPresets", "testPresets", "packagePresets"):
        raw_items = data.get(section, [])
        if not isinstance(raw_items, list):
            continue
        for preset in raw_items:
            if not isinstance(preset, dict):
                continue
            is_hidden = bool(preset.get("hidden"))
            name = preset.get("name")
            cfg_ref = (
                _resolve_configure_preset(section, name)
                if isinstance(name, str)
                else preset.get("configurePreset")
            )
            if cfg_ref is None:
                if not is_hidden:
                    errors.append(
                        f"assets/templates/CMakePresets.json {section} '{name}' "
                        "is missing 'configurePreset'."
                    )
                continue
            if cfg_ref not in configure_map:
                errors.append(
                    f"assets/templates/CMakePresets.json {section} '{name}' "
                    f"references unknown configurePreset '{cfg_ref}'."
                )
            elif not is_hidden and configure_map[cfg_ref].get("hidden"):
                errors.append(
                    f"assets/templates/CMakePresets.json {section} '{name}' "
                    f"references hidden configurePreset '{cfg_ref}'."
                )

    step_section_map = {
        "configure": "configurePresets",
        "build": "buildPresets",
        "test": "testPresets",
        "package": "packagePresets",
    }
    raw_workflows = data.get("workflowPresets", [])
    if isinstance(raw_workflows, list):
        for wf in raw_workflows:
            if not isinstance(wf, dict):
                continue
            steps = wf.get("steps")
            if not isinstance(steps, list) or not steps:
                errors.append(
                    f"assets/templates/CMakePresets.json workflowPresets '{wf.get('name')}' "
                    "must declare non-empty 'steps'."
                )
                continue
            for step in steps:
                if not isinstance(step, dict):
                    continue
                s_type = step.get("type")
                s_name = step.get("name")
                target_sec = step_section_map.get(s_type)
                if not target_sec or s_name not in section_maps[target_sec]:
                    errors.append(
                        f"assets/templates/CMakePresets.json workflowPresets '{wf.get('name')}' "
                        f"references invalid step ({s_type!r}: {s_name!r})."
                    )


def _load_inspect_project_module(root: Path) -> Any:
    inspect_path = root / "scripts" / "inspect_project.py"
    spec = importlib.util.spec_from_file_location("inspect_project_eval", inspect_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {inspect_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_schema_parity(root: Path, ip_mod: Any, errors: list[str]) -> None:
    schema_path = root / "assets" / "schemas" / "cpp-stack.schema.json"
    if not schema_path.is_file():
        errors.append("Missing assets/schemas/cpp-stack.schema.json.")
        return
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Failed parsing cpp-stack.schema.json for parity check: {exc}")
        return

    try:
        root_props = schema["properties"]
        comp_props = root_props["components"]["additionalProperties"]["properties"]
        ui_props = root_props["ui"]["properties"]
        theme_props = ui_props["theme"]["properties"]
        window_props = ui_props["windows"]["additionalProperties"]["properties"]

        parity_pairs = [
            ("VALID_ARCHITECTURES", set(root_props["architecture"]["enum"]), ip_mod.VALID_ARCHITECTURES),
            ("VALID_STACK_MODES", set(root_props["stackMode"]["enum"]), ip_mod.VALID_STACK_MODES),
            ("VALID_ROLES", set(comp_props["role"]["enum"]), ip_mod.VALID_ROLES),
            ("VALID_PLATFORMS", set(comp_props["platforms"]["items"]["enum"]), ip_mod.VALID_PLATFORMS),
            ("VALID_THEME_MODES", set(theme_props["mode"]["enum"]), ip_mod.VALID_THEME_MODES),
            ("CPP_STACK_ROOT_KEYS", set(root_props.keys()), ip_mod.CPP_STACK_ROOT_KEYS),
            ("CPP_STACK_COMPONENT_KEYS", set(comp_props.keys()), ip_mod.CPP_STACK_COMPONENT_KEYS),
            ("CPP_STACK_UI_KEYS", set(ui_props.keys()), ip_mod.CPP_STACK_UI_KEYS),
            ("CPP_STACK_THEME_KEYS", set(theme_props.keys()), ip_mod.CPP_STACK_THEME_KEYS),
            ("CPP_STACK_WINDOW_KEYS", set(window_props.keys()), ip_mod.CPP_STACK_WINDOW_KEYS),
        ]
    except (KeyError, TypeError) as exc:
        errors.append(f"Unexpected schema structure in cpp-stack.schema.json: {exc}")
        return

    for name, schema_set, code_set in parity_pairs:
        if schema_set != code_set:
            errors.append(
                f"Schema parity mismatch for {name}: schema={sorted(schema_set)} vs inspect_project={sorted(code_set)}"
            )


def check_json_assets(
    root: Path,
    stack_files: list[str],
    errors: list[str],
) -> int:
    json_files = sorted((root / "assets").rglob("*.json"))
    for jf in json_files:
        try:
            json.loads(jf.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Invalid JSON in {jf.relative_to(root).as_posix()}: {exc}")

    check_cmake_presets_template(root, errors)

    template_cfg = root / "assets" / "templates" / "cpp-stack.json"
    if not template_cfg.is_file():
        errors.append("Missing assets/templates/cpp-stack.json.")
    else:
        try:
            data = json.loads(template_cfg.read_text(encoding="utf-8-sig"))
            ip_mod = _load_inspect_project_module(root)
            expected_slugs = {Path(s).stem for s in stack_files}
            if ip_mod.DEFAULT_CATALOG_SLUGS != expected_slugs:
                errors.append(
                    "inspect_project.DEFAULT_CATALOG_SLUGS is out of sync with references/stacks/*.md."
                )
            if ip_mod.KNOWN_CATALOG_SLUGS != expected_slugs:
                errors.append(
                    "inspect_project.KNOWN_CATALOG_SLUGS is out of sync with references/stacks/*.md."
                )
            bad_aliases = {
                k: v
                for k, v in ip_mod.CATALOG_ALIASES.items()
                if v not in ip_mod.KNOWN_CATALOG_SLUGS
            }
            if bad_aliases:
                errors.append(
                    f"inspect_project.CATALOG_ALIASES targets unknown stack slugs: {bad_aliases}"
                )

            check_schema_parity(root, ip_mod, errors)

            res = ip_mod.validate_cpp_stack_data(
                data,
                template_cfg.parent,
                ip_mod.KNOWN_CATALOG_SLUGS,
                skill_root=root,
            )
            if not res.get("valid"):
                for err in res.get("errors", []):
                    errors.append(f"assets/templates/cpp-stack.json: {err}")
        except (OSError, json.JSONDecodeError, RuntimeError) as exc:
            errors.append(f"Failed validating assets/templates/cpp-stack.json: {exc}")
    return len(json_files)


def check_stacks_catalog(root: Path, errors: list[str]) -> list[str]:
    stacks_dir = root / "references" / "stacks"
    catalog = stacks_dir / "catalog.md"
    if not catalog.is_file():
        errors.append("Missing references/stacks/catalog.md.")
        return []
    catalog_text = catalog.read_text(encoding="utf-8-sig")
    linked_targets = {
        (catalog.parent / t.split("#", 1)[0]).resolve()
        for t in _extract_md_link_targets(catalog_text)
        if not t.startswith(("http://", "https://", "#", "mailto:"))
    }
    stack_files = sorted(
        p.name for p in stacks_dir.glob("*.md") if p.name != "catalog.md"
    )
    for name in stack_files:
        if (stacks_dir / name).resolve() not in linked_targets:
            errors.append(f"Stack guide '{name}' is not linked in references/stacks/catalog.md.")
    return stack_files


def check_themes(root: Path, errors: list[str]) -> dict[str, Any]:
    themes_dir = root / "references" / "ui" / "themes"
    index_md = themes_dir / "index.md"
    linked_index_targets: set[Path] = set()
    if not index_md.is_file():
        errors.append("Missing references/ui/themes/index.md.")
    else:
        index_text = index_md.read_text(encoding="utf-8-sig")
        linked_index_targets = {
            (index_md.parent / t.split("#", 1)[0]).resolve()
            for t in _extract_md_link_targets(index_text)
            if not t.startswith(("http://", "https://", "#", "mailto:"))
        }

    presets_dir = themes_dir / "presets"
    presets: list[str] = []
    if not presets_dir.is_dir():
        errors.append("Missing references/ui/themes/presets directory.")
    else:
        for entry in sorted(presets_dir.iterdir()):
            if not entry.is_dir():
                continue
            presets.append(entry.name)
            design_md = entry / "DESIGN.md"
            if not design_md.is_file():
                errors.append(f"Preset '{entry.name}' is missing DESIGN.md.")
            elif design_md.resolve() not in linked_index_targets:
                errors.append(
                    f"Preset '{entry.name}' is not linked in references/ui/themes/index.md."
                )

    custom_dir = themes_dir / "custom"
    custom_themes: list[str] = []
    if custom_dir.is_dir():
        for entry in sorted(custom_dir.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name == "native" or entry.name in presets:
                errors.append(
                    f"Custom theme '{entry.name}' conflicts with built-in theme name."
                )
            if not (entry / "DESIGN.md").is_file():
                errors.append(f"Custom theme '{entry.name}' is missing DESIGN.md.")
            else:
                custom_themes.append(entry.name)

    return {"presets": presets, "custom": custom_themes}


def check_python_scripts(root: Path, errors: list[str]) -> list[str]:
    scripts = sorted((root / "scripts").glob("*.py"))
    tests = sorted((root / "tests").glob("*.py")) if (root / "tests").is_dir() else []
    checked: list[str] = []
    for sp in [*scripts, *tests]:
        rel = sp.relative_to(root).as_posix()
        checked.append(rel)
        try:
            source = sp.read_text(encoding="utf-8")
            compile(source, str(sp), "exec")
        except (OSError, SyntaxError) as exc:
            errors.append(f"Python syntax error in {rel}: {exc}")
    return checked


def run_unit_tests(root: Path, errors: list[str]) -> dict[str, Any] | None:
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        return None
    loader = unittest.TestLoader()
    suite = loader.discover(str(tests_dir), top_level_dir=str(tests_dir))
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=1)
    result = runner.run(suite)
    if not result.wasSuccessful():
        for test_case, tb in result.failures + result.errors:
            first_msg = tb.strip().splitlines()[-1] if tb.strip() else "failed"
            errors.append(f"Unit test failed ({test_case.id()}): {first_msg}")
    return {
        "ran": result.testsRun,
        "passed": result.wasSuccessful(),
    }


def validate_skill(root: Path, run_tests: bool = True) -> tuple[bool, dict[str, Any]]:
    errors: list[str] = []
    check_skill_frontmatter(root / "SKILL.md", errors)
    check_version_file(root, errors)
    check_openai_yaml(root, errors)
    links_checked = check_markdown_links(root, errors)
    stacks = check_stacks_catalog(root, errors)
    json_checked = check_json_assets(root, stacks, errors)
    themes = check_themes(root, errors)
    scripts = check_python_scripts(root, errors)
    unit_tests = run_unit_tests(root, errors) if run_tests else None

    all_files = [
        p
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts
    ]
    total_bytes = sum(p.stat().st_size for p in all_files)

    report = {
        "skillRoot": str(root),
        "valid": len(errors) == 0,
        "errors": errors,
        "stats": {
            "totalFiles": len(all_files),
            "totalKB": round(total_bytes / 1024, 1),
            "markdownLinksChecked": links_checked,
            "jsonAssetsChecked": json_checked,
            "stackGuides": stacks,
            "themePresets": themes["presets"],
            "customThemes": themes["custom"],
            "scripts": scripts,
            "unitTests": unit_tests,
        },
    }
    return len(errors) == 0, report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate cpp-fullstack-dev skill structure, links, schemas, and scripts."
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip executing unittest suite under tests/.",
    )
    args = parser.parse_args()
    skill_root = Path(__file__).resolve().parent.parent
    ok, report = validate_skill(skill_root, run_tests=not args.skip_tests)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
