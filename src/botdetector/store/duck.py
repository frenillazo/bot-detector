"""Almacén analítico sobre DuckDB + Parquet.

Se elige DuckDB en lugar de Postgres por tres razones:

1. A esta escala (decenas de millones de interacciones) es más rápido y no
   necesita infraestructura.
2. Los Parquet exportados *son* el artefacto reproducible: un informe se ancla al
   hash del snapshot y cualquier tercero puede reejecutar el análisis sobre los
   mismos datos y obtener el mismo número.
3. Permite consultar directamente ficheros Parquet sin ingerirlos.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator
from itertools import islice
from pathlib import Path

import duckdb

from botdetector.schema import INTERACTION_COLUMNS, INTERACTIONS_DDL, Interaction, to_row

_BATCH = 10_000


def _batched(it: Iterable, n: int) -> Iterator[list]:
    iterator = iter(it)
    while batch := list(islice(iterator, n)):
        yield batch


class Store:
    """Envoltorio fino sobre una base DuckDB de interacciones."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(self.path)
        self.con.execute(INTERACTIONS_DDL)

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self.con.close()

    # ---------------------------------------------------------------- escritura

    def insert(self, interactions: Iterable[Interaction]) -> int:
        """Inserta interacciones por lotes. Devuelve el número de filas escritas."""
        placeholders = ", ".join("?" * len(INTERACTION_COLUMNS))
        sql = f"INSERT INTO interactions VALUES ({placeholders})"  # noqa: S608
        written = 0
        for batch in _batched(interactions, _BATCH):
            self.con.executemany(sql, [to_row(i) for i in batch])
            written += len(batch)
        return written

    # ---------------------------------------------------------------- lectura

    def count(self) -> int:
        return self.con.execute("SELECT count(*) FROM interactions").fetchone()[0]

    def _scope(self, target_author_id: str, actions: tuple[str, ...] | None) -> tuple[str, list]:
        """Cláusula WHERE y parámetros para acotar a una cuenta objetivo."""
        clause = "target_author_id = ?"
        params: list = [target_author_id]
        if actions:
            clause += f" AND action IN ({', '.join('?' * len(actions))})"
            params += list(actions)
        return clause, params

    def actor_counts(
        self, target_author_id: str, *, actions: tuple[str, ...] | None = None
    ) -> dict[str, int]:
        """Interacciones aportadas por cada cuenta a un objetivo.

        La agregación se hace en DuckDB, no en Python: materializar millones de
        filas para contarlas es justo lo que este almacén existe para evitar.
        """
        clause, params = self._scope(target_author_id, actions)
        rows = self.con.execute(
            f"SELECT actor_id, count(*) FROM interactions WHERE {clause} GROUP BY 1",  # noqa: S608
            params,
        ).fetchall()
        return {actor: int(n) for actor, n in rows}

    def latencies(
        self, target_author_id: str, *, actions: tuple[str, ...] | None = None
    ) -> list[float]:
        """Segundos entre publicación e interacción, para las que tienen el dato.

        El cálculo se hace con `epoch()` dentro de SQL a propósito: devolver
        columnas TIMESTAMPTZ a Python obliga a DuckDB a construir objetos con
        zona horaria, lo que arrastra una dependencia de `pytz`. Restando en SQL
        sale un `double` y el problema desaparece.
        """
        clause, params = self._scope(target_author_id, actions)
        rows = self.con.execute(
            f"SELECT epoch(ts - target_ts) FROM interactions "  # noqa: S608
            f"WHERE {clause} AND target_ts IS NOT NULL",
            params,
        ).fetchall()
        return [float(r[0]) for r in rows if r[0] is not None]

    def edges(
        self,
        *,
        target_author_id: str | None = None,
        actions: tuple[str, ...] | None = None,
        min_actor_activity: int = 2,
        min_target_engagement: int = 2,
    ) -> list[tuple[str, str]]:
        """Aristas (actor, objetivo) ya filtradas por actividad mínima.

        Los filtros no son cosméticos: un actor con una sola interacción no puede
        aportar evidencia de sincronía, y un objetivo con una sola interacción no
        genera ninguna arista de coengagement. Descartarlos antes de construir la
        matriz reduce el coste cuadrático de la similitud en uno o dos órdenes de
        magnitud sin perder señal.
        """
        where = ["TRUE"]
        params: list = []
        if target_author_id is not None:
            where.append("target_author_id = ?")
            params.append(target_author_id)
        if actions:
            where.append(f"action IN ({', '.join('?' * len(actions))})")
            params += list(actions)
        clause = " AND ".join(where)

        sql = f"""
        WITH filtered AS (
            SELECT actor_id, target_id FROM interactions WHERE {clause}
        ),
        actor_counts AS (
            SELECT actor_id FROM filtered
            GROUP BY actor_id HAVING count(DISTINCT target_id) >= ?
        ),
        target_counts AS (
            SELECT target_id FROM filtered
            GROUP BY target_id HAVING count(DISTINCT actor_id) >= ?
        )
        SELECT DISTINCT f.actor_id, f.target_id
        FROM filtered f
        JOIN actor_counts  a USING (actor_id)
        JOIN target_counts t USING (target_id)
        """  # noqa: S608 -- `clause` se compone solo de literales y placeholders
        params += [min_actor_activity, min_target_engagement]
        return self.con.execute(sql, params).fetchall()

    # ---------------------------------------------------------------- snapshots

    def export_snapshot(self, out_dir: str | Path) -> tuple[Path, str]:
        """Exporta a Parquet y devuelve (ruta, sha256).

        El hash es lo que se cita en el informe. Sin él, un resultado no es
        verificable por terceros y la herramienta no vale como evidencia.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / "interactions.parquet"
        self.con.execute(
            "COPY (SELECT * FROM interactions ORDER BY ts, actor_id, target_id) "
            "TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [str(target)],
        )
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        (out_dir / "SNAPSHOT_SHA256").write_text(f"{digest}  interactions.parquet\n")
        return target, digest

    def load_snapshot(self, parquet: str | Path) -> int:
        self.con.execute("INSERT INTO interactions SELECT * FROM read_parquet(?)", [str(parquet)])
        return self.count()
