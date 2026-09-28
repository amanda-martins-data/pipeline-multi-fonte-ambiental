# Pipeline Multi-Fonte Ambiental

Integracao de fontes publicas brasileiras heterogeneas - dados
meteorologicos do INMET, qualidade do ar da CETESB (via OpenAQ) e a
tabela de municipios do IBGE - com foco no problema que de fato
consome o tempo em engenharia de dados: **dados reais, sujos, em
volume, e chaves que nao casam**.

Projeto 13 de uma serie documentando minha transicao de Analista de
Dados para Arquitetura de Dados - veja o [perfil
completo](https://github.com/amanda-martins-data).

## Por que este projeto existe

Os 12 projetos anteriores rodavam sobre uma fonte unica, bem
comportada e de volume pequeno. Isso foi uma escolha consciente de
proporcionalidade, mas deixava tres lacunas: escala, heterogeneidade
e sujeira real.

Este projeto tambem **executa uma decisao ja registrada**. O
[ADR 0008](https://github.com/amanda-martins-data/adr-arquitetura-dados/blob/main/decisions/0008-modelagem-star-schema-vs-data-vault-vs-obt.md)
dizia:

> "O gatilho concreto para migrar da Opcao C (OBT) para a Opcao A
> (Star Schema) e a chegada de uma segunda fonte de dados que
> compartilhe dimensoes (cidade, tempo) com a atual."

O gatilho chegou.

## Dados reais processados

| Fonte | Volume |
|---|---|
| INMET 2025 | 594 estacoes, **5.025.594 linhas**, 359 MB |
| INMET 2023 | 567 estacoes, 415 MB |
| IBGE | 5.570 municipios com coordenadas (mais o distrito estadual de Fernando de Noronha, 5.571 linhas) |
| CETESB via OpenAQ | 3.993 medicoes horarias (jan-abr/2023) |

## Os achados

Todos medidos sobre dado real, reproduziveis pelos testes.

**1. Nome de municipio nao e chave.** 241 nomes normalizados
apontam para mais de um municipio, afetando 521 registros:
**9,4% dos municipios brasileiros sao inalcancaveis apenas pelo
nome**. "Bom Jesus" existe em 5 estados.

**2. O dado oficial do IBGE e inconsistente consigo mesmo.**
A mesma contracao aparece com as duas caixas: 17 nomes usam `D'`
e 29 usam `d'` (`D'Água`/`d'Água`, `D'Arco`/`d'Arco`). So com
`Oeste`, sao 13 `D'Oeste` contra 12 `d'Oeste`.

**3. Remover acento introduz 8 erros novos.** `Aracoiaba` (CE) e
`Araçoiaba` (PE) sao municipios distintos que viram a mesma chave.
`Iporá` (GO) e `Iporã` (PR) tambem. A correcao obvia cria o bug.

**4. 89,9% das estacoes INMET resolvem por nome; 60 falham** - e as
falhas tem padrao: sufixo de bairro, parentetico, abreviacao,
grafia divergente, e estacoes que nao ficam em sede municipal.
Uma delas quase passou errada: `SAO GONCALO` (PB) nao existe como
municipio na Paraiba, e o resolver chegou a devolver Sao Goncalo
(RJ), a 1.850 km. Hoje, com a UF informada, ele nunca procura fora
dela.

**5. Coordenada resolve parte, mas erra em regiao metropolitana.**
`RIO DE JANEIRO - VILA MILITAR` e atribuido a Nilopolis a 6,3 km,
porque a comparacao e com centroide, nao com poligono. Por isso
coordenada e evidencia auxiliar com limiar, nao criterio decisivo
(ver [ADR 0012](decisions/0012-estrategia-para-municipios-sem-correspondencia.md)).

## A sujeira do INMET, medida

| Problema | Evidencia |
|---|---|
| Encoding | ISO-8859-1; UTF-8 falha no byte 0xC7 |
| Cabecalho | Esta na **linha 9**; as 8 primeiras sao metadados |
| Separador | `;` com virgula decimal (`886,1`) |
| Coluna fantasma | `;` no fim de toda linha cria coluna vazia |
| Hora | Formato `0000 UTC`, nao HH:MM |
| Ausencia | Campo vazio **e** sentinela `-9999` |

## Estrutura

```
.
├── decisions/          ADRs 0011 e 0012, continuando a numeracao do Projeto 07
├── docs/               achados medidos e metodologia
├── scripts/            download da tabela de referencia
├── src/
│   ├── extract/        parser do INMET
│   └── normalize/      resolver de municipios
└── tests/
```

## Como rodar

```bash
pip install -r requirements.txt
python scripts/fetch_reference.py
python -m pytest tests/ -v
```

A tabela de municipios nao e versionada: sao 390 KB de dado publico
com fonte estavel, e versionar copia de dado publico cria risco de
a copia divergir da origem sem ninguem perceber. Os testes que
dependem dela sao pulados se o arquivo nao existir.

## Limitacoes desta versao

Registradas explicitamente, nao escondidas:

- **O join e assimetrico.** O INMET cobre 8.760 horas do ano; a
  CETESB, 1.072 (12%). O explorador do OpenAQ limita cada download
  a 30 dias, o que torna um ano inviavel manualmente.
- **Uma estacao de qualidade do ar, nao varias.** O cruzamento esta
  provado de ponta a ponta, mas a resolucao de municipios em escala
  roda sobre o INMET, nao sobre o join.
- **Centroide, nao poligono.** A resolucao espacial usa o centroide
  do municipio. A correcao seria a malha territorial do IBGE; o
  gatilho esta no ADR 0012.
