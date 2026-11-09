# Portfólio — Catálogo de Projetos

Heriberto Márcio · Engenheiro de IA · catálogo e planejamento dos projetos.

**Estado em novembro de 2026:** os projetos 00 (chat), 01 (recomendador de filmes) e 02 (agente de planilhas) estão implementados e testados localmente, cada um em repositório próprio com Docker e CI/CD preparados; ainda não estão publicados numa VPS. Os demais projetos (03 a 16) estão **planejados e ainda não existem**.

## 1. Como o currículo orienta a escolha

Os projetos de cliente (Dhauz, Oi/NIO, TIM, Opty, DSS) são confidenciais. O portfólio serve para **provar publicamente** o que o currículo afirma, usando dados públicos ou sintéticos. Cada projeto abaixo está amarrado a uma linha do currículo:

| Afirmação do currículo | Projeto que a comprova |
|---|---|
| Agente ReAct + RAG + tools, POC → produção (DSS) | 00, 01, 02 |
| Planilha → Parquet → DuckDB → SQL pelo agente (DSS) | 02 |
| Langfuse + MLflow, observabilidade (DSS) | todos (camada compartilhada) + 11 |
| FastAPI, Docker, CI/CD, escalabilidade | todos |
| MongoDB, Redis, VectorDB, SQL | 08 (e uso real em 01, 05, 03) |
| Databricks/Airflow, pipelines em escala (Oi/NIO) | 06 |
| Churn e forecast: NeuralProphet, XGBoost (Oi, TIM) | 07 |
| Segmentação + dados públicos IBGE/SUS (Opty) | 06 |
| Visão computacional YOLO (logística) | 12 |
| NLP/embeddings + crawler (Job Hunter) | 01, 13 |
| TCC: biometria palmar, rede siamesa | 14 |
| Liderança técnica / ensino (FUNETEC) | documentação do site + tutoriais por projeto |

## 2. Visão geral

Legenda de esforço: **P** ≈ 1 semana · **M** ≈ 2–3 semanas · **G** ≈ 4+ semanas (ritmo de trabalho parcial).

| # | Projeto | Tipo | Esforço | Fase |
|---|---|---|---|---|
| 00 | Site do portfólio + **chat com o portfólio** (RAG sobre currículo e docs) | Chatbot | M | 1 |
| 01 | Recomendador de filmes por descrição | Chatbot + busca vetorial | M | 1 |
| 02 | Agente analista de planilhas | Chatbot + agente ReAct | M | 1 |
| 03 | OCR → Markdown | Pipeline de documentos | M | 2 |
| 04 | Gerador de apresentações `.pptx` | Agente + geração de arquivos | G | 2 |
| 05 | Narrador de RPG em texto | Chatbot interativo | M | 2 |
| 06 | Dados públicos: IBGE × SUS (ETL + dashboard + previsão de demanda) | Engenharia de dados + ML | G | 3 |
| 07 | Churn e forecast | ML | M | 3 |
| 08 | Laboratório de bancos de dados (SQL, Mongo, Redis, vetorial) | Backend/arquitetura | M | 3 |
| 09 | Radar de produtos para afiliados | Agente + coleta | G | 4 |
| 10 | Hobbies: MCP com Blender e Godot, conteúdo para redes/YouTube | Vitrine criativa | M | 4 |
| 11 | Laboratório de avaliação e observabilidade de LLMs | Transversal | M | 3 |
| 12 | Contagem de itens com YOLO | Visão computacional | P | 2 |
| 13 | Job Hunter público + adaptador de currículo | NLP + agente | M | 3 |
| 14 | Biometria palmar com rede siamesa | Deep learning (TCC) | M | 4 |
| 15 | Agente de voz | Chatbot multimodal | M | 4 |
| 16 | Chef & Treino IA (cozinha e academia) | Chatbot com tools | P | 4 |

Os itens 11–16 são sugestões minhas, além da sua lista.

## 3. Detalhamento

### 00 · Site do portfólio + chat com o portfólio
- **O que é:** site estático com home (quem sou e resumo do currículo), blog de estudos e portfólio com uma página de documentação por projeto (arquitetura, decisões, medições, links para demo e código), gerado de Markdown. Um chat flutuante responde perguntas sobre você e os projetos usando RAG sobre o currículo e as docs.
- **Por que primeiro:** é a porta de entrada, já é um chatbot em produção e valida toda a infraestrutura (proxy, HTTPS, streaming, rate limit, tracing) antes dos outros projetos.
- **Stack planejada:** HTML/CSS/JS estático (ou Astro/Next) · FastAPI · Qdrant/pgvector · Langfuse.
- **Estado:** implementado com site estático (nginx), API FastAPI com streaming, RAG com BM25 sobre Markdown (a escolha foi medida contra embeddings), Gemini Flash-Lite como modelo padrão, limites de uso e 25 testes. Avaliado com o Gemini Flash-Lite real em 16 casos (fatos, "não sei", estado dos projetos, injeção de prompt, fora do tema): 16 de 16 corretos. O chat grava traces opcionais no Langfuse (busca, geração, tokens, latência; dados pessoais mascarados) com 7 notas automáticas de guardrails (injeção de prompt, dado pessoal, link inventado, vazamento do prompt, lacuna de conhecimento) e o feedback "útil / não ajudou" do visitante; tudo implementado e testado com o SDK, e o envio foi confirmado contra um Langfuse 4.72.0 local (teste de fumaça: 3 observações e 8 notas chegaram). Banco vetorial no chat ficou como evolução futura.

### 01 · Recomendador de filmes por descrição
- **O que é:** o usuário descreve o que quer ver ("um filme de suspense psicológico tipo Ilha do Medo, mas mais leve") e recebe filmes com sinopse semelhante, com explicação do porquê.
- **Como:** embeddings multilíngues das sinopses (TMDB) → busca vetorial → busca híbrida (vetor + filtros de gênero/ano/nota) → LLM reordena e explica. Diálogo permite refinar ("menos violento", "mais recente").
- **Mostra:** VectorDB, embeddings, busca híbrida, avaliação de relevância (conjunto de consultas de teste com nDCG).
- **Atenção:** TMDB exige atribuição e tem termos de uso para o catálogo; confirmar antes de publicar.
- **Estado:** implementado com Qdrant, BM25 e RRF ponderado, agente com a ferramenta `search_movies` (testado com o Gemini Flash-Lite), catálogo de amostra de 44 filmes e avaliação da busca com 30 consultas e 3 embedders. O melhor desenho depende do embedder: com o embedder multilíngue do Google a busca só vetorial foi a melhor (nDCG@10 de 0,996, e 0,981 nas paráfrases) e misturar BM25 piorou (0,769 nas paráfrases); com o nomic-embed-text, mais fraco em português, a híbrida foi a melhor (0,943, contra 0,883 só vetorial). Por isso o peso do BM25 é configurável e definido por embedder.

### 02 · Agente analista de planilhas
- **O que é:** o usuário envia `.xlsx`/`.csv`; o agente entende o esquema, responde perguntas em linguagem natural, gera gráficos e escreve insights. Versão pública do que você fez na DSS.
- **Como:** upload → Parquet → DuckDB; agente ReAct com tools (`describe_schema`, `run_sql`, `plot`, `summarize`); SQL somente leitura, com timeout e limite de linhas; relatório final exportável.
- **Mostra:** agentes com tools, text-to-SQL seguro, guardrails, Langfuse.
- **Atenção:** apagar uploads automaticamente (LGPD) e limitar tamanho.
- **Estado:** implementado com upload (csv/xlsx), DuckDB travado, ferramentas `describe_table`, `run_sql` e `make_chart`, relatório em Markdown e 85 testes, incluindo tentativas de fuga do SQL. Avaliado com o Gemini Flash-Lite real: 23 de 24 perguntas numéricas corretas (a falha foi cota da API) e resistência à injeção de prompt numa célula; numa pergunta sem resposta possível o modelo inventou um número, o que levou a uma checagem de ancoragem que avisa números grandes que nenhuma consulta produziu.

### 03 · Conversor OCR → Markdown
- **O que é:** envia PDF/imagem digitalizada e recebe `.md` com títulos, listas e tabelas preservados.
- **Como:** pré-processamento (deskew, binarização) → motores comparados (Tesseract, PaddleOCR, Docling/Marker, LLM com visão) → pós-correção por LLM → `.md`. Fila assíncrona (Redis + worker) para lotes.
- **Diferencial:** uma página de **benchmark** comparando motores (CER/WER, tempo, custo) em documentos reais em português. Isso é o que separa um projeto de engenharia de uma demo.

### 04 · Gerador de apresentações `.pptx`
- **O que é:** anexa documentos → o sistema resume, sintetiza e gera `.pptx` **editável** (texto em placeholders reais, não imagem). Aceita template `.pptx` do usuário e imagens de referência; opção de gerar imagens com IA.
- **Como:** ingestão (PDF/DOCX/MD) → resumo hierárquico → outline estruturado (JSON schema) → mapeamento para os layouts do template → `python-pptx` → render de prévia para checagem visual.
- **Imagens:** provedor plugável (API online ou ComfyUI/Stable Diffusion local). Geração local exige GPU, que a VPS provavelmente não tem; rodar na sua máquina e deixar a VPS só com a opção online.
- **Mostra:** saída estruturada, geração de arquivos complexos, abstração de provedores.

### 05 · Narrador de RPG em texto
- **O que é:** a IA conduz uma história, oferece 3–4 escolhas a cada cena e, no fim, exporta a aventura em PDF ou DOCX, com ou sem ilustrações.
- **Como:** estado do jogo explícito (personagem, inventário, flags, resumo da trama) em Redis; histórico completo em MongoDB; memória de longo prazo para manter coerência; escolhas retornadas como JSON; exportação com templates e imagens opcionais.
- **Mostra:** gerenciamento de estado/memória em chatbots, saída estruturada, streaming, exportação de documentos.

### 06 · Dados públicos: IBGE × SUS
- **O que é:** pipeline completo de dados públicos com dashboard interativo e previsão. Ideia central sua, que mantenho: usar projeções demográficas do IBGE para prever a demanda de uma subcategoria do SUS (por exemplo, internações por capítulo do CID, por UF/município).
- **Como:** coleta (API SIDRA/IBGE, microdados DATASUS, opcionalmente ENEM/INEP) → camadas bronze/prata/ouro com Airflow + DuckDB/Parquet (ou Databricks Free Edition, se quiser manter o termo do currículo) → análise descritiva → forecast com backtesting → dashboard em HTML/JS/CSS (ECharts ou Plotly).
- **Mostra:** ETL, orquestração, qualidade de dados, modelagem preditiva, front-end de dashboard.
- **Extra:** um assistente em linguagem natural sobre os dados (reaproveita o 02).

### 07 · Churn e forecast
- **O que é:** duas partes: (a) predição de churn com dataset público (ex.: Telco) usando XGBoost + explicabilidade (SHAP) + análise de sobrevivência; (b) forecast de série temporal com NeuralProphet/XGBoost, comparando com baselines e fazendo backtesting.
- **Como:** experimentos no MLflow, modelo servido via FastAPI, página que simula "o que acontece se eu oferecer desconto a este cliente".
- **Mostra:** ciclo completo de ML (treino, registro, serving, monitoramento de drift).

### 08 · Laboratório de bancos de dados
- **O que é:** o mesmo domínio modelado em PostgreSQL (relacional), MongoDB (documentos), Redis (cache/filas) e banco vetorial (pgvector/Qdrant), com benchmark e quando usar cada um.
- **Como:** modelagem normalizada vs. documento, índices, planos de execução (`EXPLAIN`), migrações, particionamento, backup/restore, cache-aside com Redis, comparação de busca vetorial (HNSW) com métricas de recall/latência. Tudo reproduzível via Docker Compose.
- **Mostra:** a habilidade de arquitetura de banco que você quer destacar. Funciona melhor como um **documento + repositório + gráficos** do que como app.

### 09 · Radar de produtos para afiliados
- **O que é:** coleta os produtos mais vendidos em várias fontes, o agente sugere o que está em alta e dá insights de estratégia (nicho, preço, sazonalidade, comissão).
- **Como:** conectores por fonte (APIs oficiais e programas de afiliados), normalização para um esquema único, histórico em banco, agente de análise com tools.
- **Atenção:** é o projeto de maior risco. Scraping de marketplaces viola termos de uso em vários casos e quebra com frequência. Prefira APIs oficiais e de programas de afiliados (Mercado Livre, Awin, Hotmart, Lomadee, etc.; verificar o que cada uma expõe hoje). Amazon PA-API, por exemplo, exige vendas qualificadas. Deixar por último e começar com 2 fontes.

### 10 · Hobbies: MCP com Blender e Godot, conteúdo para redes
- **O que é:** demos de um agente controlando Blender e Godot via MCP para gerar modelos, cenas e pequenos jogos; fluxo de geração de conteúdo (roteiro → voz → legendas → vídeo/post) para redes e YouTube.
- **Como hospedar:** Blender e Godot rodam na sua máquina, não na VPS. No portfólio entram **vídeos, GIFs, repositório e o making-of**, com a galeria hospedada como site estático.
- **Mostra:** domínio de MCP (cliente e servidor) e criatividade.
### 11 · Laboratório de avaliação e observabilidade de LLMs *(sugestão)*
- **O que é:** o painel que mostra como você mede qualidade: conjunto de avaliação para RAG (fidelidade, relevância do contexto), LLM-as-judge, testes de regressão de prompts, tentativas de prompt injection e guardrails. Usa Langfuse (self-hosted) e MLflow.
- **Por que importa:** é o que vagas sênior de IA procuram e o que mais diferencia "fiz um chatbot" de "coloquei um agente em produção".

### 12 · Contagem de itens com YOLO *(sugestão)*
- Demo web: sobe a foto de uma caixa e recebe os itens contados, com as caixas delimitadoras. Treinar com dataset público similar. Pequeno, visual e recria o projeto da logística. YOLO roda bem em CPU para inferência pontual.

### 13 · Job Hunter público + adaptador de currículo *(sugestão)*
- Você já tem `buscar_vagas.py` em `Curriculo/busca_vagas`. Evolução: embeddings de vagas, ranking por aderência ao seu perfil e um agente que sugere ajustes no currículo para cada vaga. Recria o Job Hunter (crawler + NLP) e é útil para você de verdade.

### 14 · Biometria palmar com rede siamesa *(sugestão)*
- Recria o TCC como demo: compara duas imagens de palma e informa a similaridade. Usar apenas dataset público de impressão palmar (com licença que permita) e não aceitar dados biométricos reais de visitantes, por ser dado sensível pela LGPD.

### 15 · Agente de voz *(sugestão)*
- Fala → texto → agente → voz, com baixa latência (streaming). Pode ser a interface alternativa do 00 ou do 05. Mostra multimodalidade e engenharia de latência.

### 16 · Chef & Treino IA *(sugestão, ligada aos seus hobbies)*
- Receitas a partir do que há na geladeira, ajustadas a macros e objetivos de treino, com tools de cálculo nutricional. Pequeno, simpático e humaniza o portfólio.

## 4. Arquitetura comum (o que torna tudo isso viável numa VPS)

```
Portfolio/
├─ build.py, content/, templates/, assets/ ← site na raiz (projeto 00)
├─ PROJETOS.md                 ← este catálogo
├─ _infra/                     ← docker-compose, proxy reverso, CI, scripts de deploy
├─ _core/                      ← biblioteca compartilhada (ver abaixo)
├─ 01-recomendador-filmes/     ← cada projeto: README, src/, Dockerfile, docs/, tests/
├─ 02-agente-planilhas/
└─ ...
```

**Camada compartilhada (`_core`)** para não reescrever em cada chatbot:
- abstração de provedor de LLM (trocar API por modelo local sem mexer no app);
- streaming (SSE), sessão e histórico;
- tracing com Langfuse, métricas e logs;
- rate limit por IP e **teto de gasto** por dia/projeto;
- componente de chat em JS reutilizável.

**Infra recomendada:**
- Proxy reverso com HTTPS automático (Caddy ou Traefik), um subdomínio por projeto (`filmes.seudominio.com`) ou um caminho por projeto. Subdomínios isolam melhor.
- Docker Compose por projeto, redes separadas, serviços compartilhados (Postgres, Redis, Qdrant, Langfuse) em um compose de infraestrutura.
- CI/CD com GitHub Actions: build, teste, deploy por SSH.
- Dimensionamento: vários containers + banco vetorial + Langfuse pedem folga de memória; um plano de 8 GB de RAM é um ponto de partida realista, mas vale conferir os planos atuais da Hostinger antes de decidir.

**Riscos para tratar desde o início:**
1. **Custo de API:** demo pública com LLM pode gerar conta alta. Limite diário, cache de respostas, modelo barato por padrão e chave com limite de gasto no provedor.
2. **Abuso e prompt injection:** validar entradas, sandbox em tudo que executa código/SQL, ferramentas de leitura apenas.
3. **LGPD:** uploads apagados automaticamente, sem login nem dados pessoais, aviso claro na tela.
4. **Sem GPU na VPS:** modelos locais pesados (geração de imagem, LLM grande) rodam na sua máquina; a VPS usa APIs.
5. **Estabilidade das demos:** healthcheck e uma versão "gravada" (vídeo/GIF) de cada projeto para o caso da demo cair.

## 5. Ordem sugerida

1. **Fase 1 — vitrine (00, 01, 02):** infra, site, três chatbots/agentes que já cobrem RAG, vetor, ReAct, FastAPI e observabilidade.
2. **Fase 2 — documentos e criatividade (03, 04, 05, 12):** projetos mais visuais e com arquivos de saída.
3. **Fase 3 — dados e ML (06, 07, 08, 11, 13):** profundidade em engenharia de dados, ML e arquitetura de banco.
4. **Fase 4 — extras e hobbies (09, 10, 14, 15, 16):** o que é mais arriscado ou mais pessoal.

Padrão por projeto: README com problema, arquitetura (diagrama), decisões e trade-offs, como rodar, resultados medidos e limitações. A documentação é o que o recrutador lê.

## 6. Decisões em aberto

- Já tem domínio? (define subdomínios e HTTPS.)
- Qual provedor de LLM e qual orçamento mensal para as demos? (Anthropic, OpenAI, ou modelos abertos via API.)
- Qual plano da VPS você já contratou ou pretende contratar?
- O código ficará em GitHub público? (recomendado; o `hmarcio2` já existe.)
- Idioma do site: só português, ou português e inglês? (as vagas internacionais do seu currículo sugerem bilíngue.)
