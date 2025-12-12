"""Airflow DAG for the reproducible CoastCast historical pipeline."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from airflow.decorators import dag, task

PROJECT_ROOT = Path(os.getenv("COASTCAST_ROOT", "/opt/coastcast"))
CONFIG = os.getenv("COASTCAST_CONFIG", "configs/base.yml")


def run_command(*arguments: str) -> None:
    subprocess.run(arguments, cwd=PROJECT_ROOT, check=True)


@dag(
    dag_id="coastcast_historical_pipeline",
    start_date=datetime(2025, 1, 1),
    schedule="0 4 * * 1",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["coastal", "forecasting", "vestland"],
)
def coastcast_pipeline():
    @task
    def ingest() -> None:
        run_command("python", "-m", "coastcast.cli", "ingest", "--config", CONFIG)

    @task
    def build() -> None:
        run_command("python", "-m", "coastcast.cli", "build", "--config", CONFIG)
        run_command("dbt", "test", "--project-dir", "transform", "--profiles-dir", "transform")

    @task
    def train() -> None:
        run_command("python", "-m", "coastcast.cli", "train", "--config", CONFIG)

    @task
    def evaluate() -> None:
        run_command("python", "-m", "coastcast.cli", "evaluate", "--config", CONFIG)

    ingest() >> build() >> train() >> evaluate()


coastcast_pipeline()
