"""Interfaz de línea de comandos."""

from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from botdetector import __version__
from botdetector.collectors.bluesky import BlueskyCollector
from botdetector.pipeline import AnalysisConfig, analyze
from botdetector.store import Store

app = typer.Typer(
    help="Medición de inautenticidad coordinada en audiencias de redes sociales.",
    no_args_is_help=True,
)
console = Console()

DEFAULT_DB = Path("data/interactions.duckdb")

BATCH_SIZE = 2_000
"""Interacciones por escritura. Lotes grandes alargan cada pausa de escritura."""


@app.command()
def version() -> None:
    """Muestra la versión."""
    console.print(f"bot-detector {__version__}")


@app.command()
def collect(
    minutes: float = typer.Option(5.0, help="Duración de la escucha en minutos."),
    limit: int | None = typer.Option(None, help="Máximo de interacciones a recolectar."),
    db: Path = typer.Option(DEFAULT_DB, help="Ruta de la base DuckDB."),
) -> None:
    """Escucha el firehose de Bluesky y almacena las interacciones.

    Gratuito y sin autenticación. Es el banco de pruebas de la herramienta: aquí
    se observa el 100% de los likes y reposts, lo que permite validar el motor
    contra verdad terreno completa.
    """
    collector = BlueskyCollector()
    until = dt.datetime.now(dt.UTC) + dt.timedelta(minutes=minutes)

    console.print(f"[dim]{collector.coverage}[/dim]")
    console.print(f"Escuchando hasta {until:%H:%M:%S} UTC...")

    async def run() -> int:
        written = 0
        with Store(db) as store:
            buffer: list = []

            async def flush() -> int:
                """Escribe el búfer sin bloquear el bucle de eventos.

                `store.insert` es síncrono y tarda cientos de milisegundos. Al
                ejecutarlo en el hilo principal, el socket deja de drenarse y
                Jetstream corta la conexión por consumidor lento: la recolección
                terminaba siempre en un múltiplo exacto del tamaño del búfer,
                justo después de cada escritura.

                Delegarlo a un hilo devuelve el control al bucle mientras dura la
                escritura, de modo que websockets sigue vaciando el socket.
                """
                if not buffer:
                    return 0
                batch, buffer[:] = buffer[:], []
                return await asyncio.to_thread(store.insert, batch)

            async for interaction in collector.stream(until=until, limit=limit):
                buffer.append(interaction)
                if len(buffer) >= BATCH_SIZE:
                    written += await flush()
                    console.print(f"  {written:,} interacciones", end="\r")

            written += await flush()
        return written

    total = asyncio.run(run())
    console.print(f"\n[green]{total:,} interacciones almacenadas en {db}[/green]")
    if collector.reconnects:
        # Una reconexión puede dejar un hueco en la serie temporal, y en un
        # análisis de sincronía un hueco es indistinguible de una pausa real de
        # la campaña. Se avisa siempre.
        console.print(
            f"[yellow]{collector.reconnects} reconexión/es durante la escucha. "
            f"{collector.coverage}[/yellow]"
        )


@app.command()
def report(
    target: str = typer.Argument(..., help="Identificador de la cuenta objetivo."),
    db: Path = typer.Option(DEFAULT_DB, help="Ruta de la base DuckDB."),
    actions: str = typer.Option("repost,quote", help="Acciones a analizar, separadas por coma."),
    min_cluster_size: int = typer.Option(3, help="Suelo absoluto de tamaño de cluster."),
    safety_factor: float = typer.Option(
        10.0, help="Margen exigido sobre la estructura más fuerte que produce el azar."
    ),
    seed: int = typer.Option(0, help="Semilla, para reproducibilidad."),
) -> None:
    """Analiza la audiencia de una cuenta y muestra su perfil.

    ATENCIÓN: el resultado NO es interpretable de forma aislada. Sin cuentas de
    control emparejadas, un valor absoluto de coordinación no significa nada.
    Ver METHODOLOGY.md, sección "Línea base".
    """
    cfg = AnalysisConfig(
        actions=tuple(a.strip() for a in actions.split(",") if a.strip()),
        min_cluster_size=min_cluster_size,
        safety_factor=safety_factor,
        seed=seed,
    )

    with Store(db) as store:
        result = analyze(store, target, cfg)

    p = result.profile
    table = Table(title=f"Perfil de audiencia — {target}", show_header=False)
    table.add_column("Métrica", style="bold")
    table.add_column("Valor")

    table.add_row("Interacciones analizadas", f"{p.n_interactions:,}")
    table.add_row("Cuentas únicas", f"{p.n_unique_actors:,}")
    table.add_row("Cuota de coordinación", str(p.coordination_share))
    table.add_row("Recurrencia (top 1%)", f"{p.recurrence_top1pct:.3f}")
    table.add_row("Gini de audiencia", f"{p.audience_gini:.3f}")
    table.add_row("Clusters coordinados", f"{p.n_clusters}")
    table.add_row("Mayor cluster", f"{p.largest_cluster_size:,} cuentas")
    table.add_row("Umbral de similitud (nulo)", f"{p.similarity_threshold:.4f}")
    if p.median_latency_s is not None:
        table.add_row("Latencia mediana", f"{p.median_latency_s:,.0f} s")
    if p.fast_reaction_share is not None:
        table.add_row("Reacción < 60 s", f"{p.fast_reaction_share:.1%}")

    console.print(table)
    console.print(
        "\n[yellow]Sin cuentas de control emparejadas, estas cifras no son "
        "publicables. Ver METHODOLOGY.md.[/yellow]"
    )


@app.command()
def curve(
    regime: str = typer.Option(
        "uniform",
        help="uniform | actor_subset | target_subset | per_target_cap",
    ),
    seeds: int = typer.Option(10, help="Número de audiencias sintéticas por punto."),
    fidelity: float = typer.Option(0.9, help="Cuánto ruido introduce el operador."),
    out: Path | None = typer.Option(None, help="Fichero markdown de salida."),
) -> None:
    """Curva de degradación: qué se puede afirmar con datos parciales.

    Responde a la única pregunta que importa antes de publicar una cifra: por
    debajo de qué cobertura este detector deja de ver campañas, y a partir de
    qué cobertura lo que dice es fiable.
    """
    from botdetector.validation import sweep, to_markdown
    from botdetector.validation.curves import MINIMUM_COVERAGE

    grids = {
        "uniform": [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.3],
        "actor_subset": [1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2],
        "target_subset": [1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2],
        "per_target_cap": [100, 40, 25, 20, 15, 10, 5],
    }
    if regime not in grids:
        raise typer.BadParameter(f"régimen desconocido: {regime}")

    console.print(f"[dim]Barriendo '{regime}' con {seeds} semillas por punto...[/dim]")
    points = sweep(
        regime=regime,
        parameters=grids[regime],
        seeds=list(range(20, 20 + seeds)),
        fidelity=fidelity,
    )

    md = to_markdown(points, f"Régimen: {regime} (fidelidad {fidelity})")
    console.print(md)
    console.print(
        f"\n[yellow]Suelo de cobertura publicable para este régimen: "
        f"{MINIMUM_COVERAGE[regime]:.0%}[/yellow]"
    )

    if out is not None:
        out.write_text(md + "\n", encoding="utf-8")
        console.print(f"[green]Escrito en {out}[/green]")


@app.command()
def snapshot(
    db: Path = typer.Option(DEFAULT_DB, help="Ruta de la base DuckDB."),
    out: Path = typer.Option(Path("snapshots"), help="Directorio de salida."),
) -> None:
    """Exporta un snapshot Parquet con su hash SHA-256.

    El hash es lo que se cita en el informe: sin él, un resultado no es
    verificable por terceros.
    """
    with Store(db) as store:
        path, digest = store.export_snapshot(out)
    console.print(f"[green]{path}[/green]\nsha256: {digest}")


if __name__ == "__main__":
    app()
