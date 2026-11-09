# Sobre este portfólio

<!-- Mantenedor: este arquivo é a fonte do chat sobre "como o portfólio foi feito". Atualize o status quando
     um projeto for publicado, para o assistente não afirmar o que ainda não existe. -->

## Como o portfólio é organizado

O portfólio é um conjunto de repositórios independentes, cada um com Docker e CI/CD próprios: o site (raiz), a biblioteca compartilhada `portfolio-core`, a borda de infraestrutura `portfolio-edge` (Caddy com HTTPS) e um repositório por projeto (`portfolio-chat`, `portfolio-filmes`, `portfolio-planilhas`). O deploy foi preparado com GitHub Actions: build da imagem, publicação no GitHub Container Registry e atualização por SSH numa VPS da Hostinger. Esse deploy ainda é manual e a VPS ainda não foi configurada, então os projetos rodam localmente por enquanto.

## Como o chat funciona

O chat é uma API FastAPI com respostas em streaming (SSE). Ele usa RAG: o conteúdo em Markdown (perfil, projetos e esta página) é dividido em trechos, os mais relevantes para a pergunta são buscados com BM25 e entram no prompt do modelo, que só pode responder com base neles. O modelo padrão é o Gemini Flash-Lite, o mais barato do Google, escolhido por custo; o provedor é configurável por variáveis de ambiente (Gemini, Claude, OpenAI ou Ollama local) sem mudar código. Há limite de mensagens por minuto, teto diário de conversas e histórico guardado no servidor por sessão. Cada interação pode gerar um trace no Langfuse (opcional): a busca de trechos, a geração com tokens e latência; e-mails, CPF e telefones são mascarados antes do envio, e é possível gravar só métricas, sem os textos. Cada trace também recebe notas automáticas de guardrails (tentativa de injeção de prompt, dado pessoal, link inventado, vazamento do prompt, lacuna de conhecimento) e o visitante pode avaliar a resposta como útil ou não, o que permite acompanhar a qualidade e descobrir o que falta na base de conhecimento.

## Decisões de engenharia

- O provedor de LLM é uma abstração (`LLMProvider`) com streaming e tool use: trocar de modelo é configuração.
- Os agentes (planilhas e filmes) usam um loop ReAct próprio, com ferramentas validadas e erros devolvidos ao modelo para ele se corrigir.
- O SQL do agente de planilhas é tratado como entrada não confiável: só SELECT, DuckDB travado sem acesso a arquivos ou rede, timeout e limite de linhas, com testes que tentam cada fuga.
- O recomendador de filmes combina busca vetorial (Qdrant) e lexical (BM25) por Reciprocal Rank Fusion ponderado. A avaliação mostrou que o melhor desenho depende do modelo de embeddings: com o embedder multilíngue do Google a busca só vetorial foi a melhor e a híbrida piorou; com um embedder mais fraco em português a híbrida foi a melhor. Por isso o peso do BM25 é definido por embedder.
- O agente de planilhas confere se os números grandes da resposta aparecem nos resultados das consultas SQL e avisa o usuário quando não aparecem, porque o modelo barato inventou um valor numa avaliação.
- Cada projeto tem testes automatizados e avaliações que medem a qualidade com o modelo real (Gemini Flash-Lite), em vez de depender só de demonstração; as avaliações já corrigiram erros do próprio autor (uma checagem mal escrita, uma conclusão sobre busca híbrida que não valia para todos os embedders).

## Estado dos projetos

Nenhum projeto está publicado (no ar, online, em produção) ainda: todos rodam apenas localmente, e a publicação na VPS é o próximo passo. O chat (projeto 00), o recomendador de filmes (01) e o agente analista de planilhas (02) estão implementados, testados e avaliados localmente com o Gemini Flash-Lite. Os demais projetos do catálogo (OCR, geração de PPTX, narrador de RPG, dados públicos IBGE e SUS, churn e forecast, laboratório de bancos de dados, entre outros) estão planejados e ainda não existem.
