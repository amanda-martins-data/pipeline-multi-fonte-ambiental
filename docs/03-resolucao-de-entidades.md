# 03 - Resolução de entidades: qual município é esse?

Três fontes precisam se encontrar na dimensão município. O IBGE identifica municípios por um código de 7 dígitos. O INMET identifica estações por um nome livre ("RIO DE JANEIRO - VILA MILITAR") e uma sigla de UF. A CETESB, via OpenAQ, identifica por coordenada. Nenhuma delas compartilha uma chave com as outras.

Este documento registra o que medi ao tentar ligar essas fontes e explica por que o resolver em `src/normalize/municipio_resolver.py` funciona em camadas. Todos os números são reproduzíveis: os da tabela do IBGE estão cobertos por `tests/test_municipio_resolver.py`, e os do INMET saem das 594 estações de 2025.

## A referência

A tabela de municípios (`scripts/fetch_reference.py`) tem 5.571 linhas: os 5.570 municípios mais o distrito estadual de Fernando de Noronha, que a fonte inclui com código próprio.

## Achado 1: nome de município não é chave

Depois de normalizar (sem acento, maiúsculas, sem pontuação), **241 nomes apontam para mais de um município**, somando 521 registros. Isso deixa 9,4% dos municípios brasileiros fora do alcance de uma busca só pelo nome. "Bom Jesus" existe em 5 estados.

| Evidência disponível | Municípios resolvidos | Taxa |
|---|---|---|
| Nome + UF | 5.571 de 5.571 | 100% |
| Só nome | 5.050 de 5.571 | 90,6% |

Com a UF, o nome basta para a tabela inteira. Sem ela, 521 municípios ficam ambíguos, e o resolver devolve os candidatos sem escolher um.

## Achado 2: o dado oficial diverge de si mesmo

A mesma contração aparece com as duas caixas na tabela do IBGE: 17 nomes usam `D'` e 29 usam `d'` (`Olho D'Água do Piauí` ao lado de `Olho d'Água das Flores`). Só com `Oeste`, são 13 `D'Oeste` e 12 `d'Oeste`.

Na prática, comparar nomes sem normalizar a caixa faz municípios que existem deixarem de ser encontrados. `Pau D'Arco` (TO) e `Pau d'Arco` (PA) são municípios diferentes, e só a UF os distingue.

## Achado 3: remover acento cria colisões novas

Remover acentos parece a correção óbvia para grafias divergentes entre fontes. Ela junta **8 pares de municípios distintos** na mesma chave:

| Sem acento | Municípios distintos |
|---|---|
| Aracoiaba | Aracoiaba (CE), Araçoiaba (PE) |
| Arapua | Arapuã (PR), Arapuá (MG) |
| Goiana | Goiana (PE), Goianá (MG) |
| Ipira | Ipira (SC), Ipirá (BA) |
| Ipora | Iporá (GO), Iporã (PR) |
| Marau | Marau (RS), Maraú (BA) |
| Parana | Paraná (RN), Paranã (TO) |
| Quixaba | Quixaba (PE), Quixabá (PB) |

Por isso a normalização nunca decide sozinha. Quando há mais de um candidato, o resolver exige a UF ou devolve ambíguo.

## Achado 4: as estações do INMET

Resolvendo as 594 estações de 2025 por nome + UF, **534 resolvem (89,9%) e 60 falham**. As falhas seguem um padrão:

| Padrão | Estações | Exemplos |
|---|---|---|
| Município + sufixo de bairro ou local | 33 | `PORTO ALEGRE - BELEM NOVO`, `SAO PAULO - MIRANTE`, `IBIRITE ROLA MOCA` |
| Abreviação | 3 | `MAL. CANDIDO RONDON`, `S. G. DA CACHOEIRA`, `S.J. DO RIO CLARO` |
| Grafia divergente do IBGE | 4 | `ARCO VERDE` (Arcoverde), `SANTANA DO LIVRAMENTO` (Sant'Ana do Livramento), `CAMPO NOVO DOS PARECIS`, `MARIANOPOLIS DO TO` |
| Local que não é sede municipal | 20 | `PICO DO COUTO`, `SERRA DOS CARAJAS`, `ABROLHOS`, `NHUMIRIM`, regiões administrativas do DF |

Os 33 do primeiro grupo resolveriam pelo maior prefixo do nome que casa com um município da UF. Não adotei isso como regra automática: o prefixo acerta `PORTO ALEGRE - BELEM NOVO`, e nada garante que o texto antes do separador seja sempre o município (`NOVA PORTEIRINHA JANAUBA` cita dois municípios vizinhos).

Li os nomes nos nomes de arquivo do INMET. Nos arquivos que conferi, o nome no cabeçalho da estação é idêntico ao do arquivo.

### O caso que quase passou errado

A estação `SAO GONCALO` fica na Paraíba, onde não existe município com esse nome. Na primeira versão do resolver, a última camada (nome único no país) rodava mesmo com a UF informada e devolvia São Gonçalo (RJ), a 1.850 km. A falha era invisível: um acerto aparente, com a estratégia registrada como resolvida.

Corrigi restringindo essa camada aos casos sem UF. O teste `test_uf_informada_nunca_e_ignorada` cobre o caso.

## As camadas do resolver

Cada resolução registra a estratégia usada, para que eu possa auditar a confiança do resultado depois.

| Camada | Evidência | Quando vale |
|---|---|---|
| 1 | Código IBGE de 7 dígitos | Sempre que o código existe na referência |
| 2 | Código de 6 dígitos (sem verificador, formato do DATASUS) | Quando o prefixo aponta para um único município |
| 3 | Nome exato + UF | Grafia idêntica à do IBGE |
| 4 | Nome normalizado + UF | Diferenças de acento, caixa e pontuação |
| 5 | Nome normalizado, sem UF | Quando a UF não foi informada e o nome é único no país |
| - | Não resolvido | Ambíguo (com candidatos) ou não encontrado |

A ordem vai da evidência mais forte para a mais fraca. Um código válido vence um nome divergente, e nenhuma camada escolhe entre candidatos empatados.

## E a coordenada?

Para as 60 estações que falharam, tentei atribuir o município de centroide mais próximo. Essa estratégia erra justamente onde as estações se concentram, em região metropolitana. A análise e a decisão estão na ADR 0012, e a escolha da chave de junção está na ADR 0011.
