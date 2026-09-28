"""
Testes do resolver de municipios contra a tabela real do IBGE.

Os testes rodam sobre data/reference/municipios_ibge.csv, que nao e
versionado (ver scripts/fetch_reference.py). Sem o arquivo, o modulo
inteiro e pulado em vez de falhar.

Os numeros verificados aqui sao os achados documentados no README e em
docs/03-resolucao-de-entidades.md: se a fonte mudar, estes testes
quebram e avisam que a documentacao precisa ser revista.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from pathlib import Path

import pytest

from src.normalize.municipio_resolver import (
    MatchStrategy,
    MunicipioResolver,
    normalize_ibge_code,
    normalize_name,
)

ROOT = Path(__file__).resolve().parent.parent
REFERENCE_CSV = ROOT / "data" / "reference" / "municipios_ibge.csv"

pytestmark = pytest.mark.skipif(
    not REFERENCE_CSV.exists(),
    reason="tabela de referencia ausente; rode python scripts/fetch_reference.py",
)

# Codigos de UF do IBGE usados nos testes.
UF_SP, UF_PE, UF_CE, UF_PR, UF_GO, UF_PI = "35", "26", "23", "41", "52", "22"


@pytest.fixture(scope="module")
def resolver() -> MunicipioResolver:
    return MunicipioResolver.from_csv(REFERENCE_CSV)


@pytest.fixture(scope="module")
def nomes(resolver: MunicipioResolver) -> list[str]:
    return [m.nome for m in resolver._municipios]


# --- Carga da referencia ----------------------------------------------------


def test_tabela_de_referencia_completa(resolver):
    # 5.570 municipios mais o distrito estadual de Fernando de Noronha,
    # que a fonte inclui com codigo proprio.
    assert len(resolver) == 5571


# --- Camadas de resolucao ---------------------------------------------------


def test_camada_1_codigo_7_digitos(resolver):
    r = resolver.resolve(code="3550308")
    assert r.strategy is MatchStrategy.IBGE_CODE
    assert r.municipio.nome == "São Paulo"


def test_codigo_vence_nome_divergente(resolver):
    # O codigo e a evidencia mais forte: um nome errado junto com um
    # codigo valido nao pode desviar a resolucao.
    r = resolver.resolve(name="Rio de Janeiro", uf=UF_SP, code="3550308")
    assert r.strategy is MatchStrategy.IBGE_CODE
    assert r.municipio.codigo_ibge == "3550308"


def test_camada_2_codigo_6_digitos(resolver):
    # Formato usado pelo DATASUS: o codigo de 7 sem o digito verificador.
    r = resolver.resolve(code="355030")
    assert r.strategy is MatchStrategy.IBGE_CODE_6
    assert r.municipio.codigo_ibge == "3550308"


def test_normalizacao_de_entradas():
    assert normalize_ibge_code("35.503-08") == "3550308"
    assert normalize_ibge_code(3550308) == "3550308"
    assert normalize_ibge_code("") is None
    assert normalize_ibge_code(None) is None
    assert normalize_name("  São   João d'Aliança ") == "SAO JOAO D ALIANCA"
    assert normalize_name("Mogi-Mirim (SP)") == "MOGI MIRIM SP"
    assert normalize_name(None) == ""


def test_camada_3_nome_exato_com_uf(resolver):
    r = resolver.resolve(name="Bom Jesus", uf=UF_PI)
    assert r.strategy is MatchStrategy.EXACT_NAME_UF
    assert r.municipio.codigo_ibge == "2201903"


def test_camada_4_nome_normalizado_com_uf(resolver):
    r = resolver.resolve(name="SAO PAULO", uf=UF_SP)
    assert r.strategy is MatchStrategy.NORMALIZED_NAME_UF
    assert r.municipio.codigo_ibge == "3550308"


def test_camada_5_nome_unico_no_pais(resolver):
    r = resolver.resolve(name="abadia de goias")
    assert r.strategy is MatchStrategy.NORMALIZED_NAME_UNIQUE
    assert r.municipio.codigo_ibge == "5200050"


def test_nome_inexistente_nao_e_inventado(resolver):
    r = resolver.resolve(name="Cidade Que Nao Existe", uf=UF_SP)
    assert r.strategy is MatchStrategy.UNRESOLVED_NOT_FOUND
    assert r.municipio is None
    assert not r.resolved


# --- Achado 1: nome nao e chave ---------------------------------------------


def test_nomes_ambiguos_no_pais(nomes):
    contagem = Counter(normalize_name(n) for n in nomes)
    ambiguos = {k: v for k, v in contagem.items() if v > 1}
    assert len(ambiguos) == 241
    assert sum(ambiguos.values()) == 521
    assert round(521 / len(nomes) * 100, 1) == 9.4


def test_bom_jesus_sem_uf_e_ambiguo(resolver):
    r = resolver.resolve(name="Bom Jesus")
    assert r.ambiguous
    assert r.municipio is None
    assert len(r.candidates) == 5
    assert len({m.codigo_uf for m in r.candidates}) == 5


def test_nome_mais_uf_resolve_todos(resolver):
    # Com a UF, todo municipio da tabela resolve para ele mesmo.
    for m in resolver._municipios:
        r = resolver.resolve(name=m.nome, uf=m.codigo_uf)
        assert r.resolved and r.municipio.codigo_ibge == m.codigo_ibge


# --- Achado 2: o dado oficial e inconsistente consigo mesmo -----------------


def test_grafia_inconsistente_do_apostrofo(nomes):
    # A mesma preposicao contraida aparece com D maiusculo e minusculo
    # (D'Oeste/d'Oeste, D'Água/d'Água, D'Arco/d'Arco).
    assert sum("D'" in n for n in nomes) == 17
    assert sum("d'" in n for n in nomes) == 29
    assert sum("D'Oeste" in n for n in nomes) == 13
    assert sum("d'Oeste" in n for n in nomes) == 12


def test_normalizacao_unifica_o_apostrofo(resolver):
    # "Pau D'Arco" (TO) e "Pau d'Arco" (PA) sao municipios distintos;
    # normalizados, viram o mesmo nome e so a UF separa os dois.
    assert normalize_name("Pau D'Arco") == normalize_name("Pau d'Arco")
    assert resolver.resolve(name="Pau d'Arco").ambiguous
    assert resolver.resolve(name="PAU D ARCO", uf="15").resolved


# --- Achado 3: remover acento cria colisoes novas ---------------------------


def _sem_acento(nome: str) -> str:
    decomposto = unicodedata.normalize("NFKD", nome)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def test_remover_acento_introduz_colisoes(nomes):
    grupos: dict[str, set[str]] = {}
    for n in nomes:
        grupos.setdefault(_sem_acento(n), set()).add(n)
    colisoes = {k for k, v in grupos.items() if len(v) > 1}
    assert len(colisoes) == 8
    assert {"Aracoiaba", "Ipora"} <= colisoes


@pytest.mark.parametrize(
    "nome, uf, esperado",
    [
        ("Aracoiaba", UF_CE, "2301208"),
        ("Araçoiaba", UF_PE, "2601052"),
        ("Iporá", UF_GO, "5210208"),
        ("Iporã", UF_PR, "4110607"),
    ],
)
def test_colisao_de_acento_nunca_e_adivinhada(resolver, nome, uf, esperado):
    # Sem UF, o resolver devolve ambiguo; com UF, acerta o municipio.
    sem_uf = resolver.resolve(name=nome)
    assert sem_uf.ambiguous and len(sem_uf.candidates) == 2
    com_uf = resolver.resolve(name=nome, uf=uf)
    assert com_uf.municipio.codigo_ibge == esperado
