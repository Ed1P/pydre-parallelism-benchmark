# Benchmark Workload Profiles
This document describes the four benchmark workload profiles used in the
`benchmark-multiprocessing` branch.
Each profile is designed to stress different components of the pydre pipeline
— schema inference, ROI slicing, filtering, and metric computation —
so that we can evaluate how threading and multiprocessing behave under distinct conditions.

## 1. Light Workload
(Source: `light.toml`)

The Light workload represents a minimal and I/O-focused configuration.

### Configuration Characteristics
- Schema inference: `infer_schema_length = 1000`
- ROIs: 1 simple time-based ROI
- Metrics: 2 lightweight metrics (Velocity, XPos)

### Intended Purpose
- Designed to simulate a very light computational load
- Emphasizes file I/O and fast ROI lookup
- Ideal for evaluating ThreadPoolExecutor with minimal overhead

### Benchmark Behavior
- Threading shows the fastest completion time
- Multiprocessing overhead is relatively large compared to actual work
- Used as a baseline for light/interactive data flows

## 2. Medium Workload
(Source: `medium.toml`)

The Medium workload provides a balanced, real-world level of complexity.

### Configuration Characteristics
- Schema inference: `infer_schema_length = 2000`
- ROIs: 3 total (general time ROI, specific time ROI, space ROI)
- Metrics: 5 metrics involving basic driving signals
(Velocity, LonAccel, LatAccel, HeadwayTime, LaneOffset)

### Intended Purpose
- Represents a typical pydre research run
- ROI slicing begins to contribute non-trivial cost
- Useful for understanding the transition from I/O-bound to mixed workloads

### Benchmark Behavior
- Threading remains optimal due to moderate computational demands
- Sequential shows larger time penalties
- Multiprocessing provides limited benefit because ROI + metric load is still modest

## 3. Heavy Workload
(Source: `heavy.toml`)

The Heavy workload simulates a full-scale research analysis environment.

### Configuration Characteristics
- Schema inference: `infer_schema_length = 5000`
- ROIs: 4 total
  - two time-based 
  - one space ROI 
  - one column-based ROI (CriticalEventStatus)
- Metrics: 10+ metrics (Velocity, Acceleration, Headway, Steering, Gaze/Eye-related metrics)

### Intended Purpose 
- Generates high ROI slicing cost
- Produces CPU-bound metric aggregation
- Used to test performance limits and scaling behavior of multiprocessing

### Benchmark Behavior
- Multiprocessing clearly outperforms threading
- Threading performance saturates around 8–12 workers
- Workload behaves as a CPU-intensive scenario with heavy ROI branching

## 4. ROI-Heavy Workload
(Source: `roi_heavy.toml`)

The ROI-heavy workload focuses almost entirely on ROI slicing cost.

### Configuration Characteristics
- Schema inference: `infer_schema_length = 3000`
- ROIs: 4 total 
  - general time ROI 
  - specific time ROI 
  - space ROI 
  - column ROI
- Metrics: Only 2 lightweight metrics (Velocity, XPos)

### Intended Purpose
- Isolates and amplifies ROI slicing complexity
- Ideal for evaluating how multiprocessing handles high-branch workloads
- Minimizes metric overhead so ROI cost dominates total run time

### Benchmark Behavior
- Multiprocessing consistently shows the lowest total time 
- Threading is limited by GIL + shared memory synchronization 
- This profile best demonstrates structural benefits of process-level isolation

## Summary
```
Light / Medium workloads → Threading offers the best time performance
Heavy / ROI-heavy workloads → Multiprocessing becomes significantly faster
Sequential → Serves as the baseline and is always the slowest
```

Together, these four profiles provide comprehensive coverage of:
- I/O-bound behavior
- Mixed workloads
- CPU-bound metric computation
- High-complexity ROI slicing

This structure enables systematic parallel performance benchmarking across a wide range of pydre use cases.