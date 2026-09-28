# ADR 0011: Usar o codigo IBGE como chave de juncao da dimensao municipio, com nome + UF como fallback em camadas

## Status

Aceita (implementada em `src/normalize/municipio_resolver.py`)

## Contexto

A ADR 0008 deixou registrado que a chegada de uma segunda fonte de
dados compartilhando a dimensao cidade seria o gatilho para migrar a
camada Gold de One Big Table para Star Schema. Este projeto e esse
gatilho: INMET, CETESB (via OpenAQ) e IBGE precisam se encontrar em
uma dimensao municipio unica.

O problema e que cada fonte identifica o municipio de um jeito. O
IBGE usa um codigo de 7 digitos. O INMET usa um nome livre de
estacao e a sigla da UF. Fontes do DATASUS usam o codigo de 6
digitos, sem o digito verificador. Medido sobre a tabela do IBGE,
241 nomes normalizados apontam para mais de um municipio (521
registros, 9,4% do pais), e remover acentos junta 8 pares de
municipios distintos. Ver `docs/03-resolucao-de-entidades.md`.

A decisao aqui e qual chave a dimensao usa e o que fazer quando a
fonte nao traz essa chave.

## Opcoes consideradas

### Opcao A - Nome do municipio como chave
- Pros: e o que as fontes mais trazem; nao exige nenhuma tabela de
  referencia para comecar.
- Contras: nao e unico. 9,4% dos municipios ficam inalcancaveis so
  pelo nome, e o proprio IBGE grafa a mesma contracao de dois jeitos
  (17 nomes com `D'`, 29 com `d'`). Uma juncao por nome erra em
  silencio: junta Bom Jesus (PI) com Bom Jesus (RS) sem avisar.

### Opcao B - Nome + UF como chave
- Pros: resolve 100% da tabela de referencia; as fontes quase sempre
  trazem a UF.
- Contras: continua dependente de grafia. Das 594 estacoes do INMET,
  60 nao resolvem por nome + UF (sufixo de bairro, abreviacao, grafia
  divergente, local que nao e sede). E uma chave composta de texto,
  mais cara de indexar e facil de corromper em uma transformacao.

### Opcao C - Codigo IBGE de 7 digitos como chave, com resolucao em camadas
- Pros: e a chave oficial, estavel e unica; e a que o IBGE e varias
  fontes publicas ja usam. O codigo de 6 digitos do DATASUS se
  reconcilia com ela por prefixo. Nome + UF entra como evidencia para
  chegar ao codigo, nao como chave.
- Contras: exige manter uma tabela de referencia e um passo de
  resolucao para toda fonte que nao traz o codigo. Registros nao
  resolvidos precisam de um destino explicito.

## Decisao

Opcao C. A chave da dimensao municipio e o codigo IBGE de 7 digitos.
Fontes sem o codigo passam pelo resolver, que tenta, nesta ordem:
codigo de 7 digitos, codigo de 6 digitos, nome exato + UF, nome
normalizado + UF e, so quando a UF nao foi informada, nome normalizado
unico no pais.

O criterio de desempate entre B e C foi o custo do erro silencioso.
Uma juncao que falha e visivel e pode ser tratada; uma juncao que
acerta o municipio errado contamina a Gold sem sinal nenhum. Por isso
o resolver nunca escolhe entre candidatos empatados (devolve ambiguo,
com os candidatos), e cada resolucao registra a estrategia usada.

O caso que confirmou o criterio: a estacao `SAO GONCALO` (PB) foi
resolvida, na primeira versao, para Sao Goncalo (RJ), a 1.850 km,
porque a camada de nome unico ignorava a UF informada. A correcao foi
restringir essa camada aos casos sem UF.

## Consequencias

A tabela de referencia do IBGE vira dependencia do pipeline. Ela nao
e versionada (ver README); os testes que dependem dela sao pulados se
o arquivo nao existir.

Toda fonte nova precisa de um passo de resolucao antes de entrar na
dimensao, e os nao resolvidos precisam de destino. Para o INMET, esse
destino e o tema da ADR 0012.

A estrategia registrada em cada resolucao permite medir a qualidade da
juncao por fonte, mas so se ela for levada adiante ate a Silver. Se
for descartada no caminho, a auditoria se perde.

Gatilho de revisao: a entrada de uma fonte que identifique municipios
por um codigo que nao seja o do IBGE (por exemplo, codigo TSE ou
SIAFI). Nesse caso, a tabela de referencia passa a precisar de uma
tabela de equivalencia de codigos, e o resolver ganha uma camada.
