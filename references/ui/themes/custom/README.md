# 用户自定义主题存放目录

将可跨项目复用的自定义主题按以下目录结构放置于此：

```text
references/ui/themes/custom/
└── <your-theme-id>/
    └── DESIGN.md
```

- 建议从 [`assets/templates/DESIGN.md`](../../../../assets/templates/DESIGN.md) 复制起点模板。
- 放置后可运行 `python <skill_dir>/scripts/validate_skill.py` 确认主题可被正常发现。
- 详细优先级、项目级 `DESIGN.md` 接入及 Token 约束见 [自定义主题扩展接口](../custom-interface.md)。
