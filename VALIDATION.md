# 公开版本验证记录

日期：2026-11-22（Asia/Shanghai）。本机环境：Python 3.12.3，Linux / WSL。

本次实际执行：

- `python3 -m unittest discover -s tests -v`：6项机制测试全部通过。
- `python3 -m program_library.demo`：基础操作未取得精确拟合；冻结库组合精确拟合并通过未见输入测试。搜索调用8192对110，另计取得调用5次；这只是单个演示。
- `python3 -m program_library.benchmark freeze --output runs/reproduction`：重新生成并冻结三种子任务及源码清单。
- `python3 -m program_library.benchmark run --output runs/reproduction`：完成完整三策略实验，墙钟约8.08秒，仅作本机记录，不代表性能承诺。
- `python3 -m program_library.verify_results runs/reproduction`：六张CSV逐项一致，包括468条策略/任务记录、24条来源记录、21条函数出生记录和各项费用。

复现结果：BASE 0/156、REPROPOSE 135/156、LIBRARY 108/156；费用分别为1,164,276、1,183,560、789,615次声明操作调用，与归档一致。

CI配置会在Python 3.10与3.12上运行同一机制测试、演示和完整基准核对。CI实际状态以GitHub Actions为准，不将配置存在当作检查通过。
