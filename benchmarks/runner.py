import os
import glob
import time
import json
import psutil
import multiprocessing
from datetime import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

# pydre imports (src/project.py)
from pydre.project import Project


# Helper: Resource Monitor
class ResourceMonitor:
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.cpu_samples = []
        self.peak_memory = 0

    def snapshot(self):
        # CPU usage snapshot
        self.cpu_samples.append(psutil.cpu_percent(interval=None))

        # memory snapshot
        mem = self.process.memory_info().rss / (1024 * 1024)
        if mem > self.peak_memory:
            self.peak_memory = mem

    def get_summary(self):
        avg_cpu = sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0
        return {
            "cpu_avg": round(avg_cpu, 2),
            "peak_memory": round(self.peak_memory, 2)
        }


# pydre worker for multiprocessing mode
def process_single_file(task):
    """
    task = {
        "project_toml": "path/to/file.toml",
        "file": "path/to/file.dat"
    }
    """
    project = Project(task["project_toml"])
    project.filelist = [task["file"]]

    start = time.perf_counter()
    project.processDatafiles(numThreads=1) # inside single process, keep threads=1
    end = time.perf_counter()

    return {
        "file": task["file"],
        "duration": end - start
    }


# Core Benchmark Runner
def run_scenario(project_file, mode, workers, file_subset):
    """
    mode: "sequential", "threading", "multiprocessing"
    workers: number of threads or processes
    file_subset: list of file paths to process
    """
    print(f"\n=== Running {mode} | workers={workers} | files={len(file_subset)} ===")

    monitor = ResourceMonitor()
    start = time.perf_counter()
    results = []

    # Sequential mode
    if mode == "sequential":
        project = Project(project_file)
        project.filelist = file_subset
        for f in file_subset:
            monitor.snapshot()
            project.processDatafiles(numThreads=1)

    # ThreadPool mode (using Project.processDatafiles)
    elif mode == "threading":
        project = Project(project_file)
        project.filelist = file_subset
        # processDatafiles handles internal threadpool
        project.processDatafiles(numThreads=workers)
        monitor.snapshot()

    # Multiprocessing mode
    elif mode == "multiprocessing":
        tasks = [{"project_toml": project_file, "file": f} for f in file_subset]
        with ProcessPoolExecutor(max_workers=workers) as exe:
            futures = [exe.submit(process_single_file, t) for t in tasks]
            for future in futures:
                res = future.result()
                results.append(res)
                monitor.snapshot()

    end = time.perf_counter()
    time_total = end - start

    stats = monitor.get_summary()

    return {
        "timestamp": datetime.now().isoformat(),
        "project_file": project_file,
        "mode": mode,
        "workers": workers,
        "file_count": len(file_subset),
        "total_time": round(time_total, 4),
        "cpu_avg": stats["cpu_avg"],
        "peak_memory": stats["peak_memory"]
    }


# 🎬 MASTER BENCHMARK EXECUTION
if __name__ == "__main__":

    # Workload project files
    PROJECTS = [
        "benchmark/projects/light.toml",
        "benchmark/projects/medium.toml",
        "benchmark/projects/heavy.toml",
        "benchmark/projects/roi_heavy.toml"
    ]

    # Data scaling (5 / 20 / 50)
    all_files = [Path(p) for p in sorted(glob.glob("benchmark/data/*.dat"))]
    files_small = all_files[:5]
    files_medium = all_files[:20]
    files_large = all_files[:50]

    FILESETS = {
        "small": files_small,
        "medium": files_medium,
        "large": files_large
    }

    # Thread / Process configs
    THREAD_COUNTS = [1, 2, 4, 8, 12, 16, 24]
    CPU_CORES = multiprocessing.cpu_count()
    PROCESS_COUNTS = [1, 2, 4, CPU_CORES]

    # Result store
    results = []

    # MAIN LOOPS
    for project_file in PROJECTS:
        for size_name, subset in FILESETS.items():

            # 1) Sequential baseline
            results.append( run_scenario(project_file, "sequential", 1, subset) )

            # 2) Threading
            for w in THREAD_COUNTS:
                results.append( run_scenario(project_file, "threading", w, subset) )

            # 3) Multiprocessing
            for w in PROCESS_COUNTS:
                results.append( run_scenario(project_file, "multiprocessing", w, subset) )


    # Save results
    output_file = f"benchmark/results/benchmark_{int(time.time())}.json"
    os.makedirs("benchmark/results", exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(results, f, indent=4)

    print(f"\n🎉 Benchmark completed! Results saved to {output_file}")
