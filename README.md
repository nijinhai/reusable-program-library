# Reusable Program Library

[![checks](https://github.com/nijinhai/reusable-program-library/actions/workflows/checks.yml/badge.svg)](https://github.com/nijinhai/reusable-program-library/actions/workflows/checks.yml)

**让程序搜索器从示例中学会新函数，并在后续任务中组合复用。**

项目实现了一个完整的程序合成与复用流程：从输入输出示例生成候选程序，验证后存入函数库，再将这些函数与已有操作组合，解决新的字符串处理任务。整个项目使用 Python 标准库，可直接运行。

## 看一个例子

给出两条示例，系统生成反转函数：

```text
abc-Def → feD-cba
XyZ-wvu → uvw-ZyX
```

```python
def solve(text):
    return text[::-1]
```

保存这个函数后，新任务增加了一层前缀：`tag/abc-DeF → FeD-cba`。搜索器找到“反转整个字符串，再取 `/` 前字段”的组合，并在新输入上得到正确结果：

```text
new/mno-PqR → RqP-onm
```

这次演示中，基础搜索用完 8,192 次调用仍未找到精确匹配；加入函数库后，110 次搜索调用找到程序，通过留出输入测试。生成函数另花费 5 次调用。

## 快速运行

需要 Python 3.10+，无需安装第三方包、配置 API Key 或使用 GPU。

```bash
git clone https://github.com/nijinhai/reusable-program-library.git
cd reusable-program-library
python3 -m program_library.demo
```

## 核心实现

```mermaid
flowchart LR
    A[输入输出示例] --> B[生成程序并拟合参数]
    B --> C[检查样例验证]
    C --> D[函数库]
    D --> E[与基础操作组合搜索]
    E --> F[新任务的程序]
```

- **程序合成**：枚举反转、字符替换、字段重排和整数线性变换等表达式，从示例拟合参数，并用检查样例选择程序。
- **函数管理**：将通过验证的表达式编译成 Python 函数，以源码哈希去重，形成可复用的函数库。
- **组合搜索**：将新函数与字段提取、大小写转换、截取等操作放入统一的 FIFO 搜索器，控制总调用预算、函数调用预算和程序长度。
- **实验评估**：对比基础搜索、逐题重新合成和函数库复用；保存逐题程序、测试结果与各环节成本，通过任务及源码哈希检查实验完整性。

## 实验结果

从 **24 道来源任务**中取得通过验证的程序，每个种子去重得到 **7 个函数**。随后固定函数库，在三种子合计 **156 道后续任务**上评估：

| 策略 | 全部样例通过的任务数 |
| --- | ---: |
| 仅使用基础操作搜索 | 0 / 156 |
| 基础搜索失败后，逐题重新合成 | 135 / 156 |
| 使用固定函数库组合搜索 | **108 / 156** |

函数库在直接复用任务中完成 **36/36**，在后处理组合任务中完成 **36/36**。重新合成在参数和格式变化任务中表现更好：完成 36/36，固定库完成 9/36。这组结果展示了保存既有函数与重新拟合程序各自适合的场景。

每题包含 4 条拟合样例、4 条检查样例和 12 条留出查询；表中计数要求三部分全部正确。任务由字符串处理模板生成，覆盖直接复用、外层包装、后处理、参数变化和排序。

完整任务分类、调用成本与分析见[实验说明](docs/experiments.md)，逐题记录见[结果目录](results/reference)。

## 测试与复现

```bash
python3 -m unittest discover -s tests -v
python3 -m program_library.benchmark freeze --output runs/reproduction
python3 -m program_library.benchmark run --output runs/reproduction
python3 -m program_library.verify_results runs/reproduction
```

选择新的输出目录运行，结果保存在 `runs/`。核对工具比较六张结果表，包括全部 **468 条策略/任务记录**。本地干净克隆及 GitHub Actions 的 Python 3.10、3.12 检查均已通过，详见[验证记录](VALIDATION.md)。

## 代码导航

| 文件 | 职责 |
| --- | --- |
| [synthesis.py](program_library/synthesis.py) | 表达式生成、参数拟合、验证和函数对象 |
| [runtime.py](program_library/runtime.py) | 统一执行接口与预算搜索 |
| [benchmark.py](program_library/benchmark.py) | 任务生成、三策略对照和留出评估 |
| [engine.py](program_library/engine.py) / [dsl.py](program_library/dsl.py) | 基础搜索器与字符串操作 |
| [demo.py](program_library/demo.py) | 端到端演示 |
| [tests](tests) | 组合复用、参数拟合、验证拒绝和预算完整性测试 |

项目源于可复用计算结构学习研究。[来源说明](docs/provenance.md)记录了代码整理过程；[实验说明](docs/experiments.md)提供相关研究与后续改进方向。
