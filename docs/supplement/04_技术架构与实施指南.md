# **WorkDataHub 系统重构项目技术架构与实施指南**

版本: 1.0  
日期: 2025-11-08  
作者: 高级软件架构师  
目标受众: WorkDataHub 开发团队

## **1\. 执行摘要 (Executive Summary)**

本文档旨在为 WorkDataHub 数据处理系统的重构提供全面的战略指导和技术实施细节。

目前，我们的遗留系统表现出典型的“棕地项目”（Brownfield）症状：架构臃肿、耦合度高、难以测试和扩展。为了降低风险并确保业务连续性，我们明确**反对“大爆炸”（Big Bang）式的重写**。

我们的核心策略是采用**绞杀植物模式（Strangler Fig Pattern）**，通过渐进式重构，在现有系统旁并行构建新的现代化系统，逐步接管业务功能。

**核心架构决策：**

1. **策略：** 采用绞杀植物模式，逐步替换旧功能。  
2. **架构：** 实施分层架构（铜/银/金层），分离数据质量层级。  
3. **设计：** 遵循整洁架构（Clean Architecture），实现核心逻辑与基础设施的解耦。  
4. **质量：** 引入数据契约（Data Contracts），使用 pandera 等工具进行严格的数据验证。

## **2\. 现状分析：遗留系统的常见问题**

在开始重构之前，必须识别当前系统存在的反模式（Anti-Patterns），以避免重蹈覆辙。

### **2.1 常见反模式**

* **巨型脚本 (Monolithic Scripts):** 单个 2000+ 行的 Python 或 SQL 文件处理所有逻辑，无法隔离测试。  
* **I/O 紧耦合:** 业务逻辑（如计算佣金）与数据库读取/文件写入混合在一起，导致无法进行单元测试。  
* **隐式 Schema:** 缺乏明确的字段定义。上游字段名变更（如 user\_id 变为 USER\_ID）会导致静默失败或数据损坏。  
* **缺乏幂等性:** 重复运行任务会导致数据重复或状态损坏。

### **2.2 痛点症状**

* 变更失败率高，修复 Bug 常引发新问题。  
* 调试周期长，难以追踪数据血缘。  
* 新成员上手困难，不敢修改现有代码。

## **3\. 目标架构设计**

我们将从单体架构迁移到模块化、显式的分层架构。

### **3.1 现代数据管道模式**

我们将主要采用 **分层架构（"奖牌"模式）**：

* **铜层 (Bronze/Raw):** 原始数据，保持原样，不可变。用于保留历史记录和重跑数据。  
* **银层 (Silver/Cleansed):** 清洗、验证、去重后的数据。通常为“应用就绪”状态。  
* **金层 (Gold/Business-Ready):** 聚合数据，直接服务于特定业务报表或应用（如“每日销售报表”）。

### **3.2 代码组织结构**

采用整洁架构原则，严格控制依赖方向（依赖必须指向内部）。

/workdatahub  
├── pyproject.toml         \# 项目定义与依赖  
└── src/  
    └── workdatahub/  
        ├── \_\_init\_\_.py  
        ├── core/            \# \<--- 核心业务逻辑  
        │   ├── \_\_init\_\_.py  
        │   ├── transformations.py \# 纯函数，如 calculate\_commission()  
        │   ├── contracts.py       \# 数据契约定义  
        │   └── domain.py          \# 领域对象  
        │  
        ├── infrastructure/    \# \<--- 基础设施层 (I/O)  
        │   ├── \_\_init\_\_.py  
        │   ├── db\_readers.py    \# 具体实现，如 SqlOrderReader  
        │   ├── file\_writers.py  \# 具体实现，如 ParquetUserWriter  
        │   └── api\_clients.py  
        │  
        ├── pipelines/         \# \<--- 编排层  
        │   ├── \_\_init\_\_.py  
        │   ├── process\_sales\_report.py \# 组装各模块  
        │   └── backfill\_users.py  
        │  
        └── main.py              \# 入口点

* **规则:** core 模块不能导入 infrastructure 或 pipelines 中的任何内容。它必须保持纯净和可测试。

## **4\. 重构策略选择**

经过对比分析，我们选择了风险最低、最稳健的路径。

### **4.1 策略对比矩阵**

| 策略 | 风险 | 工作量 | 时间线 | 业务中断 | 适用场景 |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **绞杀植物模式 (Strangler Fig)** | **低** | **高 (持续性)** | **长 (总量) 快 (见效时间)** | **极低** | **系统级迁移：** 逐步替换整个黑盒遗留系统。 |
| **抽象分支 (Branch by Abstraction)** | **中** | **中** | **中** | **低至中** | **组件级重构：** 替换单体内部的特定组件（如计算引擎）。 |
| **大爆炸重写 (Big Bang Rewrite)** | **极高** | **极高** | **极长** | **最大** | **几乎从不推荐**。 |

### **4.2 推荐路径**

1. **主要策略:** 全局采用 **绞杀植物模式**。  
2. **战术辅助:** 对于内部过于纠缠的组件，先使用 **抽象分支** 模式将其隔离，再进行绞杀。

## **5\. 实施指南：绞杀植物模式 (Strangler Fig)**

本节详细说明如何安全地替换遗留脚本（例如 legacy\_sales\_job.py）。

### **步骤 1: 识别“接缝” (Seam)**

找到一个独立的输出目标。

* **目标:** daily\_sales\_report.csv  
* **遗留代码:** legacy\_sales\_job.py

### **步骤 2: 创建“门面” (Façade)**

创建一个新的入口脚本，接管调度器的调用。初期它只是旧代码的透传。

\# new\_entrypoint.py  
import legacy\_sales\_job  
import logging

def generate\_sales\_report\_facade():  
    """  
    门面（第一阶段）：仅作为旧任务的透传代理。  
    """  
    logging.info("Façade: Running legacy sales job...")  
    try:  
        legacy\_sales\_job.run()   
        logging.info("Façade: Legacy job completed.")  
    except Exception as e:  
        logging.error(f"Façade: Legacy job failed: {e}")  
        raise

if \_\_name\_\_ \== "\_\_main\_\_":  
    generate\_sales\_report\_facade()

### **步骤 3: 构建新管道与影子模式 (Shadow Mode)**

在 workdatahub\_v2 中构建新管道，并更新门面以并行运行新旧管道。**关键：新管道必须写入不同的输出路径。**

\# new\_entrypoint.py (更新版)  
import legacy\_sales\_job  
from workdatahub\_v2.pipelines import run\_sales\_report  
import reconciliation\_util  \# 详见下文  
import logging

def generate\_sales\_report\_facade():  
    LEGACY\_PATH \= "reports/daily\_sales\_report.csv"  
    NEW\_PATH \= "reports/daily\_sales\_report\_NEW.csv"

    \# 1\. 运行遗留管道 (真理来源)  
    try:  
        legacy\_sales\_job.run(output\_path=LEGACY\_PATH)  
    except Exception as e:  
        raise \# 旧系统失败则终止

    \# 2\. 运行新管道 (影子模式)  
    try:  
        run\_sales\_report(output\_path=NEW\_PATH)  
          
        \# 3\. 结果对账 (Reconciliation)  
        reconciliation\_util.compare\_outputs(LEGACY\_PATH, NEW\_PATH)  
    except Exception as e:  
        \# 新系统失败不应影响生产环境，仅记录错误  
        logging.error(f"Shadow Mode Failed: {e}")

### **步骤 4: 实施对账 (Reconciliation)**

使用 Pandas 比较两个输出文件是否完全一致。

\# reconciliation\_util.py  
import pandas as pd  
import pandas.testing as pd\_testing  
import logging

def compare\_outputs(path\_old, path\_new):  
    try:  
        df\_old \= pd.read\_csv(path\_old)  
        df\_new \= pd.read\_csv(path\_new)

        \# 严格比对数据形状、列名、类型和数值  
        pd\_testing.assert\_frame\_equal(df\_old, df\_new)  
        logging.info("RECONCILE SUCCESS: Outputs are identical.")  
        return True  
    except AssertionError as e:  
        logging.warning(f"RECONCILE FAILED: Data mismatch. {e}")  
        return False

### **步骤 5: 切换与退役 (Cutover & Decommission)**

当对账连续多日成功后，修改门面，将新管道设为真理来源，并删除旧代码。

## **6\. 质量保障：数据契约 (Data Contracts)**

为了解决“垃圾进，垃圾出”（GIGO）的问题，我们将使用 pandera 库在代码层面强制执行数据契约。

### **6.1 定义契约**

在 core/contracts.py 中定义 Schema。

import pandera as pa  
from pandera.typing import Series

class BronzeOrdersSchema(pa.DataFrameSchema):  
    """原始订单数据的契约"""  
    order\_id: Series\[str\] \= pa.Field(unique=True)  
    order\_date: Series\[pa.DateTime\] \= pa.Field(nullable=False)  
    \# 业务规则：金额必须非负  
    amount: Series\[float\] \= pa.Field(check=pa.Check.ge(0))  
    \# 枚举值检查  
    status: Series\[str\] \= pa.Field(check=pa.Check.isin(\["pending", "shipped"\]))  
      
    class Config:  
        strict \= True \# 禁止未定义的列

### **6.2 应用契约**

在 core/transformations.py 中使用装饰器保护转换逻辑。

from .contracts import BronzeOrdersSchema, SilverUserOrdersSchema

@pa.check\_schema(BronzeOrdersSchema)  
def transform\_orders(raw\_orders\_df):  
    """  
    只有当输入数据完全符合 BronzeSchema 时，此函数才会执行。  
    这保证了核心逻辑不会处理脏数据。  
    """  
    \# ... 业务逻辑 ...  
    return silver\_df  

### 6.3 契约应用位置
* **铜层入口:** 基础设施读取数据后立即校验。
* **核心层边界:** 业务函数通过装饰器校验输入输出。
* **金层出口:** 写入最终报表前进行校验，防止向 BI 推送错误数据。

---

## 7. 技术模式与最佳实践

### 7.1 依赖注入 (Dependency Injection)
解耦业务逻辑与基础设施。
* **Bad:** 类内部直接实例化 `SqlReader`。
* **Good:** 在 `__init__` 中传入 `reader` 接口。这允许在测试时注入 `FakeReader`。

### 7.2 性能优化
* **分块处理 (Chunking):** 避免一次性将大文件读入内存，使用分块读取。
* **向量化操作:** 在 Pandas/Polars 中避免使用 `for` 循环或 `apply(axis=1)`，使用列式向量化操作。
* **文件格式:** 中间层数据（Silver）使用 **Parquet** 格式替代 CSV，以获得类型安全和更高的读写性能。

---

## 8. 迁移路线图 (Migration Roadmap)

1.  **Step 0: 盘点与基线 (Baseline)**
    * 梳理所有现有管道。
    * 为现有遗留管道的输出添加 `pandera` 校验，建立“成功基准”。
2.  **Step 1: 选择切入点**
    * 选择一个高价值、独立的输出（如每日销售报表）。
3.  **Step 2: 搭建新架构**
    * 建立 `src/core`, `src/infrastructure` 目录结构。
4.  **Step 3: 实现切片 (TDD)**
    * 编写新管道代码，确保通过 Step 0 中的数据校验。
5.  **Step 4: 并行运行与对账**
    * 使用影子模式运行，直到差异（Diff）为 0%。
6.  **Step 5: 切换**
    * 将消费者切换到新输出。
7.  **Step 6: 重复**
    * 选择下一个切入点，循环执行。

---