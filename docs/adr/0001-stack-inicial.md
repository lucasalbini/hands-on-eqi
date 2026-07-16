# ADR-0001: Stack Inicial do Analisador de Contratos

- **Status:** Aceito
- **Data:** 2026-07-16
- **Última atualização:** 2026-07-16 (criação)
- **Autor:** Lucas Albini

## 1. Contexto e Problema

Aplicação de análise de contratos: o usuário faz upload de um contrato (PDF/DOCX), o sistema extrai metadados estruturados via LLM, gera resumo executivo e análise qualitativa, e exibe tudo numa UI onde é possível revisar e corrigir os campos extraídos.

**Requisitos Funcionais:**
- RF01 — Upload de contratos em PDF e DOCX
- RF02 — Extração de metadados: tipo de contrato (enum), objeto, data de emissão, partes (prestadora/contratante: razão social, CNPJ, endereço, cidade, UF, representante e cargo)
- RF03 — Geração por IA de resumo executivo e análise qualitativa (riscos, obrigações, pontos de atenção)
- RF04 — UI para revisar e corrigir campos extraídos, preservando o valor original para auditoria
- RF05 — Validação determinística pós-LLM: CNPJ (dígitos verificadores), UF (27 siglas), data (parser BR)

**Requisitos Não-Funcionais:**
- RNF01 — A aplicação nunca chama a OpenRouter diretamente; a chave só existe no container do LiteLLM Proxy
- RNF02 — Informação ausente → `null`; o LLM não pode inventar nem inferir de conhecimento externo
- RNF03 — Texto do contrato é input não confiável (mitigação de prompt injection)
- RNF04 — Observabilidade de custo, latência e tokens por chamada LLM
- RNF05 — Setup completo com um comando (`docker compose up`)

## 2. Drivers de Decisão

1. **Simplicidade demonstrável** — é um hands-on de avaliação; cada peça deve ser justificável e inspecionável, sem infra especulativa
2. **Custo de LLM controlado** — extração literal não precisa de modelo caro; análise sim
3. **Auditabilidade** — todo output de LLM é candidato; original, normalizado e correção humana coexistem
4. **Segurança de credenciais** — blast radius da chave OpenRouter limitado a um container
5. **Trocabilidade de modelo** — mudar de modelo/provider sem tocar código de aplicação

## 3. Arquitetura Proposta

### 3.1 Visão Geral

```
                ┌──────────────┐   rewrite /api    ┌──────────────┐
   usuário ───► │   Next.js    │ ────────────────► │   FastAPI    │
                │  (frontend)  │                   │  (backend)   │
                └──────────────┘                   └──────┬───────┘
                                                          │
                                    ┌─────────────────────┼──────────────┐
                                    ▼                     ▼              ▼
                             ┌────────────┐        ┌────────────┐  ┌──────────┐
                             │  SQLite    │        │  LiteLLM   │  │ uploads  │
                             │ (aiosqlite)│        │   Proxy    │  │ (volume) │
                             └────────────┘        └─────┬──────┘  └──────────┘
                                                         │ OPENROUTER_API_KEY
                                                         ▼ (só aqui)
                                                   ┌────────────┐
                                                   │ OpenRouter │
                                                   └────────────┘
   Prometheus ◄── /metrics (backend) + /metrics (litellm) ──► Grafana
```

### 3.2 Conceitos centrais

- **Pipeline**: sequência parse → extract → analyze executada em background por contrato
- **Campo extraído**: unidade auditável com `llm_value` (bruto), `normalized_value` (pós-validação), `is_valid`/`validation_error` e `corrected_value` (humano)
- **Valor efetivo**: `corrected_value ?? normalized_value ?? llm_value (se válido)` — calculado na API, nunca materializado
- **Prompt versionado**: arquivo `*_vN.md`; a versão usada é gravada junto do resultado

### 3.3 Fluxo de Dados

1. `POST /api/v1/contracts` com `contrato.pdf` → `202 {"id": "3fa8...", "status": "processing"}`; pipeline agendado via BackgroundTasks
2. **parse**: pdfplumber extrai o texto → persistido em `contracts.raw_text`
3. **extract**: chamada 1 (modelo barato, `temperature=0`, structured output). Ex.: texto contém "CNPJ nº 12.345.678/0001-90" → `{"provider": {"cnpj": "12.345.678/0001-90", ...}}`
4. **validação determinística**: `validate_cnpj("12.345.678/0001-90")` → dígitos verificadores OK → `normalized_value="12.345.678/0001-90"`, `is_valid=true`. Se o LLM devolvesse "12.345.678/0001-99" → `is_valid=false`, `validation_error="dígito verificador inválido"` — persistido assim, nunca descartado
5. **analyze**: chamada 2 (modelo forte) com texto + metadados validados → `summary` + `ai_analysis` (JSON estruturado com riscos/obrigações/pontos de atenção) → contrato `completed`
6. UI faz polling em `/status`; ao completar, exibe campos com flags de validação. Usuário corrige um CNPJ inválido → `PATCH /fields` revalida deterministicamente → grava `corrected_value` mantendo `llm_value` original

## 4. Decisões Técnicas

### 4.1 Backend: FastAPI + SQLAlchemy 2.0 async + SQLite

- **Decisão:** FastAPI com SQLAlchemy 2.0 async sobre SQLite (aiosqlite), gerenciado com uv.
- **Justificativa:** stack async coerente ponta a ponta (driver 2); SQLite elimina um serviço de banco inteiro (driver 1) — o padrão de escrita é raro e single-writer.
- **Alternativas consideradas:**

| Opção | Prós | Contras |
|---|---|---|
| SQLite (aiosqlite) | zero infra, um volume, suficiente p/ escrita rara | sem concorrência de escrita real, sem rede |
| PostgreSQL | robusto, concorrente | +1 container, migrations, overkill p/ escopo |

- **Notas:** sem Alembic na v1 — `create_all` no lifespan; banco descartável. Migrations entram quando houver dado a preservar.

### 4.2 Pipeline: BackgroundTasks + polling

- **Decisão:** pipeline roda em `BackgroundTasks` do FastAPI; UI acompanha por polling de status.
- **Justificativa:** um processo, sem broker (driver 1). Estágio persistido a cada passo dá visibilidade de progresso e localização de erro.
- **Alternativas consideradas:**

| Opção | Prós | Contras |
|---|---|---|
| BackgroundTasks + polling | zero infra extra, testável inline | restart perde jobs em voo; não escala horizontal |
| Celery/arq + Redis | retry, workers, durabilidade | +2 containers, complexidade não exigida |
| Processamento síncrono | trivial | request de 30–60s, timeout, UI travada |

- **Notas:** trade-off consciente — restart do container deixa contratos presos em `processing`. O schema já suporta múltiplas extrações por contrato (reprocesso é evolução natural).

### 4.3 Gateway LLM: LiteLLM Proxy como único caminho

- **Decisão:** backend fala protocolo OpenAI com o LiteLLM Proxy; o proxy fala com a OpenRouter. Aliases estáveis (`extraction-model`, `analysis-model`) no config do proxy.
- **Justificativa:** chave OpenRouter confinada ao container do proxy (driver 4); troca de modelo é edição de config (driver 5); custo/tokens/latência instrumentados no proxy, não no app (RNF04).
- **Alternativas consideradas:**

| Opção | Prós | Contras |
|---|---|---|
| LiteLLM Proxy | isolamento da chave, métricas grátis, aliases | +1 container, +1 hop |
| SDK OpenRouter direto no backend | menos peças | chave no app, métricas manuais, acoplamento |

### 4.4 Duas chamadas LLM com prompts versionados

- **Decisão:** extração literal (modelo barato, `temperature=0`) e resumo+análise (modelo forte) são chamadas, prompts e schemas separados. Prompts em arquivos `*_vN.md`; versão gravada no banco junto do resultado.
- **Justificativa:** tarefas com perfis opostos (driver 2): extração quer determinismo e custo baixo; análise quer capacidade. Versão persistida torna qualquer resultado reproduzível/comparável (driver 3).
- **Alternativas consideradas:**

| Opção | Prós | Contras |
|---|---|---|
| 2 chamadas especializadas | custo otimizado, prompts focados | 2 round-trips |
| 1 chamada única | 1 round-trip | modelo caro faz trabalho braçal; prompt monolítico |

- **Notas:** modelos escolhidos via OpenRouter: `anthropic/claude-haiku-4.5` (extração) e `anthropic/claude-sonnet-5` (análise) — ver D1.

### 4.5 Output do LLM como candidato

- **Decisão:** structured output (JSON schema derivado do Pydantic) + validação Pydantic sempre + validadores determinísticos (CNPJ/UF/data BR). Campo inválido é persistido com flag, nunca descartado nem corrigido silenciosamente.
- **Justificativa:** RNF02/RF05 — o LLM não é fonte de verdade; a UI mostra exatamente o que veio e o que falhou (driver 3).
- **Alternativas consideradas:**

| Opção | Prós | Contras |
|---|---|---|
| Validação determinística pós-LLM | confiável, testável, explicável | código próprio p/ cada tipo |
| Confiar no structured output | menos código | schema não valida dígito verificador nem calendário |
| Segunda chamada LLM validadora | flexível | não-determinística, custo, valida LLM com LLM |

### 4.6 Persistência campo-a-campo (EAV restrito)

- **Decisão:** campos extraídos em tabela `extracted_fields` (um registro por campo: `field_name` plano tipo `provider.cnpj`), não colunas tipadas.
- **Justificativa:** cada campo carrega 5 atributos de auditoria (driver 3); PATCH de correção e renderização da UI ficam uniformes. Não há requisito de query por campo específico — o trade-off clássico do EAV não se aplica.
- **Alternativas consideradas:**

| Opção | Prós | Contras |
|---|---|---|
| Campo-a-campo | auditoria uniforme, PATCH trivial | sem query tipada por campo |
| Colunas tipadas | queries diretas, FK/índices | ~5 colunas de auditoria × 17 campos, ou tabela paralela de correções |

### 4.7 Frontend: Next.js + SWR

- **Decisão:** Next.js App Router + TypeScript + Tailwind; dados via SWR (polling nativo com `refreshInterval`); rewrite `/api → backend` (sem CORS).
- **Justificativa:** stack fechada pelo requisito; SWR resolve polling/revalidação sem estado global.

### 4.8 Qualidade: uv, ruff, mypy --strict, detect-secrets, pytest

- **Decisão:** uv para deps, ruff (lint+format), mypy --strict, detect-secrets no pre-commit e CI; pytest com coverage mínimo 80% (gate de CI), 90% para promover a prod.
- **Justificativa:** camadas de qualidade automatizadas desde o commit 1 (driver 1); nos testes, o único mock é o cliente LLM — banco, validadores e parsing rodam de verdade.

## 7. Segurança

- **Chave OpenRouter**: injetada só no container litellm (RNF01); backend autentica no proxy com master key própria. `detect-secrets` no pre-commit e CI; `.env` gitignored.
- **Prompt injection** (RNF03): texto do contrato delimitado em `<contract_text>` com instrução explícita de que é dado, não comando + reforço pós-texto; output forçado a schema fechado; validação determinística limita o que um injection consegue corromper. Teste de regressão com fixture maliciosa.
- **Upload**: validação de MIME/extensão e tamanho (20 MB); arquivo armazenado com nome UUID (não o nome original) em volume isolado.
- **Sem auth de usuário na v1**: escopo single-user local. Registrado como limitação, não como lacuna acidental.

## 10. Riscos e Mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|---|---|---|---|
| Restart perde jobs `processing` | contrato preso | média | status visível; schema suporta reprocesso futuro |
| PDF escaneado sem texto | pipeline falha | média | erro explícito por estágio ("OCR fora de escopo") |
| Structured output não suportado fim-a-fim na rota OpenRouter→Anthropic | extração falha | baixa | fallback: instrução JSON + validação Pydantic + 1 retry com o erro |
| LLM alucina valor plausível | metadado errado | média | validação determinística + revisão humana na UI (flags) |
| Prompt injection no contrato | output corrompido | média | delimitação + schema fechado + teste de regressão |
| SQLite lock com escrita concorrente | erro 5xx | baixa | escrita rara, 1 pipeline por vez por processo |

## 11. Decisões em Aberto

| # | Decisão | Opções | Prazo |
|---|---|---|---|
| D1 ✅ | Slugs OpenRouter exatos dos modelos | resolvido 2026-07-16 via lista oficial: `anthropic/claude-haiku-4.5` (extração) e `anthropic/claude-sonnet-5` (análise) | issue #7 |
| D2 | Estratégia de reprocessamento de contrato | novo endpoint vs re-upload | pós-MVP |

## 13. Referências

- LiteLLM Proxy: https://docs.litellm.ai/docs/simple_proxy
- OpenRouter models: https://openrouter.ai/models
- SQLAlchemy 2.0 async: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Structured Outputs (protocolo OpenAI): https://platform.openai.com/docs/guides/structured-outputs
- Algoritmo CNPJ (dígitos verificadores): https://www.macoratti.net/alg_cnpj.htm

## 14. Estado da Implementação

### 14.1 Entregue ✅
- Scaffold do monorepo, pre-commit, branches protegidas (#1, PR #19)
- CI backend/frontend/secrets (#2, PR #20)

### 14.2 Pendente dentro deste ADR
- Issues #4–#18 (backend core, pipeline, frontend, infra, observabilidade)

### 14.3 Fora de escopo
- OCR de PDFs escaneados; autenticação de usuários; reprocessamento (D2); migrations (Alembic)
