"""

This script reads one or more benchmark JSON files produced by the pydre
benchmark runner and generates summary tables and visualizations.

The goal is to satisfy the following analysis requirements:

1. time vs threads (per workload)
2. time vs processes (per workload)
3. time vs file count
4. CPU usage vs parallel mode


USAGE (from project root or from the "benchmark" directory):

    # From project root:
    uv run python benchmark/analyze_benchmark.py benchmark/results/*.json

    # Or from inside benchmark/:
    uv run python analyze_benchmark.py results/*.json

DEPENDENCIES:
    - polars
    - matplotlib

NOTE:
    - The script assumes that each JSON file contains a list of records.
    - Each record is a dictionary with at least the following keys:
        - "project_file": str   (path or name of the project toml)
        - "mode": str           ("sequential", "threading", "multiprocessing")
        - "workers": int        (number of threads or processes; often 1 for sequential)
        - "file_count": int     (number of files processed in this run)
        - "total_time": float   (wall-clock time in seconds)
        - "cpu_avg": float      (average CPU usage in percent, optional but recommended)
        - "peak_memory": float  (peak memory usage in MB, optional)
    - Extra keys (e.g. throughput, file_avg_time, timestamp) are preserved,
      but not required for the basic plots.
"""

import sys
import json
from pathlib import Path
from typing import List

import polars as pl
import matplotlib.pyplot as plt


# =====================================================================
# Utility helpers
# =====================================================================

def load_json_files(json_paths: List[Path]) -> pl.DataFrame:
    """
    Load multiple JSON benchmark files into a single Polars DataFrame.

    Parameters
    ----------
    json_paths : List[Path]
        List of paths to JSON files. Each JSON file is expected to
        contain a list of benchmark result records (dicts).

    Returns
    -------
    pl.DataFrame
        Combined DataFrame containing all records from all JSON files.
    """
    rows = []

    for path in json_paths:
        # Each file is assumed to be a list of records in JSON format
        with path.open("r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse JSON file: {path}") from e

        if isinstance(data, dict):
            # If for some reason the JSON is a single dict, wrap it
            rows.append(data)
        elif isinstance(data, list):
            rows.extend(data)
        else:
            raise ValueError(
                f"Unexpected JSON structure in file {path}. "
                "Expected list of dicts or a single dict."
            )

    if not rows:
        raise ValueError("No benchmark records found in the provided JSON files.")

    return pl.DataFrame(rows)


def ensure_output_dir(outdir: str = "benchmark/analysis_output") -> Path:
    """
    Ensure that the output directory exists, creating it if necessary.

    Parameters
    ----------
    outdir : str
        Relative or absolute path to the desired output directory.

    Returns
    -------
    Path
        Path object pointing to the output directory.
    """
    out_path = Path(outdir)
    out_path.mkdir(parents=True, exist_ok=True)
    return out_path


def sanitize_name(name: str) -> str:
    """
    Sanitize a string to be safely used as part of a filename.

    This is used to turn project_file paths like:
        "benchmark/projects/heavy.toml"
    into something like:
        "benchmark_projects_heavy.toml"

    Parameters
    ----------
    name : str
        Arbitrary string (typically a path).

    Returns
    -------
    str
        Sanitized string safe for filenames.
    """
    # Replace path separators and spaces with underscores
    sanitized = name.replace("\\", "_").replace("/", "_").replace(" ", "_")
    return sanitized


# =====================================================================
# Plotting helpers
# =====================================================================

def plot_time_vs_workers_per_workload(
    df: pl.DataFrame,
    mode: str,
    outdir: Path
) -> None:
    """
    Plot "total_time vs workers" for each workload (project_file) under
    a specific parallel mode: "threading" or "multiprocessing".

    For each project_file (workload), this will create one figure with:
    - X-axis: workers
    - Y-axis: total_time
    - Separate line for each file_count (small/medium/large)

    Parameters
    ----------
    df : pl.DataFrame
        Benchmark results DataFrame.
    mode : str
        Parallel mode to filter on ("threading" or "multiprocessing").
    outdir : Path
        Directory where the PNG files will be written.
    """
    df_mode = df.filter(pl.col("mode") == mode)

    if df_mode.is_empty():
        # If we have no data for this mode, do nothing.
        print(f"[INFO] No data found for mode={mode}. Skipping time-vs-workers plots.")
        return

    # Get unique project_file entries (each representing a workload)
    project_files = df_mode.select(pl.col("project_file").unique())["project_file"]

    for proj in project_files:
        df_proj = df_mode.filter(pl.col("project_file") == proj)

        # Create a new figure for this workload
        plt.figure(figsize=(8, 5))

        # For each file_count, plot a separate line
        file_counts = df_proj.select(pl.col("file_count").unique())["file_count"]
        for fc in file_counts:
            sub = (
                df_proj
                .filter(pl.col("file_count") == fc)
                .sort("workers")
            )

            # If there are no worker variations, skip (nothing to plot)
            if sub.height == 0:
                continue

            plt.plot(
                sub["workers"],
                sub["total_time"],
                marker="o",
                label=f"{fc} files"
            )

        proj_clean = sanitize_name(str(proj))
        plt.title(f"{mode.capitalize()} — Time vs Workers\nWorkload: {proj}")
        plt.xlabel("Workers")
        plt.ylabel("Total Time (s)")
        plt.grid(True)
        plt.legend(title="File Count")
        plt.tight_layout()

        out_path = outdir / f"time_vs_workers_{mode}_{proj_clean}.png"
        plt.savefig(out_path)
        plt.close()

        print(f"[PLOT] Saved: {out_path}")


def plot_time_vs_filecount(df: pl.DataFrame, outdir: Path) -> None:
    """
    Plot "time vs file_count" to visualize how the pipeline scales as
    the number of files increases.

    There are multiple possible definitions for "time vs file_count".
    In this implementation, we compute the BEST (minimum total_time)
    configuration for each (mode, file_count) pair across all workloads.

    This gives us a "performance envelope" per mode, showing how the
    best achievable performance scales with file_count.

    Parameters
    ----------
    df : pl.DataFrame
        Benchmark results DataFrame.
    outdir : Path
        Directory where the PNG file will be written.
    """
    plt.figure(figsize=(8, 5))

    modes = ["sequential", "threading", "multiprocessing"]

    for mode in modes:
        df_mode = df.filter(pl.col("mode") == mode)
        if df_mode.is_empty():
            continue

        # For each file_count, find the configuration with the minimum total_time
        best_per_filecount = (
            df_mode
            .sort(["file_count", "total_time"])
            .group_by("file_count")
            .first()
            .sort("file_count")
        )

        plt.plot(
            best_per_filecount["file_count"],
            best_per_filecount["total_time"],
            marker="o",
            label=mode
        )

    plt.title("Best Total Time vs File Count\n(per parallel mode)")
    plt.xlabel("File Count")
    plt.ylabel("Best Total Time (s)")
    plt.grid(True)
    plt.legend(title="Parallel Mode")
    plt.tight_layout()

    out_path = outdir / "time_vs_filecount_best_per_mode.png"
    plt.savefig(out_path)
    plt.close()

    print(f"[PLOT] Saved: {out_path}")


def plot_cpu_usage_vs_mode(df: pl.DataFrame, outdir: Path) -> None:
    """
    Plot CPU usage vs parallel mode, to satisfy the requirement:

        "cpu usage vs parallel mode"

    Implementation detail:
    - We group by (project_file, mode) and compute the mean cpu_avg.
    - Then we create one bar plot per workload, comparing modes.

    If cpu_avg is not present in the DataFrame, this function will
    print a message and return without plotting.

    Parameters
    ----------
    df : pl.DataFrame
        Benchmark results DataFrame.
    outdir : Path
        Directory where PNG files will be written.
    """
    if "cpu_avg" not in df.columns:
        print("[INFO] 'cpu_avg' column not found. Skipping CPU usage plots.")
        return

    project_files = df.select(pl.col("project_file").unique())["project_file"]

    for proj in project_files:
        df_proj = df.filter(pl.col("project_file") == proj)

        # Group by mode and compute mean CPU usage
        # We also ignore NaN or None values automatically
        cpu_summary = (
            df_proj
            .group_by("mode")
            .agg(pl.col("cpu_avg").mean().alias("cpu_avg_mean"))
            .sort("mode")
        )

        if cpu_summary.is_empty():
            continue

        modes = cpu_summary["mode"]
        cpu_means = cpu_summary["cpu_avg_mean"]

        plt.figure(figsize=(6, 4))
        plt.bar(modes, cpu_means)
        plt.title(f"Mean CPU Usage vs Parallel Mode\nWorkload: {proj}")
        plt.xlabel("Parallel Mode")
        plt.ylabel("Mean CPU Usage (%)")
        plt.grid(axis="y")

        plt.tight_layout()
        proj_clean = sanitize_name(str(proj))
        out_path = outdir / f"cpu_usage_vs_mode_{proj_clean}.png"
        plt.savefig(out_path)
        plt.close()

        print(f"[PLOT] Saved: {out_path}")


def plot_time_ranking_heatmap(ranking_df: pl.DataFrame, outdir: Path) -> None:
    """
    Create a heatmap where:
        rows = workload (project_file)
        columns = mode (sequential, threading, multiprocessing)
        value = rank (1 = fastest)

    Produces: time_ranking_heatmap.png
    """

    import numpy as np
    import matplotlib.pyplot as plt

    # Pivot the ranking_df into a matrix: workload × mode
    pivot = (
        ranking_df
        .pivot(
            values="rank",
            index="project_file",
            columns="mode"
        )
        .sort("project_file")
    )

    # Convert to numpy matrix for heatmap
    modes = ["sequential", "threading", "multiprocessing"]
    workloads = pivot["project_file"]

    # Extract rank values in correct column order
    matrix = np.array([
        [pivot[row, mode] if pivot[row, mode] is not None else np.nan
         for mode in modes]
        for row in range(len(workloads))
    ], dtype=float)

    plt.figure(figsize=(8, 5))
    cmap = plt.cm.get_cmap("viridis_r")  # reversed so rank1=bright, rank3=dark
    im = plt.imshow(matrix, cmap=cmap)

    plt.colorbar(im, label="Rank (1 = fastest)")

    plt.xticks(ticks=range(len(modes)), labels=modes)
    plt.yticks(ticks=range(len(workloads)), labels=workloads)

    plt.title("Time Ranking Heatmap\n(1 = fastest, 3 = slowest)")
    plt.tight_layout()

    out_path = outdir / "time_ranking_heatmap.png"
    plt.savefig(out_path)
    plt.close()

    print(f"[PLOT] Saved: {out_path}")


# =====================================================================
# Tabular summaries
# =====================================================================

def compute_best_configurations(df: pl.DataFrame, outdir: Path) -> pl.DataFrame:
    """
    Compute the "best" (fastest) configuration per (project_file, mode)
    combination.

    The best configuration is defined as the record with the minimum
    total_time for a given (project_file, mode).

    This answers questions like:
    - "For each workload, which mode/worker combination is fastest?"
    - "What is the optimal numThreads for medium workload?"
    - "How does the best process configuration compare to threads?"

    Parameters
    ----------
    df : pl.DataFrame
        Benchmark results DataFrame.
    outdir : Path
        Directory where the CSV file will be written.

    Returns
    -------
    pl.DataFrame
        DataFrame containing one row per (project_file, mode) with
        the fastest configuration information.
    """
    # Sort by total_time ascending so .first() will pick the fastest
    best_df = (
        df.sort(["project_file", "mode", "total_time"])
          .group_by(["project_file", "mode"])
          .first()
    )

    # Save as CSV for archival and future analysis
    out_csv = outdir / "best_configurations.csv"
    best_df.write_csv(out_csv)
    print(f"[CSV] Saved best configurations table to: {out_csv}")

    return best_df


def print_best_configuration_summary(best_df: pl.DataFrame) -> None:
    """
    Print a human-readable summary of the best configurations.

    This is convenient for quick inspection in the terminal and for
    preparing short executive summaries for your supervisor.

    Parameters
    ----------
    best_df : pl.DataFrame
        DataFrame produced by compute_best_configurations().
    """
    print("\n================ BEST CONFIGURATIONS (per workload & mode) ================")

    # Sort for a stable, readable order
    best_df_sorted = best_df.sort(["project_file", "mode"])

    for row in best_df_sorted.iter_rows(named=True):
        proj = row.get("project_file")
        mode = row.get("mode")
        workers = row.get("workers")
        file_count = row.get("file_count")
        total_time = row.get("total_time")

        print(
            f"Workload: {proj} | Mode: {mode:<14} | "
            f"Workers: {workers:<3} | Files: {file_count:<3} | "
            f"Total Time: {total_time:.3f} s"
        )

    print("======================================================================\n")


def compute_time_ranking_table(df: pl.DataFrame, outdir: Path) -> pl.DataFrame:
    """
    Create a time ranking table across:
        - project_file (workload)
        - mode (sequential / threading / multiprocessing)

    Ranking is based on total_time (ascending).
    The fastest mode gets rank 1.

    Output:
        time_ranking_table.csv
    """

    # Compute the minimum total_time for each mode within each workload
    ranking_raw = (
        df.sort(["project_file", "mode", "total_time"])
          .group_by(["project_file", "mode"])
          .first()
          .select([
              "project_file",
              "mode",
              "workers",
              "file_count",
              "total_time"
          ])
    )

    # Assign ranks (rank=1 is fastest)
    ranking_with_rank = (
        ranking_raw
        .with_columns([
            pl.col("total_time")
            .rank("dense", descending=False)
            .over("project_file")
            .alias("rank")
        ])
        .sort(["project_file", "rank"])
    )

    # Save CSV
    out_csv = outdir / "time_ranking_table.csv"
    ranking_with_rank.write_csv(out_csv)
    print(f"[CSV] Saved time ranking table to: {out_csv}")

    return ranking_with_rank


# =====================================================================
# Main entry point
# =====================================================================

def main() -> None:
    """
    Main entry point for the analysis script.

    Steps:
    1. Parse command-line arguments to get JSON files.
    2. Load all JSON data into a single Polars DataFrame.
    3. Create an output directory for figures and CSVs.
    4. Generate required plots:
        - time vs threads (per workload)
        - time vs processes (per workload)
        - time vs file count (best-per-mode envelope)
        - CPU usage vs parallel mode
    5. Compute and save best configurations table.
    6. Print a concise summary of best configurations.
    """
    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            "    uv run python analyze_benchmark.py <json_files>\n\n"
            "Example:\n"
            "    uv run python analyze_benchmark.py results/*.json"
        )
        sys.exit(1)

    json_paths = [Path(arg) for arg in sys.argv[1:]]

    # Filter out any paths that do not exist to avoid silent failures
    existing_paths = [p for p in json_paths if p.exists()]
    if not existing_paths:
        raise FileNotFoundError("None of the provided JSON paths exist.")

    print("[INFO] Loading JSON benchmark files...")
    df = load_json_files(existing_paths)
    print(f"[INFO] Loaded {df.height} benchmark records.")

    outdir = ensure_output_dir()

    # 1) time vs threads (per workload)
    plot_time_vs_workers_per_workload(df, mode="threading", outdir=outdir)

    # 2) time vs processes (per workload)
    plot_time_vs_workers_per_workload(df, mode="multiprocessing", outdir=outdir)

    # 3) time vs file count (best-per-mode envelope)
    plot_time_vs_filecount(df, outdir=outdir)

    # 4) cpu usage vs parallel mode
    plot_cpu_usage_vs_mode(df, outdir=outdir)

    # Best configurations (per workload & mode)
    best_df = compute_best_configurations(df, outdir=outdir)
    print_best_configuration_summary(best_df)

    ranking_df = compute_time_ranking_table(df, outdir)
    print(ranking_df)

    plot_time_ranking_heatmap(ranking_df, outdir)

    print(f"[DONE] Analysis complete. Outputs written to: {outdir}")


if __name__ == "__main__":
    main()
