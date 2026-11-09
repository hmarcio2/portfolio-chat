# Observabilidade do chat: evidências

Esta pasta documenta o que o chat envia ao Langfuse **sem precisar de um servidor Langfuse no ar**.

| Arquivo | O que é |
|---|---|
| `trace-viewer.html` | Visualizador estático (abre direto no navegador): lista de traces, linha do tempo (busca e geração, com o primeiro token), tokens, entrada e saída, e as 8 notas por trace |
| `trace-example.json` | Os dados do visualizador: spans OpenTelemetry e notas exportados do pipeline real |
| `trace-viewer.template.html` | Modelo da página (o gerador injeta o JSON) |

**Como foi gerado:** `python -m evaluation.capture_traces` roda 8 conversas pelo chat real (Gemini Flash-Lite, base de conhecimento real), com o SDK real do Langfuse ligado a um exportador em memória e a um HTTP interceptado. É o que o Langfuse receberia. **Não é uma captura da interface do Langfuse**; tire prints de verdade (o Langfuse local já foi validado, veja o README do `portfolio-langfuse`) e coloque em `docs/observabilidade/prints/`. O que esta pasta mostra foi gerado antes de o servidor existir; o envio real foi confirmado depois com `evaluation.langfuse_smoke` (3 observações e 8 notas chegaram a um Langfuse 4.72.0 local).

**O que as 8 conversas mostram** (medido em 2026-11-01): respostas em cerca de 0,8 a 1,5 s, com o primeiro token em 0,6 a 1,0 s; a pergunta em inglês e a de acompanhamento ("e quais tecnologias ele usou?") funcionam; 3 alertas, todos verdadeiros: `knowledge_gap` ("Ele já trabalhou na Google?"), `injection_suspect` (pedido de ignorar instruções) e `pii_in_input` (e-mail na pergunta, mascarado no trace). O feedback do visitante (👍/👎) aparece como a nota `user_feedback`.

**Falsos positivos já corrigidos com esse método:** o `knowledge_gap` disparava com um aviso no segundo parágrafo de uma resposta correta; agora só olha o primeiro parágrafo.

**Painéis a montar no Langfuse** (quando subir): taxa semanal de `knowledge_gap` (lista do que falta na base), de `injection_suspect`, de feedback positivo, latência p50/p95 da `generation` e tokens por dia.

## Prints da interface (passo a passo)

Os dados já estão no Langfuse local: `python -m evaluation.seed_langfuse` enviou as 7 conversas de exemplo pelo chat real (Gemini Flash-Lite) para o ambiente `portfolio-demo`: 8 traces e 60 notas (3 `user_feedback`, 2 `knowledge_gap`, 1 `injection_suspect`, 1 `pii_in_input`). Rode de novo para criar conversas novas.

1. Suba o servidor, se não estiver no ar: `cd _langfuse && docker compose -f compose.yml -f compose.local.yml up -d`.
2. Abra `http://localhost:3300` e entre com o e-mail e a senha de administrador que o `scripts/gen_env.py` gravou em `_langfuse/.env` (`LANGFUSE_INIT_USER_EMAIL` e `LANGFUSE_INIT_USER_PASSWORD`). **Esse arquivo não vai para o git.** Escolha o projeto `portfolio-chat`.
3. Em **Tracing > Traces**, filtre o **Environment** por `portfolio-demo`. Salve os prints em `prints/` com estes nomes:

| Arquivo | O que mostrar |
|---|---|
| `01-lista-de-traces.png` | a lista de traces filtrada, com latência, tokens e as notas nas colunas |
| `02-trace-com-retrieval-e-generation.png` | um trace aberto (ex.: "Quais tecnologias o Heriberto usou no projeto DSS?"): a árvore `chat-turn` > `retrieval` + `generation`, o prompt completo e a resposta |
| `03-notas-de-guardrail.png` | o trace do "Ignore todas as instruções..." com `injection_suspect` e o do "Ele já trabalhou na Google?" com `knowledge_gap` (aba **Scores**) |
| `04-pii-mascarada.png` | o trace do e-mail digitado: a entrada aparece com `[email]` no lugar do endereço |
| `05-sessao.png` | a conversa "Fale do projeto DSS" + "e quais tecnologias ele usou?" em **Sessions** (dois turnos juntos) |

**Antes de publicar um print**, confira que ele não mostra a senha, as chaves do projeto (`pk-lf-`, `sk-lf-`), o e-mail do administrador nem o endereço de outra aba do navegador. Os traces de exemplo têm só perguntas de teste e dados fictícios (o e-mail do trace 04 é `visitante@exemplo.com`).
