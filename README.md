# Acervo das Comissões — CMSP

Série histórica do acervo das 7 Comissões Permanentes da Câmara Municipal de São Paulo: quais matérias estão em análise em cada comissão, com qual relator e em que estado da tramitação interna, dia após dia, e o que acontece com os projetos depois (pareceres, votações, desfechos).

O SPLEGIS mostra só o retrato do momento. Este repositório tira um retrato por dia e guarda a evolução, para responder perguntas como "o acervo da CCJ está crescendo ou diminuindo?", "quanto tempo as matérias passaram sem relator ao longo do ano?" ou "em que etapa os projetos mais travam?".

**Painel:** https://prototiposlegisla.github.io/comissoes-acervo/

**Autoria:** criado e mantido por [André Marcon](mailto:andremarcon@saopaulo.sp.leg.br) e Kauê Negrão.

## Como funciona

### O ponto de partida: o relatório do SPLEGIS

Uma das páginas do SPLEGIS Consulta é o relatório [Projetos em Análise nas Comissões](https://splegisconsulta.saopaulo.sp.leg.br/Relatorio/IndexComissaoProjetoTramitacaoInterna). Ele responde à pergunta "o que está com cada comissão agora?". Você escolhe uma das 7 Comissões Permanentes e ele lista as matérias que estão com ela, que formam o acervo da comissão. 

Para cada matéria do acervo, o relatório mostra:

- **o rótulo, a ementa e os autores**, como "PL 502/2026 — Dispõe sobre…";
- **o relator**, se a comissão já designou um;
- **a tramitação externa:** de que área a matéria veio, quando foi enviada à comissão e quando a comissão a recebeu;
- **a tramitação interna:** o último passo dado dentro da comissão, com a data, como "Relator(a) / Estudo para manifestação do relator";
- **os prazos:** há quantos dias a matéria está na comissão e há quantos está no passo atual.

Dá para filtrar por tipo de matéria, autor, relator e outros campos. Além dos projetos (PL, PDL, PR e PLO), o relatório traz documentos recebidos, requerimentos e outros tipos de matéria.

### A ideia

O relatório mostra como o acervo está agora, mas não guarda como estava ontem: quando uma matéria sai da comissão, ela some da lista, e cada passo interno novo toma o lugar do anterior. Este site tira uma "foto" do relatório todo dia, guarda todas as fotos e as transforma em gráficos. Com muitas fotos em sequência, dá para ver o filme: o acervo crescendo, matérias entrando e saindo, quanto tempo cada uma fica parada.

### As quatro peças

1. **O coletor** (pasta [`coletor/`](coletor/)) é um programa em Python que faz o que você faria à mão: abre o relatório de cada comissão e copia a tabela.

   Mas ele não copia o que aparece na tela. Quando você abre o relatório no navegador, a página chega em duas etapas. Primeiro vem a moldura: títulos, filtros e a tabela ainda vazia. Em seguida, o próprio navegador faz um segundo pedido ao SPLEGIS, só pelos dados da tabela, e o SPLEGIS responde com uma lista em formato JSON. JSON é texto organizado em campos com nome, feito para ser lido por programas. Cada matéria vem mais ou menos assim (simplificado):

   ```json
   {"rotulo": "PL 502/2026", "relator": {"texto": "FULANO DE TAL"},
    "tramitacaoInterna": {"tipo": "Estudo para manifestação do relator", "data": "24/08/2026 15:43:00"}}
   ```

   O navegador usa essa lista para preencher a tabela que você vê. O coletor faz esse segundo pedido diretamente, sem passar pela moldura, e recebe os dados já separados em campos, sem precisar garimpá-los do meio do HTML da página.

   Depois, ele grava tudo em arquivos CSV (planilhas em texto puro) na pasta [`dados/`](dados/). Nada do que já foi coletado se perde: o passado fica guardado nos próprios arquivos, como explicado em [Como os dados ficam guardados](#como-os-dados-ficam-guardados).

2. **O agendador** é o GitHub Actions. Ninguém precisa deixar um computador ligado: o GitHub empresta uma máquina temporária para rodar tarefas programadas. O arquivo [`.github/workflows/coleta.yml`](.github/workflows/coleta.yml) diz, em resumo: "às 10h07, às 15h07 e às 21h47, ligue uma máquina, rode os testes, rode o coletor e salve os arquivos no repositório". Cada coleta vira um commit. O git guarda, assim, uma cópia de cada versão dos arquivos, inclusive das fotos antigas do `acervo.csv`; é uma cópia de segurança e um registro para auditoria, mas o site não depende dela, porque o histórico que ele usa já está no `historico.csv`.

3. **O gerador do painel** (pasta [`painel/`](painel/)) prepara os dados para o site. Os CSVs são bons para guardar, mas grandes e espalhados demais para um site carregar. Depois de cada coleta, o comando `python -m painel` lê todos eles, faz as contas (quantas matérias havia em cada dia, medianas, funis...) e grava arquivos JSON enxutos em `site/dados/`.

4. **O site** (pasta [`site/`](site/)) é estático: só HTML, CSS e JavaScript, sem servidor nem banco de dados, hospedado de graça no GitHub Pages. Quando você abre o endereço, o navegador baixa os JSONs e desenha os gráficos ali mesmo, com [Observable Plot](https://observablehq.com/plot/). Por isso os filtros respondem na hora: os dados já estão todos no seu navegador.

### De onde vêm os dados

A foto do relatório não conta tudo. Ela mostra que uma matéria sumiu do acervo, mas não diz para onde ela foi; e mostra o último passo interno de cada matéria, mas não os que vieram antes. Por isso o coletor consulta três fontes do SPLEGIS:

| Fonte                                                                                                                                       | O que traz                                                                                                                                           | Para que serve                                                                                                       |
| ------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| O relatório [Projetos em Análise nas Comissões](https://splegisconsulta.saopaulo.sp.leg.br/Relatorio/IndexComissaoProjetoTramitacaoInterna) | Cada matéria em cada comissão hoje: relator, datas de envio e de recebimento, último passo interno.                                                  | A foto do dia.                                                                                                       |
| O feed diário de eventos ([`MateriasEventos`](https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx), no webservice do SPLEGIS)                  | Tudo o que tramitou num dia: envios de uma área para outra, recebimentos, passos internos, com o motivo.                                             | Saber o que aconteceu entre uma foto e outra (quando, para onde e por que uma matéria saiu) e reconstruir o passado. |
| Outras consultas do [mesmo webservice](https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx)                                                    | Relatores e pareceres, autores, vetos e desfecho de cada projeto desde 2013, mais as filiações partidárias dos vereadores e os cargos nas comissões. | Os gráficos de pareceres, prazos, desfechos, funil, presidentes e partidos.                                          |

### Como os dados ficam guardados

A cada coleta, o coletor atualiza vários arquivos em [`dados/`](dados/). Eles se comportam de jeitos diferentes: um é trocado a cada coleta, os outros só acumulam.

**[`acervo.csv`](dados/acervo.csv): a foto do último dia.** Uma linha por matéria em cada comissão, com o que o relatório mostra dela. É o único arquivo que a coleta substitui por inteiro: ele sempre mostra o acervo do último dia, e o de ontem só fica no histórico do git.

**[`historico.csv`](dados/historico.csv): todas as fotos, sem repetição.** Guardar uma foto inteira por dia repetiria quase tudo: das cerca de 4 mil matérias do acervo, a maioria passa dias ou meses sem mudar nada. Por isso o histórico guarda cada estado uma vez só, com o período em que valeu. Cada linha diz "a matéria X esteve na comissão Y, neste estado, da data `desde` até a data `ate`". O estado inclui o relator, as datas de envio e de recebimento e o último passo interno. Enquanto nada muda, a linha fica aberta, com `ate` vazio, e a coleta não mexe nela. Quando algo muda, a linha recebe o `ate` (o último dia em que aquele estado foi visto) e, se a matéria continua na comissão, uma linha nova é aberta.

Um exemplo inventado, com só algumas colunas. O PL 123/2026 chega à CCJ em 05/10. Na coleta de 07/10, o histórico tem uma linha aberta para ele:

| comissao | rotulo      | desde      | ate | relator | passo interno    |
| -------- | ----------- | ---------- | --- | ------- | ---------------- |
| CCJ      | PL 123/2026 | 2026-10-05 |     |         | Designar Relator |

Em 09/10, a CCJ designa o relator. A coleta desse dia fecha a primeira linha em 08/10, o último dia em que o projeto foi visto sem relator, e abre outra:

| comissao | rotulo      | desde      | ate        | relator          | passo interno                       |
| -------- | ----------- | ---------- | ---------- | ---------------- | ----------------------------------- |
| CCJ      | PL 123/2026 | 2026-10-05 | 2026-10-08 |                  | Designar Relator                    |
| CCJ      | PL 123/2026 | 2026-10-09 |            | Ver. FULANO (PT) | Estudo para manifestação do relator |

Em 20/10, a CCJ dá o parecer e envia o projeto à Comissão de Finanças. Na coleta desse dia ele já não está no acervo da CCJ: a segunda linha é fechada em 19/10, e uma linha nova é aberta para a FIN:

| comissao | rotulo      | desde      | ate        | relator          | passo interno                       |
| -------- | ----------- | ---------- | ---------- | ---------------- | ----------------------------------- |
| CCJ      | PL 123/2026 | 2026-10-05 | 2026-10-08 |                  | Designar Relator                    |
| CCJ      | PL 123/2026 | 2026-10-09 | 2026-10-19 | Ver. FULANO (PT) | Estudo para manifestação do relator |
| FIN      | PL 123/2026 | 2026-10-20 |            |                  |                                     |

Com isso, dá para remontar a foto de qualquer dia já coletado: o acervo do dia `d` são as linhas com `desde` até `d` e com `ate` vazio ou a partir de `d`. Em 15/10, por exemplo, o PL 123/2026 estava na CCJ, com relator. Um projeto que passa um ano parado ocupa uma linha só. É deste arquivo que sai toda a série histórica do painel.

**Os arquivos que só acrescentam.** Os demais guardam informações que a foto não traz e nunca apagam o que já têm:

- [`coletas.csv`](dados/coletas.csv) é o registro das coletas: o dia a que cada uma se refere, a hora exata em que foi feita e quantas matérias cada comissão tinha. Diz quais dias têm foto, e a hora serve para contar os dias de cada matéria como o SPLEGIS conta.
- [`materias.csv`](dados/materias.csv) é o catálogo de toda matéria já vista: rótulo, tipo, número, ano e ementa. A ementa fica aqui, uma vez só, e não em cada linha do histórico. Quando a matéria sai das comissões, continua no catálogo.
- [`autorias.csv`](dados/autorias.csv) traz os autores de cada matéria do catálogo.
- [`tramitacoes.csv`](dados/tramitacoes.csv) e [`passos_internos.csv`](dados/passos_internos.csv) são os eventos do feed diário. O primeiro guarda cada envio de uma área para outra que entra ou sai de uma comissão, com o motivo (é por ele que se sabe para onde e por que uma matéria saiu). O segundo guarda cada passo interno dado nas comissões, inclusive os que aconteceram entre uma coleta e outra e que a foto não chega a mostrar. A cada coleta, entram os eventos do dia que ainda não estavam lá.

**Os arquivos que são baixados de novo toda noite.** Os das outras consultas do webservice (relatores e pareceres, autores, vetos, desfechos, vereadores, cargos e áreas) funcionam de outro jeito. Um projeto de anos atrás ainda pode ganhar um parecer ou ser encerrado, então a coleta da noite baixa de novo os projetos dos últimos oito anos e substitui o que havia sobre eles.

Todos os arquivos e colunas estão descritos em [Os dados](#os-dados).

### E o passado?

A coleta diária começou em 02/10/2026. Para não esperar anos até a série ter profundidade, a pasta [`reconstrucao/`](reconstrucao/) refaz o acervo de cada dia desde novembro de 2018 a partir do feed de eventos: se o feed diz que uma matéria foi enviada à CCJ em 10/03/2019 e saiu de lá em 02/05/2019, ela esteve no acervo da CCJ nesse intervalo. O resultado foi ancorado na primeira foto real e conferido contra o histórico oficial das matérias. O painel junta as duas séries: a reconstruída até a véspera da primeira coleta e a das fotos reais dali em diante. Os detalhes estão em [Série reconstruída](#série-reconstruída-nov2018-a-out2026).

### Um dia do projeto

1. **10h07.** O GitHub liga uma máquina, roda os testes e, se passarem, coleta o relatório, baixa os eventos do dia e grava tudo num commit.
2. **Logo depois.** O commit dispara o segundo workflow, [`painel.yml`](.github/workflows/painel.yml), que roda o gerador do painel e publica o site. Em poucos minutos, o site mostra a foto nova.
3. **15h07.** Nova coleta. Ela substitui a das 10h07: fica valendo uma foto por dia, a mais recente.
4. **21h47.** A coleta da noite fecha a foto do dia. É também a única que atualiza relatores, pareceres, autores, vetos e desfechos, que são consultas mais demoradas, de alguns minutos.
5. **23h47.** Repescagem: só coleta se o dia ainda estiver sem foto.

O agendamento do GitHub às vezes atrasa horas (já atrasou seis). Por isso, uma coleta feita até as 9h vale para o dia anterior, cujo fim ela retrata.

### Cuidados para não gravar dado errado

- **Testes antes de coletar.** Se algum teste falha, a coleta não acontece, e o site continua mostrando a última foto boa.
- **Resposta incompleta não entra.** Se alguma comissão falhar na consulta, nada é gravado. Se o acervo de uma comissão cair mais de 50% de um dia para o outro, a coleta também é barrada, porque isso costuma ser resposta incompleta do SPLEGIS e seria registrado como uma saída em massa de matérias.
- **Coletar de novo não duplica.** Uma segunda coleta no mesmo dia substitui a primeira.
- **Sem dependências.** O coletor e o gerador do painel usam só a biblioteca padrão do Python; não há nada para instalar.

### Onde está cada coisa

| Pasta                                      | O que tem                                                                                                                                   |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| [`coletor/`](coletor/)                     | O coletor: `coletar.py` (a foto do relatório), `tramitacoes.py` (os eventos do dia) e `legislativo.py` (as demais consultas ao webservice). |
| [`dados/`](dados/)                         | Os CSVs, que são o produto principal do projeto. Estão descritos em [Os dados](#os-dados).                                                  |
| [`reconstrucao/`](reconstrucao/)           | O programa que reconstrói o acervo desde 2018; o resultado fica em [`dados/reconstrucao/`](dados/reconstrucao/).                            |
| [`painel/`](painel/)                       | O gerador dos JSONs do site.                                                                                                                |
| [`site/`](site/)                           | O site: `index.html` (a estrutura da página), `app.js` (os gráficos e os filtros), `trajetorias.js` (a aba Trajetórias), `xlsx.js` (o relatório consolidado em Excel) e `estilo.css`.                                           |
| [`tests/`](tests/)                         | Os testes automáticos.                                                                                                                      |
| [`.github/workflows/`](.github/workflows/) | Os dois agendamentos: `coleta.yml` e `painel.yml`.                                                                                          |

## Os dados

Todos os arquivos estão em UTF-8, separados por vírgula. As datas seguem o formato ISO 8601 (`2026-08-24T15:43:00`), no horário de Brasília.

| Arquivo                                                    | Conteúdo                                                                                                                                                            |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`dados/acervo.csv`](dados/acervo.csv)                     | Retrato do dia: uma linha por comissão × matéria. O histórico do git guarda os retratos anteriores.                                                                 |
| [`dados/historico.csv`](dados/historico.csv)               | Os mesmos estados em intervalos de validade (`desde`/`ate`). É o arquivo para a série histórica.                                                                    |
| [`dados/materias.csv`](dados/materias.csv)                 | Catálogo cumulativo de toda matéria já vista: rótulo, tipo, número, ano e ementa.                                                                                   |
| [`dados/autorias.csv`](dados/autorias.csv)                 | Autores de cada matéria.                                                                                                                                            |
| [`dados/coletas.csv`](dados/coletas.csv)                   | Data, hora e tamanho do acervo de cada comissão em cada coleta.                                                                                                     |
| [`dados/tramitacoes.csv`](dados/tramitacoes.csv)           | Envios de e para as comissões registrados no feed do SPLEGIS desde o início da coleta diária, com o motivo.                                                         |
| [`dados/passos_internos.csv`](dados/passos_internos.csv)   | Passos da tramitação interna nas comissões registrados no feed desde o início da coleta diária.                                                                     |
| [`dados/relatorias.csv`](dados/relatorias.csv)             | Relator, parecer e conclusão de cada projeto (PL, PDL, PR, PLO) apresentado desde 2013 em cada comissão permanente, por despacho.                                   |
| [`dados/encerrados.csv`](dados/encerrados.csv)             | Como terminou cada projeto encerrado desde 2013: promulgado, vetado, retirado, arquivado etc.                                                                       |
| [`dados/eventos.csv`](dados/eventos.csv)                   | Eventos marcados nos gráficos de tempo (como a pandemia): `data`, `texto` curto do marco e `descricao`. Editado à mão.                                              |
| [`dados/areas.csv`](dados/areas.csv)                       | Nome de cada área de tramitação do SPLEGIS (`SGP21` = Equipe de Apoio ao Plenário etc.).                                                                            |
| [`dados/autores.csv`](dados/autores.csv)                   | Autores de cada projeto apresentado desde 2013, na ordem, com a data de leitura. Dá a autoria (vereadores, Executivo, Mesa) e o partido do primeiro autor.          |
| [`dados/vetos.csv`](dados/vetos.csv)                       | Projetos apresentados desde 2013 que foram vetados, total ou parcialmente. O veto aparece aqui assim que é dado; em `encerrados.csv`, só quando a Câmara o aprecia. |
| [`dados/filiacoes.csv`](dados/filiacoes.csv)               | Partidos de cada vereador, com as datas de filiação. Dá o partido do relator na data do parecer.                                                                    |
| [`dados/cargos_comissoes.csv`](dados/cargos_comissoes.csv) | Presidentes, vices e membros das 7 comissões permanentes, com as datas.                                                                                             |

### `acervo.csv` e `historico.csv`

| Coluna                                                               | Descrição                                                                                                                                                                            |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `comissao`                                                           | Sigla da comissão: `ADM`, `CCJ`, `ECON`, `EDUC`, `FIN`, `SAUDE` ou `URB`.                                                                                                            |
| `materia_id`                                                         | Identificador da matéria no SPLEGIS. Liga com `materias.csv` e `autorias.csv`.                                                                                                       |
| `desde`, `ate`                                                       | Só no histórico. Primeira e última data de coleta em que a matéria foi vista nesse estado, nessa comissão. `ate` vazio significa que o estado continuava vigente na última coleta.   |
| `rotulo`                                                             | Tipo, número e ano, como `PL 502/2026`.                                                                                                                                              |
| `relator_codigo`, `relator`                                          | Relator designado; vazio significa sem relator. O código é o mesmo usado para autores em `autorias.csv`.                                                                             |
| `enviado_por`, `enviado_em`                                          | Área de origem e data do envio da matéria à comissão (tramitação externa).                                                                                                           |
| `recebido_em`                                                        | Data do recebimento pela comissão. Vazio significa envio ainda pendente de recebimento.                                                                                              |
| `interna_data`, `interna_area`, `interna_tipo`, `interna_comentario` | Última tramitação interna na comissão, como `Relator(a)` / `Estudo para manifestação do relator`.                                                                                    |
| `ultima_interna`                                                     | Resumo textual da última tramitação interna, como o SPLEGIS o exibe. Só vem preenchido quando os campos `interna_*` estão vazios, porque nos demais casos repete a mesma informação. |

Uma mudança em qualquer coluna de estado (relator, tramitação etc.) fecha o intervalo anterior e abre um novo. O acervo de qualquer data coletada `d` é o conjunto das linhas com `desde <= d` e (`ate` vazio ou `d <= ate`). Por exemplo, com [DuckDB](https://duckdb.org/):

```sql
SELECT comissao, count(*) AS materias
FROM read_csv('dados/historico.csv', types = {'desde': 'DATE', 'ate': 'DATE'})
WHERE desde <= DATE '2026-10-15' AND (ate IS NULL OR ate >= DATE '2026-10-15')
GROUP BY comissao
ORDER BY comissao;
```

As contagens de dias não são gravadas, porque mudariam todo dia em toda linha. Para reproduzir os números do SPLEGIS, conte os períodos completos de 24 horas entre `recebido_em` (dias na comissão) ou `interna_data` (dias no estado atual) e o `coletado_em` da coleta, em `coletas.csv`.

O relatório traz todos os tipos de matéria: `PL`, `PDL`, `PR`, `PLO`, `DOCREC` (documentos recebidos), `RDP`, `REC` e outros. Para olhar só os projetos, filtre pelo `tipo` em `materias.csv`.

### `materias.csv`, `autorias.csv`, `coletas.csv`, `tramitacoes.csv` e `passos_internos.csv`

- `materias.csv`: `materia_id`, `rotulo`, `tipo`, `numero`, `ano`, `ementa`. Matérias que saem das comissões continuam no catálogo, com a última versão vista.
- `autorias.csv`: `materia_id`, `ordem`, `autor_codigo`, `autor`, `classe` (`Vereador`, `Remetente` ou `Promovente`).
- `coletas.csv`: `data`, `coletado_em` (com fuso), `comissao`, `materias` (tamanho do acervo naquela coleta).
- `tramitacoes.csv`: `data`, `rotulo`, `tipo` (`envio`, ou `excl_envio` quando o envio foi desfeito), `de` e `para` (áreas, como `CCJ` ou `SGP21`) e `motivo`, como o feed o registra (`Motivo: A pedido. Obs: Aprovado em Reunião Conjunta.`). Só os envios que saem de uma comissão ou chegam a ela, das matérias que o relatório lista.
- `passos_internos.csv`: `data`, `rotulo`, `tipo` (`interna`, ou `excl_interna` quando o passo foi excluído), `comissao`, `area`, `passo` e `comentario`, como `Relator(a)` / `Estudo para manifestação do relator`. Só os passos nas 7 comissões.
- Os dois arquivos só acrescentam: cada coleta baixa o feed do dia de referência e do anterior e junta o que faltava. `python -m coletor.tramitacoes --desde AAAA-MM-DD` preenche lacunas.

### `relatorias.csv`, `encerrados.csv`, `areas.csv`, `autores.csv`, `vetos.csv`, `filiacoes.csv` e `cargos_comissoes.csv`

Vêm do [webservice do SPLEGIS](https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx) (operações `ProjetosReunioesDeComissao`, `ProjetosEncerrados`, `AreasDeTramitacao`, `ProjetosAutores`, `ProjetosVetadosPorPromovente` e `VereadoresCMSP`), por `python -m coletor.legislativo`, uma vez por dia, para os projetos dos últimos oito anos; `--desde 2013` refaz tudo.

- `relatorias.csv`: `rotulo`, `comissao`, `despacho` (número do despacho que mandou o projeto às comissões) e `despachado_em`, `relator` e `partido` (o que o SPLEGIS registra hoje para o vereador, que pode não ser o da época; o painel usa o da data do parecer, por `filiacoes.csv`), `parecer` (número/ano), `parecer_em` e `conclusao` (como `FAVORÁVEL`, `LEGALIDADE COM SUBSTITUTIVO`, `CONTRÁRIO`). Não traz a data da designação do relator.
- `encerrados.csv`: `rotulo`, `tipo`, `ano`, `leitura`, `encerramento` e `motivo` (`Encerrado-PROMULGADO`, `Encerrado-VETO TOTAL ACEITO`, `Encerrado-TERMINO DE LEGISLATURA (ART. 275 REG. INT.)` etc.).
- `areas.csv`: `sigla`, `nome`.
- `autores.csv`: `rotulo`, `leitura`, `ordem` (1 = primeiro autor), `autor_codigo` e `autor`. Os prefeitos são reconhecidos pelo código de autor, como na composição do acervo. Como lista todos os projetos, dá também a contagem de projetos apresentados por ano.
- `vetos.csv`: `rotulo` e `veto` (`Veto Total` ou `Veto Parcial`). A consulta é por autor; vêm os vetos dos projetos de todos os autores de `autores.csv`. Os vetos totais de 2013 a 2022 só foram encerrados no SPLEGIS em dois lotes, em 2019 e em 2025, quando a Câmara os apreciou.
- `filiacoes.csv`: `vereador`, `partido`, `inicio`, `fim`. Inclui os vereadores de legislaturas anteriores.
- `cargos_comissoes.csv`: `comissao`, `cargo` (`Presidente`, `Vice-presidente`, `Membro`...), `vereador`, `inicio`, `fim`. As comissões extraordinárias ficam de fora.

## Série reconstruída (nov/2018 a out/2026)

Para que a série não precise de anos para ganhar profundidade, [`dados/reconstrucao/`](dados/reconstrucao/) traz o acervo de cada dia desde novembro de 2018. Ele foi reconstruído a partir dos eventos de tramitação que o SPLEGIS publica dia a dia e ancorado no primeiro retrato real. A reconstrução não sabe, dia a dia, quais matérias estavam sem relator: o webservice diz quem foi o relator de cada projeto em cada comissão desde 2013 ([`dados/relatorias.csv`](dados/relatorias.csv)), mas não em que data ele foi designado. Por isso a série estima as matérias sem relator pelo passo interno vigente, e o número exato só existe a partir da coleta diária. O que não pôde ser recuperado aparece como `?`. Método, arquivos e validação estão em [`dados/reconstrucao/README.md`](dados/reconstrucao/README.md).

## Rodar localmente

Requer Python 3.10 ou mais recente. O GitHub Actions usa o 3.12; antes de subir uma mudança, vale rodar os testes nessa versão, porque um teste que falha lá impede a coleta.

```sh
python -m coletor.coletar              # coleta e grava em dados/
python -m coletor.coletar --se-faltar  # só coleta se hoje ainda não tiver coleta
python -m coletor.coletar --forcar     # ignora a trava contra queda brusca do acervo
python -m coletor.tramitacoes          # envios do dia de referência e do anterior, do feed
python -m coletor.legislativo          # relatorias, autores, vetos e desfechos (últimos 8 anos)
python -m unittest                     # testes

python -m reconstrucao baixar --inicio 2018-10-26 --fim 2026-10-02  # feed de eventos (cache)
python -m reconstrucao gerar                                        # refaz dados/reconstrucao/

python -m painel                    # gera site/dados/ a partir de dados/
python -m http.server -d site 8000  # abre o painel em http://localhost:8000
```

## O painel

O painel ([`site/`](site/)) tem quatro abas. A última, **Metodologia e dados**, explica como cada número é calculado, de onde vêm os dados e onde baixá-los.

O **Retrato do dia** traz o acervo atual:

- os indicadores do relatório: acervo ativo, relatores, sem relator, mais de 180 e de 365 dias, mediana;
- as distribuições por relator e por estado da tramitação;
- a pesquisa por autor ou partido, com seleção múltipla;
- a lista das matérias de cada recorte, com links para o SPLEGIS e exportação em CSV, Excel e PDF;
- o relatório consolidado em XLSX, com uma aba por comissão.

A **Evolução** traz as séries desde novembro de 2018 (algumas desde 2013), com um resumo da última semana no topo e os gráficos em quatro seções:

- **Tamanho e movimento:** tamanho do acervo, o mesmo por comissão, crescimento comparado (base 100), entradas e saídas por mês, por que as matérias saem e as rotas entre as comissões.
- **Composição e tempo:** composição do acervo por legislatura, tipo e autoria; idade e tempo sem movimentação; idade mediana; e a curva de permanência, que mostra quanto tempo as matérias ficam na comissão (estimador de Kaplan-Meier), por comissão ou por autoria.
- **Tramitação interna:** em que ponto da tramitação estão (área ou etapa), as matérias sem relator, o tempo de cada etapa e um calendário diário de votações e passos internos.
- **Votações e resultados:** votações e pareceres por mês, quanto demora o parecer, quem relata, quem presidiu as comissões, os partidos nas comissões, como terminam os projetos, o funil de até onde eles chegam e a matriz de onde cada grupo de projetos trava.

As **Trajetórias** mostram o caminho de cada projeto (PL, PDL, PR e PLO) que passou pelas comissões desde outubro de 2018, cerca de 10 mil, cada um como uma linha que atravessa faixas: as comissões, as áreas para onde foi enviado fora delas (SGP12, SGP21, SGP23, Arquivo) e o desfecho. A cor pode mostrar o desfecho, o ano de apresentação, o tipo ou a fase dentro da comissão (sem relator, estudo, diligência, em pauta, votado). Ao lado, um mapa de transições mostra quantos projetos fizeram cada envio de uma faixa para outra; clicar num arco filtra as linhas. As linhas são desenhadas em WebGL, e os dados vêm de `site/dados/trajetorias.json`, gerado por [`painel/trajetorias.py`](painel/trajetorias.py).

Os filtros de comissão, de matérias (só projetos ou todas) e de período, inclusive com datas escolhidas, valem para quase todos os gráficos; cada cartão diz quando não valem. A maioria dos gráficos pode ser vista como tabela e baixada em CSV ou como imagem.

O site é publicado no GitHub Pages pelo workflow [`painel.yml`](.github/workflows/painel.yml), a cada push e depois de cada coleta. Usa [Observable Plot](https://observablehq.com/plot/) e [D3](https://d3js.org/) (licença ISC), copiados em `site/vendor/`.

Se o SPLEGIS bloquear o acesso a partir do GitHub, o coletor respeita as variáveis de ambiente `HTTPS_PROXY`/`HTTP_PROXY`. Basta defini-las no workflow a partir de um secret.

## Licença

Código sob a [licença MIT](LICENSE). Os dados são públicos e vêm do SPLEGIS, da Câmara Municipal de São Paulo.
