# Challenging the Parallelism Dogma in pydre
### Threading vs Multiprocessing Across Real-World Workloads

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **“Effective parallelism emerges from alignment between workload characteristics and execution strategy.”**

---

## 🚀 Project Overview

This repository presents a systematic benchmark of **parallel execution strategies** within the **[pydre](https://github.com/OSUDSL/pydre) analytics pipeline**.  

It evaluates how **sequential**, **thread-based**, and **process-based** execution models behave under distinct workload characteristics, including I/O-bound processing, CPU-intensive metric aggregation, and ROI-heavy branching scenarios.

Rather than assuming that increased parallelism always improves performance, this project demonstrates that **execution strategy effectiveness depends strongly on workload structure and overhead characteristics**.

---

## 🎯 Benchmark Goals

The benchmark was designed to answer the following questions:

- When does threading outperform multiprocessing in real-world analytics?
- At what point does thread-based execution saturate and stop scaling?
- How do ROI complexity and CPU-bound metrics affect parallel performance?
- Can a **dynamic worker allocation strategy** provide stable performance without manual tuning?

---

## 🧠 Key Findings

- **Threading performs best** for light and medium workloads dominated by I/O and low-overhead computation.
- **Multiprocessing consistently outperforms threading** for heavy and ROI-heavy workloads, where CPU-bound execution and branching dominate.
- Thread-based execution **saturates beyond moderate worker counts**, showing diminishing returns even on multi-core systems.
- A **dynamic worker allocation strategy using ~75% of available logical CPUs** delivers stable, near-optimal performance across workloads without configuration-specific tuning.

These results challenge the assumption that “more parallelism is always better” and instead highlight the importance of **workload-aware execution design**.

### Why 75% of Logical CPUs?

Rather than using all available logical CPUs, this benchmark adopts a dynamic worker allocation strategy that defaults to approximately **75% of available cores**.

This value was derived empirically through worker-scaling experiments across multiple workload profiles. Results showed that execution time typically improved up to a point, after which additional workers led to **diminishing returns or performance degradation** due to:

- increased context switching and scheduler contention,
- memory bandwidth pressure,
- overhead from process coordination and branching-heavy execution paths.

Across systems tested, the optimal region consistently fell within the **70–80% utilization range**, where CPU usage remained high while execution time and run-to-run variance were minimized.

Selecting 75% serves as a practical midpoint that avoids over-subscription while remaining close to peak performance, providing a **stable, workload-agnostic default** without requiring manual tuning.

---

## 🧪 Benchmark Workload Profiles

Four workload profiles were used to systematically stress different components of the pydre pipeline:

| Profile | Focus | Characteristics |
|------|------|------|
| **Light** | I/O-bound | Minimal schema inference, single ROI, lightweight metrics |
| **Medium** | Mixed | Multiple ROIs, moderate schema inference, common driving metrics |
| **Heavy** | CPU-bound | Deep schema inference, many metrics, complex ROI slicing |
| **ROI-heavy** | Branching | ROI slicing dominates execution cost |

Each profile was evaluated across sequential, threading, and multiprocessing execution modes.

---

## ⚙️ Repository Structure

```
pydre-parallelism-benchmark/
├── benchmarks/
│   ├── analyze_benchmark.py          # Aggregates benchmark results
│   ├── runner.py                     # Benchmark execution entry point
│   ├── projects/                     # Workload configuration files (.toml)
│   │   ├── light.toml
│   │   ├── medium.toml
│   │   ├── heavy.toml
│   │   └── roi_heavy.toml
│   ├── analysis_output/              # Generated plots and summary tables
│   └── results/                      # Raw benchmark logs (gitignored by default)
├── docs/
│   └── pydre-parallelism-benchmark-report.pdf
└── README.md
```

---

## 🔗 About pydre

This benchmark is built on **pydre**, a Python-based driving simulation data reduction engine developed by  
**The Ohio State University Driving Simulation Lab**.

pydre handles:

- Schema inference over large time-series datasets
- Flexible ROI slicing (time, space, column-based)
- Metric computation over driving and physiological signals

For installation and full documentation, see:  
👉 [https://github.com/OSU-Driving-Simulation-Lab/pydre](https://github.com/OSUDSL/pydre)

This repository focuses exclusively on **benchmarking execution strategies**, not on reimplementing pydre itself.

---

## 📦 Data Policy

**Note:** Large-scale experimental input data is **not included** in this repository.

Raw driving simulation datasets and derived input files were intentionally excluded to:

- Avoid distributing proprietary or sensitive research data
- Keep the repository lightweight and focused on benchmarking methodology
- Encourage reproducibility using user-generated or domain-specific datasets

To reproduce the experiments:

- Generate your own pydre-compatible input data, or
- Adapt the provided workload configuration files to existing datasets

The benchmark code and analysis pipeline are fully reusable across compatible data sources.

---

## 📄 Technical Report

A complete technical report detailing methodology, benchmark design, results, and analysis is included:

* [📄 Download PDF: Challenging the Parallelism Dogma – Tech Report](https://github.com/its-spark-dev/pydre-parallelism-benchmark/blob/main/report/challrnging-the-parallelism-dogma-tech-report.pdf)

The report covers:

- Workload design rationale
- Execution-time ranking across workloads
- Worker scaling behavior
- CPU utilization patterns
- Practical recommendations for default execution strategies

---

## 🙋 Author

**Sanghyeon Park**

- GitHub: https://github.com/its-spark-dev  
- LinkedIn: https://www.linkedin.com/in/park3283/

---

## 📝 License

This project is released under the **MIT License**.  
See [MIT License](LICENSE) for details.

---

> *“Parallel performance emerges from alignment — not from brute force.”*
