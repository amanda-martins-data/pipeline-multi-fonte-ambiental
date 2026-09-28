# ADR 0012: Tratar coordenada como evidencia auxiliar e mandar os nao resolvidos para quarentena

## Status

Aceita (quarentena ainda nao implementada no pipeline - ver
Consequencias)

## Contexto

A ADR 0011 definiu o codigo IBGE como chave da dimensao municipio e o
nome + UF como caminho para chegar a ele. Aplicado as 594 estacoes do
INMET de 2025, esse caminho resolve 534 (89,9%) e deixa 60 sem
municipio:

- 33 sao nome de municipio com sufixo de bairro ou local
  (`PORTO ALEGRE - BELEM NOVO`, `SAO PAULO - MIRANTE`);
- 3 sao abreviacoes (`MAL. CANDIDO RONDON`);
- 4 tem grafia divergente do IBGE (`ARCO VERDE`, `SANTANA DO
  LIVRAMENTO`);
- 20 sao locais que nao sao sede municipal (`PICO DO COUTO`,
  `ABROLHOS`, regioes administrativas do DF).

Toda estacao do INMET traz latitude e longitude no cabecalho do
arquivo. A tentacao obvia e usar a coordenada para resolver as 60:
atribuir o municipio de centroide mais proximo.

Essa tentativa foi medida, e erra onde as estacoes mais se
concentram:

| Estacao | Municipio correto | Centroide mais proximo |
|---|---|---|
| `RIO DE JANEIRO - VILA MILITAR` | Rio de Janeiro (centroide a 22,4 km) | Nilopolis, a 6,3 km |
| `PORTO ALEGRE - BELEM NOVO` | Porto Alegre (centroide a 17,4 km, o terceiro mais proximo) | Guaiba, a 16,4 km |
| `SAO GONCALO` (PB) | nao confirmado | Marizopolis, a 4,6 km |

O motivo e geometrico: o centroide de um municipio grande fica longe
das suas bordas. Uma estacao na zona oeste do Rio de Janeiro esta mais
perto do centro de Nilopolis, um municipio pequeno e vizinho, do que
do centro do Rio. Comparar com o centroide nao diz se o ponto esta
dentro do poligono do municipio.

## Opcoes consideradas

### Opcao A - Coordenada como criterio decisivo (centroide mais proximo)
- Pros: resolve 100% das estacoes, sem trabalho manual; usa um dado
  que ja esta no arquivo.
- Contras: erra em silencio exatamente nas capitais e regioes
  metropolitanas, onde esta a maior parte das estacoes urbanas e dos
  dados de qualidade do ar. Contradiz o criterio da ADR 0011 de que um
  erro silencioso e pior que uma falha visivel.

### Opcao B - Coordenada como evidencia auxiliar, com quarentena
- Pros: a coordenada confirma uma hipotese vinda do nome (o prefixo
  `PORTO ALEGRE` e o municipio de Porto Alegre estao a menos de um
  limiar de distancia), em vez de gerar a hipotese sozinha. O que nao
  se confirma vai para uma tabela de quarentena explicita, com o
  motivo.
- Contras: nao resolve tudo. Exige manter a quarentena e revisar os
  casos que ficam nela. O limiar de distancia e um parametro a mais
  para justificar.

### Opcao C - Descartar as estacoes nao resolvidas
- Pros: simples; a Gold so recebe o que casou.
- Contras: perde 10% das estacoes sem registro de por que, incluindo
  as duas da cidade de Sao Paulo (`SAO PAULO - MIRANTE` e `SAO PAULO -
  INTERLAGOS`), a mesma cidade da estacao da CETESB usada neste projeto
  (Cerqueira Cesar). Descartar as duas deixaria o cruzamento sem
  nenhuma estacao do INMET dentro da cidade.

### Opcao D - Ponto no poligono, com a malha territorial do IBGE
- Pros: resolve a causa do erro; uma estacao dentro do poligono do
  Rio de Janeiro e do Rio de Janeiro, sem ambiguidade.
- Contras: exige a malha municipal do IBGE (arquivo geografico, bem
  maior que a tabela de municipios) e uma dependencia geoespacial.
  Desproporcional para o volume atual de 60 estacoes.

## Decisao

Opcao B. A coordenada entra como evidencia auxiliar: ela pode
confirmar um municipio proposto pelo nome (por exemplo, pelo maior
prefixo do nome que casa com um municipio da UF), se o centroide desse
municipio estiver dentro de um limiar de distancia. Ela nunca propoe
um municipio sozinha. O que nao se confirma vai para uma tabela de
quarentena com a estacao, o motivo e os candidatos.

O criterio de desempate entre B e D foi proporcionalidade. D e a
resposta correta para o problema geometrico, mas custa uma dependencia
nova para resolver 60 linhas de referencia, que mudam raramente. B
aceita deixar alguns casos em quarentena e revisados a mao em troca de
nao adicionar essa dependencia agora. A e C foram descartadas pelo
mesmo motivo da ADR 0011: erram ou perdem dados sem sinal.

## Consequencias

Alguns casos continuam sem municipio e dependem de revisao manual. Os
20 locais que nao sao sede municipal (parques, serras, farois,
regioes do DF) sao os candidatos mais provaveis a ficar na quarentena.

A quarentena ainda nao esta implementada no pipeline; hoje o resolver
devolve `UNRESOLVED_NOT_FOUND` ou `UNRESOLVED_AMBIGUOUS`, e o destino
desses registros fica para a camada de transformacao
(`src/transform/`, adiada).

O limiar de distancia precisa ser escolhido e justificado quando a
confirmacao por coordenada for implementada, e os casos medidos aqui
mostram que ele nao pode ser pequeno: as estacoes estao a 22,4 km do
centroide do Rio de Janeiro e a 17,4 km do de Porto Alegre, os
municipios corretos. Um limiar que funcione para municipios grandes
tambem aceita municipios vizinhos inteiros, e por isso a coordenada so
confirma um candidato vindo do nome, nunca escolhe entre vizinhos.

Gatilho de revisao: a quarentena passar das 60 estacoes medidas aqui,
ou a entrada de uma fonte identificada so por coordenada em regiao
metropolitana (por exemplo, mais estacoes de qualidade do ar). Nesse
ponto a Opcao D deixa de ser desproporcional, e a malha territorial do
IBGE deve substituir o centroide.
