# Pipeline Multi-Fonte Ambiental

[![CI](https://github.com/amanda-martins-data/pipeline-multi-fonte-ambiental/actions/workflows/ci.yml/badge.svg)](https://github.com/amanda-martins-data/pipeline-multi-fonte-ambiental/actions/workflows/ci.yml)

Integração de fontes públicas brasileiras heterogêneas: dados meteorológicos do INMET, qualidade do ar da CETESB (via OpenAQ) e a tabela de municípios do IBGE. O foco é o problema que mais consome tempo em engenharia de dados: **dados reais, sujos, em volume, e chaves que não casam**.

Projeto 13 de uma série que documenta minha transição de Analista de Dados para Arquitetura de Dados. Veja o [perfil completo](https://github.com/amanda-martins-data).

## Por que este projeto existe

Os 12 projetos anteriores rodavam sobre uma fonte única, bem comportada e de volume pequeno. Foi uma escolha consciente de proporcionalidade, e deixou três lacunas: escala, heterogeneidade e sujeira real.

Este projeto também executa uma decisão que eu já tinha registrado. O [ADR 0008](https://github.com/amanda-martins-data/adr-arquitetura-dados/blob/main/decisions/0008-modelagem-star-schema-vs-data-vault-vs-obt.md) dizia:

> "O gatilho concreto para migrar da Opção C (OBT) para a Opção A (Star Schema) é a chegada de uma segunda fonte de dados que compartilhe dimensões (cidade, tempo) com a atual."

O gatilho chegou.

## Dados reais processados

| Fonte | Volume |
|---|---|
| INMET 2025 | 594 estações, **5.025.594 linhas** (5.020.248 de medição), 359 MB |
| INMET 2023 | 567 estações, 415 MB |
| IBGE | 5.570 municípios com coordenadas, mais o distrito estadual de Fernando de Noronha (5.571 linhas) |
| CETESB via OpenAQ | 3.993 medições horárias (jan a abr/2023), 1.072 horas distintas |

## Os achados

Medi todos sobre dado real, e os testes os reproduzem.

**1. Nome de município não é chave.** 241 nomes normalizados apontam para mais de um município, o que afeta 521 registros. Isso deixa **9,4% dos municípios brasileiros fora do alcance de uma busca só pelo nome**. "Bom Jesus" existe em 5 estados.

**2. O dado oficial do IBGE diverge de si mesmo.** A mesma contração aparece com as duas caixas: 17 nomes usam `D'` e 29 usam `d'` (`D'Água`/`d'Água`, `D'Arco`/`d'Arco`). Só com `Oeste`, são 13 `D'Oeste` e 12 `d'Oeste`.

**3. Remover acento introduz 8 colisões novas.** `Araçoiaba` (PE) e `Aracoiaba` (CE) são municípios distintos que viram a mesma chave, e o mesmo vale para `Iporá` (GO) e `Iporã` (PR). A correção mais óbvia cria o bug.

**4. 89,9% das estações do INMET resolvem por nome, e 60 falham.** As falhas seguem um padrão: sufixo de bairro, parêntese, abreviação, grafia divergente e estações fora de sede municipal. Uma delas quase passou errada: `SAO GONCALO` (PB) não existe como município na Paraíba, e o resolver chegou a devolver São Gonçalo (RJ), a 1.850 km. Hoje, com a UF informada, ele só procura dentro dela.

**5. Coordenada resolve parte dos casos e erra em região metropolitana.** `RIO DE JANEIRO - VILA MILITAR` é atribuída a Nilópolis, a 6,3 km, porque eu comparo com o centroide, que ignora o formato do polígono do município. Por isso trato a coordenada como evidência auxiliar, com limiar de distância, e deixo o nome propor o candidato (ver [ADR 0012](decisions/0012-estrategia-para-municipios-sem-correspondencia.md)).

## A sujeira do INMET, medida

| Problema | Evidência |
|---|---|
| Encoding | ISO-8859-1; UTF-8 falha no byte 0xC7 |
| Cabeçalho | Fica na **linha 9**; as 8 primeiras são metadados |
| Separador | `;` com vírgula decimal (`886,1`) |
| Coluna fantasma | `;` no fim de toda linha cria uma coluna vazia |
| Hora | Formato `0000 UTC` |
| Ausência | Campo vazio **e** sentinela `-9999` |

## Estrutura

```
.
├── decisions/          ADRs 0011 e 0012, continuando a numeração do Projeto 07
├── docs/               achados medidos e metodologia
├── scripts/            download da tabela de referência
├── src/
│   ├── extract/        parser do INMET
│   └── normalize/      resolver de municípios
└── tests/
```

## Como rodar

```bash
pip install -r requirements.txt
python scripts/fetch_reference.py
python -m pytest tests/ -v
```

A tabela de municípios fica fora do versionamento. São 390 KB de dado público com fonte estável, e uma cópia no repositório poderia divergir da origem sem ninguém perceber. Os testes que dependem dela são pulados quando o arquivo não existe.

## Limitações desta versão

Registro aqui o que ainda falta:

- **O join é assimétrico.** O INMET cobre 8.760 horas do ano e a CETESB cobre 1.072 (12%). O explorador do OpenAQ limita cada download a 30 dias, o que torna um ano inteiro inviável manualmente.
- **Uma estação de qualidade do ar.** O cruzamento está provado de ponta a ponta com ela, e a resolução de municípios em escala roda sobre o INMET.
- **Resolução espacial por centroide.** A correção seria usar a malha territorial do IBGE, e o gatilho para isso está no ADR 0012.
- **A quarentena está decidida e ainda não implementada.** Hoje o resolver devolve `UNRESOLVED_NOT_FOUND` ou `UNRESOLVED_AMBIGUOUS`, e o destino desses registros fica para a camada de transformação, que adiei.
