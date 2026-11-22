# Reusable Program Library

**从输入输出示例合成函数，验证后入库，再与已有操作组合解决新任务。**

一个仅依赖 Python 标准库的研究原型，展示符号程序合成、可执行函数库、预算约束搜索，以及严格区分拟合、验证与测试的实验流程。

## 快速体验

需要 Python 3.10+，无需 API Key、GPU 或第三方 Python 包。从仓库根目录运行：

```bash
python3 -m program_library.demo
python3 -m unittest discover -s tests -v
```

演示先从 `abc-Def → feD-cba` 等示例取得反转函数，再冻结函数库。
面对 `tag/abc-DeF → FeD-cba`，搜索器组合“提取字段”和已取得的反转函数，最后在未参与程序选择的输入上测试。当前动作顺序是先反转整个字符串，再提取 `/` 前的字段。
这是确定性的机制演示，不是完整基准结果。输出末尾示例：

```text
Input: new/mno-PqR -> Expected: RqP-onm
Baseline exact fit: False
Library exact fit: True; held-out exact: True
Charged search calls: baseline=8192, library=110
Acquisition calls: 5 (not included in search calls)
```

```mermaid
flowchart LR
    A[来源题的输入输出示例] --> B[枚举表达式并拟合参数]
    B --> C[独立检查样例验证]
    C --> D[去重并冻结函数库]
    D --> E[新任务中与基础操作组合搜索]
    E --> F[程序确定后进行留出测试]
```

## 实际实现了什么

- **符号提案器**：在预设元语法中枚举字符反转、替换、字段重排和整数仿射计算，并支持少量前后处理；参数从示例拟合。
- **函数库**：通过拟合与检查的表达式编译为 Python 函数，以源码哈希去重；部署阶段不增加或修改函数。
- **组合搜索**：FIFO搜索将新函数与字段提取、大小写转换、截取等基础操作组合；按输入行累计操作调用，限制总预算、函数预算与程序长度。
- **评估与审计**：先固定返回程序，再读取留出查询；记录逐题质量、真实调用新函数的情况，以及取得、验证、回退和执行费用。

这是受限符号程序合成，候选由受信任的内置元语法生成。`Learned`会编译表达式，不能作为执行外部任意代码的沙箱。

## 完整实验结果

三种子（801–803），每种子8道来源题、52道后续题。每题4条拟合样例、4条检查样例、12条留出查询。
来源阶段共取得24/24个通过验证的程序，每种子去重后得到7个函数。

| 策略 | 严格解决 / 156 | 增量操作调用 |
| --- | ---: | ---: |
| BASE：仅基础操作搜索 | 0 | 1,164,276 |
| REPROPOSE：基础搜索失败后逐题重新合成 | 135 | 1,183,560 |
| LIBRARY：冻结函数库并组合复用 | **108** | **789,615** |

“严格解决”指一题的拟合、检查和查询全部正确。
总调用包含各策略规定的来源取得、历史回放、后续搜索、验证和回退成本；另有共同旧求解成本288,244次，原表单列。
表达式费用按照语法操作权重计量，**不是CPU等价计算量或运行时间**。

| 后续任务类型 | BASE | REPROPOSE | LIBRARY |
| --- | ---: | ---: | ---: |
| 直接复用 | 0/36 | 36/36 | 36/36 |
| 外层包装 | 0/36 | 36/36 | 27/36 |
| 后处理组合 | 0/36 | 27/36 | 36/36 |
| 参数或格式变化 | 0/36 | 36/36 | 9/36 |
| 元语法外的排序任务 | 0/12 | 0/12 | 0/12 |

**结果支持**：从示例取得的新计算，确实可以在冻结后组合复用；其效果受参数固化、表达空间和搜索调度限制。
**尚未支持**：函数库普遍优于重新生成，或在同质量、同总预算下更经济。REPROPOSE的成功数更高，不能直接把库的较少调用解释成效率胜出；还缺正式的“先提案再搜索”强对照。
三个种子共享设计模板，只改变词汇和任务顺序，不能当作三个独立真实任务分布。

原始逐题记录见 [results/reference](results/reference)，实验条件见[协议](docs/original_protocol.md)。

## 从头复现

使用一个尚不存在的新输出目录，避免覆盖既有结果：

```bash
python3 -m program_library.benchmark freeze --output runs/reproduction
python3 -m program_library.benchmark run --output runs/reproduction
python3 -m program_library.verify_results runs/reproduction
```

冻结步骤记录任务和源码哈希。源码或任务在运行前改变会导致校验失败。结果生成在 `runs/`，不进入版本控制。
核对工具逐项比较6张表，包括全部468条策略/任务记录，而非仅比较总成功数。公开整理版本已完成一次从头运行，六张表全部一致；详见[验证记录](VALIDATION.md)。

## 代码导航

| 文件 | 职责 |
| --- | --- |
| [synthesis.py](program_library/synthesis.py) | 候选表达式生成、参数拟合、验证、函数对象 |
| [runtime.py](program_library/runtime.py) | 基础操作与新函数的统一执行和预算搜索 |
| [benchmark.py](program_library/benchmark.py) | 任务生成、三策略对照、函数冻结和留出评估 |
| [engine.py](program_library/engine.py) / [dsl.py](program_library/dsl.py) | 原始基础搜索器和字符串操作语义 |
| [demo.py](program_library/demo.py) | 最小端到端演示 |
| [tests](tests) | 参数拟合、检查拒绝、组合复用、预算和冻结完整性测试 |

## 研究背景与来源

本项目从一组更广泛的神经算子与计算结构学习实验中提取而来，公开版聚焦可独立运行的符号程序库。
原研究中的“规则复用精确匹配率93.4%”来自另一组Soft-EM实验，**不属于本仓库的指标**。

本仓库是实验原型及证据整理，不声称首次提出程序库学习，也不声称开放式代码发明或通用自主学习。
相关方向包括 [DreamCoder](https://arxiv.org/abs/2006.08381)、[Stitch](https://arxiv.org/abs/2211.16605) 和 [LILO](https://arxiv.org/abs/2310.19791)；本项目没有复现这些系统或报告对它们的性能优势。

源码来源、公开整理改动和结果追踪见[来源说明](docs/provenance.md)。
