# 来源与整理范围

原始研究快照提交：`ad1f5d046346c7403ad167eef35e54fdb29d01d6`（完整研究档案保留在私有仓库）。

公开版对应文件：

| 本仓库 | 原研究路径 |
| --- | --- |
| `program_library/synthesis.py` | `experiments/structure_lifecycle_ad_c_v0_1/c_synth.py` |
| `program_library/runtime.py` | 同目录 `c_runtime.py` |
| `program_library/benchmark.py` | 同目录 `c_acquire.py` |
| `program_library/tasks.py` | 同目录 `a_expand.py` 的 `source_task` |
| `program_library/engine.py` | `experiments/cml_retrospective_birth_v0_1/engine.py` |
| `program_library/world.py` | 同目录 `world.py` |
| `program_library/dsl.py`、`canon.py` | `experiments/cml_prose_feasibility_v0_1/src/` 下同名文件 |
| `results/reference/` | Lifecycle C正式修正后的结果目录中的同名文件 |

整理改动：将依赖改为包内相对导入，提取历史题生成器，增加可配置输出目录；冻结清单使用包内文件名，避免依赖原工作区绝对路径；补充演示、机制测试、结果核对工具和CI。
候选生成、拟合、排序、搜索动作顺序、预算、任务随机数及评估规则沿用原实验。

`results/reference/`保留历史结果，不把归档本身当作新的独立复现。
公开版本是否复现了历史结果，以根目录`VALIDATION.md`的实际检查记录为准。

原始计费修复说明见`accounting_repair.md`。该说明中的文件名按原研究目录记述，仅用于记录历史；公开版包含修正后的实现与结果。
