# ADR 0011: Usar o código IBGE como chave de junção da dimensão município, com nome + UF como fallback em camadas

## Status

Aceita (implementada em `src/normalize/municipio_resolver.py`)

## Contexto

A ADR 0008 deixou registrado que a chegada de uma segunda fonte de dados compartilhando a dimensão cidade seria o gatilho para migrar a camada Gold de One Big Table para Star Schema. Este projeto é esse gatilho: INMET, CETESB (via OpenAQ) e IBGE precisam se encontrar em uma dimensão município única.

Cada fonte identifica o município de um jeito. O IBGE usa um código de 7 dígitos. O INMET usa um nome livre de estação e a sigla da UF. Fontes do DATASUS usam o código de 6 dígitos, sem o dígito verificador. Medi sobre a tabela do IBGE que 241 nomes normalizados apontam para mais de um município (521 registros, 9,4% do país) e que remover acentos junta 8 pares de municípios distintos. Os detalhes estão em `docs/03-resolucao-de-entidades.md`.

A decisão aqui é qual chave a dimensão usa e o que fazer quando a fonte não traz essa chave.

## Opções consideradas

### Opção A - Nome do município como chave
- Prós: é o que as fontes mais trazem, e não exige nenhuma tabela de referência para começar.
- Contras: nome não é único. 9,4% dos municípios ficam fora do alcance de uma busca só pelo nome, e o próprio IBGE grafa a mesma contração de dois jeitos (17 nomes com `D'`, 29 com `d'`). Uma junção por nome erra em silêncio: junta Bom Jesus (PI) com Bom Jesus (RS) sem avisar.

### Opção B - Nome + UF como chave
- Prós: resolve 100% da tabela de referência, e as fontes quase sempre trazem a UF.
- Contras: continua dependente de grafia. Das 594 estações do INMET, 60 falham por nome + UF (sufixo de bairro, abreviação, grafia divergente, local que não é sede). É também uma chave composta de texto, mais cara de indexar e fácil de corromper em uma transformação.

### Opção C - Código IBGE de 7 dígitos como chave, com resolução em camadas
- Prós: é a chave oficial, estável e única, usada pelo IBGE e por várias fontes públicas. O código de 6 dígitos do DATASUS se reconcilia com ela por prefixo. Nome + UF serve de evidência para chegar ao código.
- Contras: exige manter uma tabela de referência e um passo de resolução para toda fonte que não traz o código. Registros não resolvidos precisam de um destino explícito.

## Decisão

Escolhi a Opção C. A chave da dimensão município é o código IBGE de 7 dígitos. Fontes sem o código passam pelo resolver, que tenta, nesta ordem: código de 7 dígitos, código de 6 dígitos, nome exato + UF, nome normalizado + UF e, quando a UF não foi informada, nome normalizado único no país.

O critério de desempate entre B e C foi o custo do erro silencioso. Uma junção que falha é visível e pode ser tratada, e uma junção que acerta o município errado contamina a Gold sem sinal nenhum. Por isso o resolver nunca escolhe entre candidatos empatados (devolve ambíguo, com os candidatos), e cada resolução registra a estratégia usada.

O caso que confirmou o critério: a estação `SAO GONCALO` (PB) foi resolvida, na primeira versão, para São Gonçalo (RJ), a 1.850 km, porque a camada de nome único ignorava a UF informada. Corrigi restringindo essa camada aos casos sem UF.

## Consequências

A tabela de referência do IBGE vira dependência do pipeline. Ela fica fora do versionamento (ver README), e os testes que dependem dela são pulados se o arquivo não existir.

Toda fonte nova precisa de um passo de resolução antes de entrar na dimensão, e os não resolvidos precisam de destino. Para o INMET, esse destino é o tema da ADR 0012.

A estratégia registrada em cada resolução permite medir a qualidade da junção por fonte, desde que eu a leve adiante até a Silver. Se ela for descartada no caminho, a auditoria se perde.

Gatilho de revisão: a entrada de uma fonte que identifique municípios por um código diferente do IBGE (por exemplo, código TSE ou SIAFI). Nesse caso, a tabela de referência passa a precisar de uma tabela de equivalência de códigos, e o resolver ganha uma camada.
