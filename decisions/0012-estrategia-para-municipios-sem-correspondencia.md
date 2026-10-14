# ADR 0012: Tratar coordenada como evidência auxiliar e mandar os não resolvidos para quarentena

## Status

Aceita (quarentena ainda não implementada no pipeline; ver Consequências)

## Contexto

A ADR 0011 definiu o código IBGE como chave da dimensão município e o nome + UF como caminho para chegar a ele. Aplicado às 594 estações do INMET de 2025, esse caminho resolve 534 (89,9%) e deixa 60 sem município:

- 33 são nome de município com sufixo de bairro ou local (`PORTO ALEGRE - BELEM NOVO`, `SAO PAULO - MIRANTE`);
- 3 são abreviações (`MAL. CANDIDO RONDON`);
- 4 têm grafia divergente do IBGE (`ARCO VERDE`, `SANTANA DO LIVRAMENTO`);
- 20 são locais que não são sede municipal (`PICO DO COUTO`, `ABROLHOS`, regiões administrativas do DF).

Toda estação do INMET traz latitude e longitude no cabeçalho do arquivo. A tentação óbvia é usar a coordenada para resolver as 60, atribuindo o município de centroide mais próximo.

Medi essa tentativa, e ela erra onde as estações mais se concentram:

| Estação | Município correto | Centroide mais próximo |
|---|---|---|
| `RIO DE JANEIRO - VILA MILITAR` | Rio de Janeiro (centroide a 22,4 km) | Nilópolis, a 6,3 km |
| `PORTO ALEGRE - BELEM NOVO` | Porto Alegre (centroide a 17,4 km, o terceiro mais próximo) | Guaíba, a 16,4 km |
| `SAO GONCALO` (PB) | não confirmado | Marizópolis, a 4,6 km |

O motivo é geométrico: o centroide de um município grande fica longe das suas bordas. Uma estação na zona oeste do Rio de Janeiro está mais perto do centro de Nilópolis, um município pequeno e vizinho, do que do centro do Rio. Comparar com o centroide ignora o formato do polígono e não diz se o ponto está dentro do município.

## Opções consideradas

### Opção A - Coordenada como critério decisivo (centroide mais próximo)
- Prós: resolve 100% das estações, sem trabalho manual, usando um dado que já está no arquivo.
- Contras: erra em silêncio justamente nas capitais e regiões metropolitanas, onde está a maior parte das estações urbanas e dos dados de qualidade do ar. Contradiz o critério da ADR 0011 de que um erro silencioso é pior que uma falha visível.

### Opção B - Coordenada como evidência auxiliar, com quarentena
- Prós: a coordenada confirma uma hipótese vinda do nome (o prefixo `PORTO ALEGRE` e o município de Porto Alegre estão a menos de um limiar de distância), e o nome continua sendo a fonte da hipótese. O que não se confirma vai para uma tabela de quarentena explícita, com o motivo.
- Contras: não resolve tudo. Exige manter a quarentena e revisar os casos que ficam nela. O limiar de distância é um parâmetro a mais para justificar.

### Opção C - Descartar as estações não resolvidas
- Prós: simples, e a Gold só recebe o que casou.
- Contras: perde 10% das estações sem registro do motivo, incluindo as duas da cidade de São Paulo (`SAO PAULO - MIRANTE` e `SAO PAULO - INTERLAGOS`), a mesma cidade da estação da CETESB usada neste projeto (Cerqueira César). Descartar as duas deixaria o cruzamento sem nenhuma estação do INMET dentro da cidade.

### Opção D - Ponto no polígono, com a malha territorial do IBGE
- Prós: resolve a causa do erro. Uma estação dentro do polígono do Rio de Janeiro é do Rio de Janeiro, sem ambiguidade.
- Contras: exige a malha municipal do IBGE (arquivo geográfico bem maior que a tabela de municípios) e uma dependência geoespacial. É desproporcional para o volume atual de 60 estações.

## Decisão

Escolhi a Opção B. A coordenada entra como evidência auxiliar: ela pode confirmar um município proposto pelo nome (por exemplo, pelo maior prefixo do nome que casa com um município da UF), se o centroide desse município estiver dentro de um limiar de distância. A hipótese sempre nasce do nome. O que não se confirma vai para uma tabela de quarentena com a estação, o motivo e os candidatos.

O critério de desempate entre B e D foi a proporcionalidade. D é a resposta correta para o problema geométrico, e custa uma dependência nova para resolver 60 linhas de referência que mudam raramente. Com B, aceito deixar alguns casos em quarentena para revisão manual e evito essa dependência agora. Descartei A e C pelo mesmo motivo da ADR 0011: elas erram ou perdem dados sem sinal.

## Consequências

Alguns casos continuam sem município e dependem de revisão manual. Os 20 locais que não são sede municipal (parques, serras, faróis, regiões do DF) são os candidatos mais prováveis a ficar na quarentena.

A quarentena ainda não está implementada no pipeline. Hoje o resolver devolve `UNRESOLVED_NOT_FOUND` ou `UNRESOLVED_AMBIGUOUS`, e o destino desses registros fica para a camada de transformação (`src/transform/`, adiada).

Preciso escolher e justificar o limiar de distância quando implementar a confirmação por coordenada. Os casos medidos aqui mostram que ele não pode ser pequeno: as estações estão a 22,4 km do centroide do Rio de Janeiro e a 17,4 km do de Porto Alegre, que são os municípios corretos. Um limiar que funcione para municípios grandes também aceita municípios vizinhos inteiros, e por isso a coordenada só confirma um candidato vindo do nome e nunca escolhe entre vizinhos.

Gatilho de revisão: a quarentena passar das 60 estações medidas aqui, ou a entrada de uma fonte identificada só por coordenada em região metropolitana (por exemplo, mais estações de qualidade do ar). Nesse ponto a Opção D deixa de ser desproporcional, e a malha territorial do IBGE deve substituir o centroide.
