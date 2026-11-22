#!/usr/bin/env python3
"""Read-only compact UI theme token extractor for DESIGN.md and theme.json."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parent.parent

SEMANTIC_KEY_MAP: dict[str, tuple[str, ...]] = {
    "bg.canvas": ("canvas",),
    "bg.surface": ("surface-1", "canvas-soft", "surface", "surface-card"),
    "bg.elevated": ("surface-2", "surface-3", "canvas-soft-2", "surface-soft", "surface-strong"),
    "text.primary": ("ink",),
    "text.secondary": (
        "ink-muted",
        "ink-subtle",
        "ink-secondary",
        "ink-mute",
        "body",
        "charcoal",
        "slate",
        "muted",
        "mute",
    ),
    "border.subtle": ("hairline", "hairline-soft", "hairline-strong"),
    "accent.primary": ("primary", "link"),
    "accent.hover": (
        "primary-hover",
        "primary-active",
        "primary-pressed",
        "primary-press",
        "primary-deep",
        "link-deep",
    ),
    "state.success": ("semantic-success", "success"),
    "state.warning": ("semantic-warning", "warning"),
    "state.danger": ("semantic-error", "error", "danger"),
}

CSS_VAR_MAP: dict[str, str] = {
    "bg.canvas": "--bg-canvas",
    "bg.surface": "--bg-surface",
    "bg.elevated": "--bg-elevated",
    "text.primary": "--text-primary",
    "text.secondary": "--text-secondary",
    "border.subtle": "--border-subtle",
    "accent.primary": "--accent-primary",
    "accent.hover": "--accent-hover",
    "state.success": "--state-success",
    "state.warning": "--state-warning",
    "state.danger": "--state-danger",
}


def list_themes(skill_root: Path = SKILL_ROOT) -> dict[str, list[str]]:
    themes_dir = skill_root / "references" / "ui" / "themes"
    presets_dir = themes_dir / "presets"
    custom_dir = themes_dir / "custom"
    presets = sorted(
        p.name
        for p in presets_dir.iterdir()
        if p.is_dir() and (p / "DESIGN.md").is_file()
    ) if presets_dir.is_dir() else []
    custom = sorted(
        p.name
        for p in custom_dir.iterdir()
        if p.is_dir() and (p / "DESIGN.md").is_file()
    ) if custom_dir.is_dir() else []
    return {"presets": presets, "custom": custom}


def _strip_yaml_scalar(raw: str) -> str:
    val = raw.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in {"'", '"'}:
        return val[1:-1]
    return val


def _parse_frontmatter_sections(text: str) -> dict[str, Any]:
    match = re.match(r"^---\s*\r?\n(.*?)\r?\n---", text, re.DOTALL)
    if not match:
        return {}
    fm = match.group(1)
    meta: dict[str, str] = {}
    colors: dict[str, str] = {}
    rounded: dict[str, str] = {}
    spacing: dict[str, str] = {}
    font_families: dict[str, str] = {}

    current_section: str | None = None
    current_typo_key: str | None = None

    for line in fm.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0:
            current_typo_key = None
            if ":" not in stripped:
                current_section = None
                continue
            key, val = stripped.split(":", 1)
            key = key.strip()
            val = val.strip()
            if not val:
                current_section = key
            else:
                current_section = None
                if key in {"name", "mode", "description"}:
                    meta[key] = _strip_yaml_scalar(val)
            continue

        if current_section in {"colors", "rounded", "spacing"} and indent == 2 and ":" in stripped:
            k, v = stripped.split(":", 1)
            k = k.strip()
            v = _strip_yaml_scalar(v)
            if v:
                if current_section == "colors":
                    colors[k] = v
                elif current_section == "rounded":
                    rounded[k] = v
                elif current_section == "spacing":
                    spacing[k] = v
        elif current_section == "typography":
            if indent == 2 and ":" in stripped:
                k, _ = stripped.split(":", 1)
                current_typo_key = k.strip()
            elif indent >= 4 and current_typo_key and ":" in stripped:
                k, v = stripped.split(":", 1)
                if k.strip() == "fontFamily":
                    fam = _strip_yaml_scalar(v)
                    if fam:
                        font_families[current_typo_key] = fam

    return {
        "meta": meta,
        "colors": colors,
        "rounded": rounded,
        "spacing": spacing,
        "fontFamilies": font_families,
    }


def _parse_markdown_token_table(text: str) -> dict[str, str]:
    """Parse semantic color tokens from template-style Markdown tables."""
    tokens: dict[str, str] = {}
    row_re = re.compile(
        r"^\|\s*`([a-z]+\.[a-z0-9_.-]+)`\s*\|\s*`([^`]+)`\s*\|",
        re.MULTILINE,
    )
    for match in row_re.finditer(text):
        tokens[match.group(1).strip()] = match.group(2).strip()
    return tokens


def extract_theme_from_file(path: Path, theme_id: str | None = None) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")

    if path.suffix.lower() == ".json":
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("theme.json root must be an object.")
        return {
            "id": theme_id or data.get("id") or data.get("name") or path.stem,
            "source": str(path),
            "format": "json",
            "tokens": data,
        }

    fm = _parse_frontmatter_sections(text)
    raw_colors: dict[str, str] = fm.get("colors", {})
    table_tokens = _parse_markdown_token_table(text)

    semantic: dict[str, str] = {}
    for sem_key, candidates in SEMANTIC_KEY_MAP.items():
        if sem_key in table_tokens:
            semantic[sem_key] = table_tokens[sem_key]
            continue
        for cand in candidates:
            if cand in raw_colors:
                semantic[sem_key] = raw_colors[cand]
                break

    # Vercel uses monochrome primary (#171717) with blue link (#0070f3) as chromatic accent
    if (theme_id or "").lower() == "vercel" and "link" in raw_colors:
        semantic["accent.primary"] = raw_colors["link"]
        if "link-deep" in raw_colors:
            semantic["accent.hover"] = raw_colors["link-deep"]

    css_vars = {
        CSS_VAR_MAP[k]: v for k, v in semantic.items() if k in CSS_VAR_MAP
    }

    missing_recommended = [
        req
        for req in (
            "bg.canvas",
            "bg.surface",
            "text.primary",
            "text.secondary",
            "border.subtle",
            "accent.primary",
            "state.danger",
        )
        if req not in semantic
    ]

    result: dict[str, Any] = {
        "id": theme_id or fm.get("meta", {}).get("name") or path.parent.name,
        "source": str(path),
        "format": "design-md",
        "semanticTokens": semantic,
        "cssVariables": css_vars,
        "missingRecommendedTokens": missing_recommended,
        "rounded": fm.get("rounded", {}),
        "spacing": fm.get("spacing", {}),
    }

    font_families = fm.get("fontFamilies", {})
    if font_families:
        unique_fonts: list[str] = []
        for fam in font_families.values():
            if fam not in unique_fonts:
                unique_fonts.append(fam)
        result["fontFamilies"] = unique_fonts
    if fm.get("meta", {}).get("mode"):
        result["mode"] = fm["meta"]["mode"]

    return result


def resolve_theme_target(target: str, skill_root: Path = SKILL_ROOT) -> tuple[Path, str | None]:
    candidate = Path(target)
    if candidate.is_file():
        return candidate.resolve(), None

    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", target) or ".." in target:
        raise FileNotFoundError(
            f"Theme '{target}' not found as a file, skill custom theme, or built-in preset."
        )

    themes_dir = skill_root / "references" / "ui" / "themes"
    custom_path = themes_dir / "custom" / target / "DESIGN.md"
    if custom_path.is_file():
        return custom_path.resolve(), target

    preset_path = themes_dir / "presets" / target / "DESIGN.md"
    if preset_path.is_file():
        return preset_path.resolve(), target

    raise FileNotFoundError(
        f"Theme '{target}' not found as a file, skill custom theme, or built-in preset."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract compact normalized UI tokens from a preset, custom theme, or DESIGN.md/theme.json."
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Theme preset/custom ID (e.g. linear, cursor) or path to DESIGN.md / theme.json.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List built-in presets and skill-level custom themes.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Emit single-line compact JSON.",
    )
    args = parser.parse_args()

    if args.list:
        print(json.dumps(list_themes(), indent=None if args.compact else 2, ensure_ascii=False))
        return 0

    if not args.target:
        parser.error("Provide a theme ID / file path, or pass --list.")

    try:
        path, theme_id = resolve_theme_target(args.target)
        extracted = extract_theme_from_file(path, theme_id=theme_id)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(extracted, indent=None if args.compact else 2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
