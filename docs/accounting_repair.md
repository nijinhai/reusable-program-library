# C计费修正

第一版C运行完成后、尚未查看成绩表时，检查源代码发现LIBRARY若核验失败，会回退至研究过程已计算的BASE答案，但其BASE运行/核验费用没有进入该部署路径账本。

原运行完整保留在 `results/c_new_computation_engineering_original/`；该版本主脚本快照 `c_acquire_before_cost_repair.py` 与原freeze.json中的主脚本SHA256一致。修正只为实际使用的回退加回BASE搜索及核验费，增加fallback_to_base字段。任务生成、语法、候选选择、所有预算、返回答案策略均未改变。

修正后重新冻结并运行 `results/c_new_computation/`。两次tasks_frozen SHA256应完全相同；最后核对所有返回程序、严格成功和逐题掩码未变。最终报告使用修正后的计费。
