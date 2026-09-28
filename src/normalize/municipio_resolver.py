"""
municipio_resolver.py
----------------------
Resolve referencias a municipios brasileiros vindas de fontes
heterogeneas para o codigo IBGE canonico de 7 digitos.

O problema, medido sobre a tabela oficial do IBGE (5.570 municipios
mais o distrito estadual de Fernando de Noronha, ver
data/reference/municipios_ibge.csv):

- 241 nomes normalizados apontam para mais de um municipio, afetando
  521 registros - ou seja, 9,4% dos municipios brasileiros sao
  INALCANCAVEIS apenas pelo nome. "Bom Jesus" existe em 5 estados.
- O proprio dado oficial e inconsistente: 17 nomes usam a contracao
  "D'" com D maiusculo e 29 usam "d'" com d minusculo ("D'Oeste" e
  "d'Oeste", "D'Agua" e "d'Agua"). So com "Oeste", 13 contra 12.
- Remover acentos, que parece a correcao obvia, INTRODUZ 8 colisoes
  novas: "Araçoiaba" e "Aracoiaba" sao municipios diferentes que
  viram a mesma chave, assim como "Iporá" e "Iporã".

Por isso a resolucao e feita em camadas, da mais confiavel para a
menos confiavel, e tudo que nao resolve com seguranca vai para
quarentena em vez de ser descartado ou adivinhado.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class MatchStrategy(str, Enum):
    """Como a resolucao foi obtida - registrada em toda resolucao
    para que a confianca do resultado seja auditavel."""

    IBGE_CODE = "ibge_code"
    IBGE_CODE_6 = "ibge_code_6digits"
    EXACT_NAME_UF = "exact_name_uf"
    NORMALIZED_NAME_UF = "normalized_name_uf"
    NORMALIZED_NAME_UNIQUE = "normalized_name_unique"
    UNRESOLVED_AMBIGUOUS = "unresolved_ambiguous"
    UNRESOLVED_NOT_FOUND = "unresolved_not_found"


# Estrategias que produzem um municipio confiavel.
RESOLVED_STRATEGIES = {
    MatchStrategy.IBGE_CODE,
    MatchStrategy.IBGE_CODE_6,
    MatchStrategy.EXACT_NAME_UF,
    MatchStrategy.NORMALIZED_NAME_UF,
    MatchStrategy.NORMALIZED_NAME_UNIQUE,
}


@dataclass(frozen=True)
class Municipio:
    codigo_ibge: str
    nome: str
    codigo_uf: str
    uf: str = ""


@dataclass
class Resolution:
    """Resultado de uma tentativa de resolucao. Carrega sempre o
    motivo, para que uma resolucao possa ser auditada depois."""

    input_name: str | None
    input_uf: str | None
    input_code: str | None
    municipio: Municipio | None
    strategy: MatchStrategy
    candidates: list[Municipio] = field(default_factory=list)

    @property
    def resolved(self) -> bool:
        return self.strategy in RESOLVED_STRATEGIES

    @property
    def ambiguous(self) -> bool:
        return self.strategy is MatchStrategy.UNRESOLVED_AMBIGUOUS


def normalize_name(name: str) -> str:
    """Normalizacao conservadora para comparacao de nomes.

    Remove acentos, caixa e pontuacao. Isso resolve a maior parte
    das divergencias de grafia entre fontes, mas ATENCAO: a remocao
    de acentos introduz colisoes reais (Araçoiaba/Aracoiaba,
    Iporá/Iporã). Por isso o resultado desta funcao NUNCA e usado
    sozinho quando ha mais de um candidato - ver resolve()."""
    if name is None:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(name))
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    upper = without_accents.upper()
    only_alnum = re.sub(r"[^A-Z0-9 ]", " ", upper)
    return re.sub(r"\s+", " ", only_alnum).strip()


def normalize_ibge_code(code) -> str | None:
    """Normaliza codigo IBGE para 7 digitos.

    Varias fontes publicas brasileiras (DATASUS entre elas) usam o
    codigo de 6 digitos, que e o de 7 sem o digito verificador
    final. Aqui tratamos o de 6 como prefixo a ser reconciliado,
    nao como codigo invalido."""
    if code is None:
        return None
    digits = re.sub(r"\D", "", str(code))
    if not digits:
        return None
    return digits


class MunicipioResolver:
    def __init__(self, municipios: list[Municipio]) -> None:
        self._municipios = municipios

        self._by_code7: dict[str, Municipio] = {}
        self._by_code6: dict[str, list[Municipio]] = {}
        self._by_exact_name_uf: dict[tuple[str, str], Municipio] = {}
        self._by_norm_name_uf: dict[tuple[str, str], list[Municipio]] = {}
        self._by_norm_name: dict[str, list[Municipio]] = {}

        for m in municipios:
            self._by_code7[m.codigo_ibge] = m
            self._by_code6.setdefault(m.codigo_ibge[:6], []).append(m)
            self._by_exact_name_uf[(m.nome, m.codigo_uf)] = m
            norm = normalize_name(m.nome)
            self._by_norm_name_uf.setdefault((norm, m.codigo_uf), []).append(m)
            self._by_norm_name.setdefault(norm, []).append(m)

    @classmethod
    def from_csv(cls, path: str | Path) -> "MunicipioResolver":
        municipios = []
        with open(path, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                municipios.append(
                    Municipio(
                        codigo_ibge=str(row["codigo_ibge"]).strip(),
                        nome=str(row["nome"]).strip(),
                        codigo_uf=str(row["codigo_uf"]).strip(),
                    )
                )
        return cls(municipios)

    def resolve(
        self,
        name: str | None = None,
        uf: str | None = None,
        code: str | None = None,
    ) -> Resolution:
        """Resolve em camadas, da evidencia mais forte para a mais
        fraca. Nunca escolhe arbitrariamente entre candidatos
        igualmente plausiveis - nesse caso devolve ambiguo."""
        norm_code = normalize_ibge_code(code)

        # Camada 1: codigo IBGE de 7 digitos - evidencia mais forte.
        if norm_code and len(norm_code) == 7 and norm_code in self._by_code7:
            return Resolution(name, uf, code, self._by_code7[norm_code], MatchStrategy.IBGE_CODE)

        # Camada 2: codigo de 6 digitos (sem digito verificador).
        if norm_code and len(norm_code) == 6:
            candidates = self._by_code6.get(norm_code, [])
            if len(candidates) == 1:
                return Resolution(name, uf, code, candidates[0], MatchStrategy.IBGE_CODE_6)
            if len(candidates) > 1:
                return Resolution(
                    name, uf, code, None, MatchStrategy.UNRESOLVED_AMBIGUOUS, candidates
                )

        norm_uf = str(uf).strip() if uf is not None else None

        # Camada 3: nome exato + UF.
        if name is not None and norm_uf:
            exact = self._by_exact_name_uf.get((str(name).strip(), norm_uf))
            if exact is not None:
                return Resolution(name, uf, code, exact, MatchStrategy.EXACT_NAME_UF)

        # Camada 4: nome normalizado + UF.
        if name is not None and norm_uf:
            candidates = self._by_norm_name_uf.get((normalize_name(name), norm_uf), [])
            if len(candidates) == 1:
                return Resolution(name, uf, code, candidates[0], MatchStrategy.NORMALIZED_NAME_UF)
            if len(candidates) > 1:
                return Resolution(
                    name, uf, code, None, MatchStrategy.UNRESOLVED_AMBIGUOUS, candidates
                )

        # Camada 5: nome normalizado sem UF - so vale se for unico
        # no pais inteiro. Para 241 nomes isso nao acontece.
        # So roda quando a UF NAO foi informada: se a UF veio e o nome
        # nao existe nela, procurar no pais inteiro contradiz a
        # evidencia. Sem essa guarda, a estacao SAO GONCALO (PB) do
        # INMET era resolvida para Sao Goncalo (RJ).
        if name is not None and not norm_uf:
            candidates = self._by_norm_name.get(normalize_name(name), [])
            if len(candidates) == 1:
                return Resolution(
                    name, uf, code, candidates[0], MatchStrategy.NORMALIZED_NAME_UNIQUE
                )
            if len(candidates) > 1:
                return Resolution(
                    name, uf, code, None, MatchStrategy.UNRESOLVED_AMBIGUOUS, candidates
                )

        return Resolution(name, uf, code, None, MatchStrategy.UNRESOLVED_NOT_FOUND)

    def __len__(self) -> int:
        return len(self._municipios)
