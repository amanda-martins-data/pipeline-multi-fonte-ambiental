"""
fetch_reference.py
------------------
Baixa a tabela de referencia de municipios do IBGE (codigo de 7
digitos, nome, UF, coordenadas do centroide) para
data/reference/municipios_ibge.csv.

A tabela nao e versionada no repositorio: sao ~390 KB de dado publico
com fonte estavel, e versionar uma copia cria o risco de a copia
divergir da origem sem ninguem perceber. Os testes que dependem dela
sao pulados se o arquivo nao existir.

Uso:
    python scripts/fetch_reference.py
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

SOURCE_URL = (
    "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/"
    "main/csv/municipios.csv"
)
ROOT = Path(__file__).resolve().parent.parent
DESTINATION = ROOT / "data" / "reference" / "municipios_ibge.csv"
EXPECTED_MIN_ROWS = 5570


def main() -> int:
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    print(f"Baixando {SOURCE_URL}")
    urllib.request.urlretrieve(SOURCE_URL, DESTINATION)

    with open(DESTINATION, encoding="utf-8") as fh:
        rows = sum(1 for _ in fh) - 1  # desconta o cabecalho

    print(f"Salvo em {DESTINATION} ({rows} municipios)")
    if rows < EXPECTED_MIN_ROWS:
        print(
            f"ATENCAO: esperados ao menos {EXPECTED_MIN_ROWS} municipios, "
            f"vieram {rows}. A fonte pode ter mudado.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
