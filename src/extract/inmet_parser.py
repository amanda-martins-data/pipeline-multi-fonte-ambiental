"""
inmet_parser.py
----------------
Parser para os arquivos CSV horarios do INMET (Instituto Nacional de
Meteorologia), no formato distribuido em inmet.gov.br/dados.

ATENCAO: este e um parser para dado real e sujo. As particularidades
abaixo foram medidas diretamente nos arquivos de 2023 e 2025, nao sao
suposicoes:

- Encoding e latin-1 (ISO-8859-1), nao UTF-8. Ler como UTF-8 falha no
  primeiro nome de estacao com cedilha (byte 0xC7).
- As 8 primeiras linhas do arquivo sao metadados da estacao (regiao,
  UF, nome, codigo, latitude, longitude, altitude, data de fundacao).
  O cabecalho de colunas de verdade so aparece na linha 9 (indice 8).
- O separador de campo e ';', e o separador decimal e ',' (formato
  brasileiro). "23,4" precisa virar 23.4 antes da conversao numerica.
- Toda linha termina com um ';' sobrando, o que cria uma coluna
  fantasma vazia no fim de cada registro.
- A hora vem no formato "HHMM UTC" (exemplo: "0000 UTC", "1300 UTC").
  Arquivos de anos anteriores usam "HH:MM"; os dois formatos sao
  aceitos.
- Valores faltantes aparecem de duas formas diferentes na mesma
  coluna: string vazia OU o sentinela -9999. As duas precisam virar
  None, nunca um numero.

Este modulo nao decide o que fazer com valores faltantes alem de
identifica-los como None - a decisao de descartar, interpolar ou
manter e da camada de transformacao (fora do escopo deste modulo).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

ENCODING = "latin-1"
HEADER_LINE = 8  # indice zero-based da linha com o cabecalho real de colunas
MISSING_SENTINEL = -9999.0
DATE_FORMATS = ("%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y")


@dataclass(frozen=True)
class StationMetadata:
    """Metadados da estacao, extraidos das 8 linhas iniciais do
    arquivo (antes do cabecalho de colunas).

    Coordenadas ausentes ficam como None, e nao como 0.0: (0, 0) e uma
    coordenada valida no oceano Atlantico, e um zero silencioso seria
    resolvido para o municipio mais proximo sem ninguem perceber."""

    regiao: str
    uf: str
    nome_estacao: str
    codigo_estacao: str
    latitude: float | None
    longitude: float | None
    altitude: float | None
    data_fundacao: str


def parse_decimal(raw: str | None) -> float | None:
    """Converte um campo numerico no formato brasileiro (virgula como
    separador decimal) para float. Trata string vazia e o sentinela
    -9999 como ausencia de dado, retornando None nos dois casos."""
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    value = value.replace(",", ".")
    try:
        parsed = float(value)
    except ValueError:
        return None
    if parsed == MISSING_SENTINEL:
        return None
    return parsed


def parse_hour(raw: str) -> int:
    """Converte o campo de hora do INMET para a hora inteira UTC (0-23).

    Aceita o formato atual 'HHMM UTC' (por exemplo '0000 UTC' ou
    '1300 UTC') e o formato antigo 'HH:MM'. Levanta ValueError para
    qualquer outra coisa, em vez de devolver uma hora inventada."""
    token = raw.strip().split(" ")[0].replace(":", "")
    if len(token) != 4 or not token.isdigit():
        raise ValueError(f"hora em formato inesperado: {raw!r}")
    hour = int(token[:2])
    if not 0 <= hour <= 23:
        raise ValueError(f"hora fora do intervalo 0-23: {raw!r}")
    return hour


def parse_date(raw: str) -> date:
    """Converte o campo de data do INMET para date. O formato atual e
    'AAAA/MM/DD'; 'AAAA-MM-DD' e 'DD/MM/AAAA' aparecem em arquivos de
    outros anos e tambem sao aceitos."""
    value = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"data em formato inesperado: {raw!r}")


def parse_metadata(lines: list[str]) -> StationMetadata:
    """Recebe as primeiras HEADER_LINE linhas do arquivo (ja
    decodificadas) e extrai os metadados da estacao. Cada linha tem o
    formato 'CHAVE:;VALOR' - o valor esta sempre no segundo campo."""

    def field_value(line: str) -> str:
        parts = line.split(";")
        return parts[1].strip() if len(parts) > 1 else ""

    values = [field_value(line) for line in lines]
    # Ordem observada nos arquivos reais do INMET:
    # 0 REGIAO, 1 UF, 2 ESTACAO, 3 CODIGO (WMO),
    # 4 LATITUDE, 5 LONGITUDE, 6 ALTITUDE, 7 DATA DE FUNDACAO
    return StationMetadata(
        regiao=values[0],
        uf=values[1],
        nome_estacao=values[2],
        codigo_estacao=values[3],
        latitude=parse_decimal(values[4]),
        longitude=parse_decimal(values[5]),
        altitude=parse_decimal(values[6]),
        data_fundacao=values[7],
    )


def read_rows(path: str | Path) -> Iterator[dict]:
    """Le um arquivo CSV horario do INMET e devolve um gerador de
    dicionarios, um por linha de medicao, ja com valores tipados
    (date, hora inteira, floats) e faltantes normalizados para None.

    Cada dicionario inclui os metadados da estacao (repetidos em toda
    linha, para que o consumidor nao precise juntar dois arquivos) e
    as colunas de medicao presentes no cabecalho real, ja sem a coluna
    fantasma criada pelo ';' final de cada linha.
    """
    with open(path, encoding=ENCODING, newline="") as fh:
        raw_lines = fh.readlines()

    metadata = parse_metadata(raw_lines[:HEADER_LINE])

    header_line = raw_lines[HEADER_LINE].rstrip("\r\n")
    header_fields = [h.strip() for h in header_line.split(";")]
    if header_fields and header_fields[-1] == "":
        header_fields = header_fields[:-1]  # remove a coluna fantasma

    data_lines = raw_lines[HEADER_LINE + 1 :]
    reader = csv.reader(data_lines, delimiter=";")

    for raw_row in reader:
        if not raw_row or not raw_row[0].strip():
            continue
        if raw_row[-1] == "":
            raw_row = raw_row[:-1]  # remove a coluna fantasma

        row = dict(zip(header_fields, raw_row))

        data_raw = row.get("Data")
        hora_raw = row.get("Hora UTC")

        parsed_row: dict = {
            "codigo_estacao": metadata.codigo_estacao,
            "nome_estacao": metadata.nome_estacao,
            "uf": metadata.uf,
            "latitude": metadata.latitude,
            "longitude": metadata.longitude,
            "altitude": metadata.altitude,
            "data": parse_date(data_raw) if data_raw else None,
            "hora_utc": parse_hour(hora_raw) if hora_raw else None,
        }

        for column, value in row.items():
            if column in ("Data", "Hora UTC"):
                continue
            parsed_row[column] = parse_decimal(value)

        yield parsed_row
