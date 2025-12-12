"""Command-line interface for each pipeline stage."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from coastcast.config import load_settings
from coastcast.data.ingest import ingest as run_ingest
from coastcast.evaluation import generate_evaluation_report
from coastcast.lakehouse import build_lakehouse
from coastcast.logging import configure_logging
from coastcast.modeling import train as run_train

app = typer.Typer(no_args_is_help=True, help="CoastCast Vestland data and modeling pipeline")
ConfigOption = Annotated[Path, typer.Option(exists=True, dir_okay=False)]


def _settings(config: Path):
    configure_logging()
    return load_settings(config)


@app.command()
def ingest(config: ConfigOption = Path("configs/base.yml")) -> None:
    outputs = run_ingest(_settings(config))
    typer.echo(f"Bronze data written: {outputs}")


@app.command()
def build(config: ConfigOption = Path("configs/base.yml")) -> None:
    outputs = build_lakehouse(_settings(config))
    typer.echo(f"Analytical data written: {outputs}")


@app.command()
def train(config: ConfigOption = Path("configs/base.yml")) -> None:
    output = run_train(_settings(config))
    typer.echo(f"Model bundle written: {output}")


@app.command()
def evaluate(config: ConfigOption = Path("configs/base.yml")) -> None:
    output = generate_evaluation_report(_settings(config))
    typer.echo(f"Evaluation written: {output}")


@app.command()
def pipeline(config: ConfigOption = Path("configs/base.yml")) -> None:
    settings = _settings(config)
    run_ingest(settings)
    build_lakehouse(settings)
    run_train(settings)
    output = generate_evaluation_report(settings)
    typer.echo(f"Pipeline complete. Evaluation written: {output}")


if __name__ == "__main__":
    app()
