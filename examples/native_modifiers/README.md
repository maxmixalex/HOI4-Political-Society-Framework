# Native modifier integration examples

These optional files demonstrate all three engine entry points against the
vanilla example's British organizations:

| File | Entry point | Behavior |
| --- | --- | --- |
| `common/ideas/psf_author_examples.txt` | National spirit | TUC influence, support, satisfaction drift and authority position |
| `common/dynamic_modifiers/psf_author_examples.txt` | Timed dynamic modifier | Labour satisfaction, economic drift and civil liberties |
| `common/country_leader/psf_author_examples.txt` | Leader/advisor trait | Independent effects on Labour and the TUC |
| `common/scripted_effects/psf_author_examples.txt` | Event/focus/decision hook | Enables or removes the national spirit and thirty-day dynamic modifier |

Compile the vanilla content normally, then copy this folder's `common/` and
`localisation/` trees into `psf_vanilla_example/` in a development build. Call
`psf_example_enable_native_modifiers = yes` in initialized British country
scope. The trait is a definition for your own characters and is not assigned
automatically. Both hooks import pending native popularity before changing the
modifier source and then refresh/export the PSF projection. To remove the
example idea/dynamic modifier, call
`psf_example_disable_native_modifiers = yes` in the same country.

The keys are generated from actual group IDs, the three metrics and every
declared axis. A custom manifest must use its own generated keys from
`psf-registry.json`. These examples do not change anyone's existing focus tree,
decisions or characters. They are excluded from the normal installation and
validated as a separate combined build in CI.

这些可复制示例展示民族精神、动态修正和人物特质如何直接使用 PSF 的原生
modifier 键。一次性数值效果和具名持续来源另见
[`docs/MODIFIERS.md`](../../docs/MODIFIERS.md)。基础值、有效值和每日变化分别计算；
民族精神移除后，其静态加成消失，已经累积的每日变化保留。
