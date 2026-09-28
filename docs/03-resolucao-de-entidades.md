# 03 - Resolucao de entidades: qual municipio e esse?

Tres fontes precisam se encontrar na dimensao municipio. O IBGE
identifica municipios por um codigo de 7 digitos. O INMET identifica
estacoes por um nome livre ("RIO DE JANEIRO - VILA MILITAR") e uma
sigla de UF. A CETESB, via OpenAQ, identifica por coordenada. Nenhuma
delas compartilha uma chave com as outras.

Este documento registra o que foi medido ao tentar ligar essas fontes,
e por que o resolver em `src/normalize/municipio_resolver.py` funciona
em camadas. Todos os numeros sao reproduziveis: os da tabela do IBGE
estao cobertos por `tests/test_municipio_resolver.py`, e os do INMET
foram medidos sobre as 594 estacoes de 2025.

## A referencia

A tabela de municipios (`scripts/fetch_reference.py`) tem 5.571
linhas: os 5.570 municipios mais o distrito estadual de Fernando de
Noronha, que a fonte inclui com codigo proprio.

## Achado 1: nome nao e chave

Depois de normalizar (sem acento, maiusculas, sem pontuacao), **241
nomes apontam para mais de um municipio**, somando 521 registros. Ou
seja, 9,4% dos municipios brasileiros nao podem ser identificados so
pelo nome. "Bom Jesus" existe em 5 estados.

| Evidencia disponivel | Municipios resolvidos | Taxa |
|---|---|---|
| Nome + UF | 5.571 de 5.571 | 100% |
| So nome | 5.050 de 5.571 | 90,6% |

Com a UF, o nome volta a ser suficiente para a tabela inteira. Sem
ela, 521 municipios ficam ambiguos, e o resolver devolve os candidatos
em vez de escolher um.

## Achado 2: o dado oficial e inconsistente consigo mesmo

A mesma contracao aparece com as duas caixas na tabela do IBGE: 17
nomes usam `D'` e 29 usam `d'` (`Olho D'Água do Piauí` ao lado de
`Olho d'Água das Flores`). So com `Oeste`, sao 13 `D'Oeste` contra
12 `d'Oeste`.

Consequencia pratica: comparar nomes sem normalizar a caixa deixa de
encontrar municipios que existem. `Pau D'Arco` (TO) e `Pau d'Arco`
(PA) sao municipios diferentes que so se distinguem pela UF.

## Achado 3: remover acento cria colisoes novas

Remover acentos parece a correcao obvia para grafias divergentes entre
fontes. Mas ela junta **8 pares de municipios distintos** na mesma
chave:

| Sem acento | Municipios distintos |
|---|---|
| Aracoiaba | Aracoiaba (CE), Araçoiaba (PE) |
| Arapua | Arapuã (PR), Arapuá (MG) |
| Goiana | Goiana (PE), Goianá (MG) |
| Ipira | Ipira (SC), Ipirá (BA) |
| Ipora | Iporá (GO), Iporã (PR) |
| Marau | Marau (RS), Maraú (BA) |
| Parana | Paraná (RN), Paranã (TO) |
| Quixaba | Quixaba (PE), Quixabá (PB) |

Por isso a normalizacao nunca decide sozinha: quando ha mais de um
candidato, o resolver exige a UF ou devolve ambiguo.

## Achado 4: as estacoes do INMET

Resolvendo as 594 estacoes de 2025 por nome + UF, **534 resolvem
(89,9%) e 60 nao resolvem**. As falhas tem padrao:

| Padrao | Estacoes | Exemplos |
|---|---|---|
| Municipio + sufixo de bairro ou local | 33 | `PORTO ALEGRE - BELEM NOVO`, `SAO PAULO - MIRANTE`, `IBIRITE ROLA MOCA` |
| Abreviacao | 3 | `MAL. CANDIDO RONDON`, `S. G. DA CACHOEIRA`, `S.J. DO RIO CLARO` |
| Grafia divergente do IBGE | 4 | `ARCO VERDE` (Arcoverde), `SANTANA DO LIVRAMENTO` (Sant'Ana do Livramento), `CAMPO NOVO DOS PARECIS`, `MARIANOPOLIS DO TO` |
| Local que nao e sede municipal | 20 | `PICO DO COUTO`, `SERRA DOS CARAJAS`, `ABROLHOS`, `NHUMIRIM`, regioes administrativas do DF |

Os 33 do primeiro grupo resolveriam pelo maior prefixo do nome que
casa com um municipio da UF. Isso nao foi adotado como regra
automatica: o prefixo acerta `PORTO ALEGRE - BELEM NOVO`, mas nada
garante que o texto antes do separador seja sempre o municipio
(`NOVA PORTEIRINHA JANAUBA` cita dois municipios vizinhos).

Os nomes foram lidos dos nomes de arquivo do INMET. Nos arquivos
conferidos, o nome no cabecalho da estacao e identico ao do arquivo.

### O caso que quase passou errado

A estacao `SAO GONCALO` fica na Paraiba, onde nao existe municipio com
esse nome. Na primeira versao do resolver, a ultima camada (nome unico
no pais) rodava mesmo com a UF informada, e devolvia Sao Goncalo (RJ),
a 1.850 km. Nao era uma falha visivel: era um acerto aparente, com a
estrategia registrada como resolvida.

A correcao foi restringir essa camada aos casos sem UF. O teste
`test_uf_informada_nunca_e_ignorada` cobre o caso.

## As camadas do resolver

Cada resolucao registra a estrategia usada, para que a confianca do
resultado possa ser auditada depois.

| Camada | Evidencia | Quando vale |
|---|---|---|
| 1 | Codigo IBGE de 7 digitos | Sempre que o codigo existe na referencia |
| 2 | Codigo de 6 digitos (sem verificador, formato do DATASUS) | Quando o prefixo aponta para um unico municipio |
| 3 | Nome exato + UF | Grafia identica a do IBGE |
| 4 | Nome normalizado + UF | Diferencas de acento, caixa e pontuacao |
| 5 | Nome normalizado, sem UF | So quando a UF nao foi informada e o nome e unico no pais |
| - | Nao resolvido | Ambiguo (com candidatos) ou nao encontrado |

A ordem vai da evidencia mais forte para a mais fraca. Um codigo
valido vence um nome divergente; nenhuma camada escolhe entre
candidatos empatados.

## E a coordenada?

A tentativa seguinte para as 60 estacoes foi atribuir o municipio de
centroide mais proximo. Ela erra justamente onde as estacoes se
concentram, em regiao metropolitana. A analise e a decisao estao na
ADR 0012; a escolha da chave de juncao, na ADR 0011.
