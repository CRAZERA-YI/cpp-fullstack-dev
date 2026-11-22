---
name: my-custom-theme
mode: dark
targets: [qt, web]
description: "Brief 1-sentence visual direction and target domain."
---

# Custom Theme Specification

## 1. Color Tokens

| Semantic Role | Hex / RGBA | Usage |
| --- | --- | --- |
| `bg.canvas` | `#0f1115` | Main workspace / app canvas |
| `bg.surface` | `#161a22` | Sidebars, cards, toolbars |
| `bg.elevated` | `#1e2430` | Popovers, menus, dialogs |
| `text.primary` | `#f3f5f8` | Headings and primary content |
| `text.secondary` | `#a4aebc` | Captions, metadata, labels |
| `border.subtle` | `#2a3140` | Hairlines and input borders |
| `accent.primary` | `#4f7cff` | Primary action, active focus ring |
| `accent.hover` | `#6c92ff` | Hover state for primary action |
| `state.success` | `#2ea043` | Success badge / positive status |
| `state.warning` | `#d29922` | Warning notice |
| `state.danger` | `#f85149` | Destructive action / error state |

## 2. Typography & CJK Fallback

- **UI Sans**: `"Inter", "Segoe UI", "PingFang SC", "Microsoft YaHei UI", "Noto Sans CJK SC", sans-serif`
- **Monospace**: `"JetBrains Mono", "Cascadia Mono", "Consolas", "SF Mono", monospace`
- **Scale**: Caption `12px` / Body `13–14px` / Section `16px` / Title `20px`

## 3. Spacing, Radius & Elevation

- **Spacing Grid**: `4px` base (`4 / 8 / 12 / 16 / 24px`)
- **Border Radius**: Controls `6px`, Panels/Cards `8px`, Modals `12px`
- **Elevation**: Prefer crisp `1px` borders over heavy drop shadows in desktop workspaces.

## 4. Component States

- **Focus Ring**: Visible `1px` or `2px` `accent.primary` outline for keyboard navigation.
- **Selection**: Distinguish selected items via both surface tint and border/icon (never color hue alone).
- **Disabled**: Lower foreground contrast clearly while keeping text legible (`>= 3:1` where practical).

## 5. Qt & Web Mapping Notes

- **Qt Widgets**: Map base roles to `QPalette`, scope QSS by top-level `objectName` (e.g., `QWidget#mainRoot`), and style `QLineEdit:focus`, `QListView::item:selected`, `QMenu`.
- **Qt Quick**: Expose tokens via a single QML `Theme` singleton object.
- **Web**: Export tokens as CSS Custom Properties under `:root` / `[data-theme="my-custom-theme"]` and bind Tailwind/component classes to those variables.
