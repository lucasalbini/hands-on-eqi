# Análise de Contratos com LLM

Upload de um contrato (PDF/DOCX) → extração de metadados estruturados via LLM → resumo executivo e análise qualitativa → UI para revisar e corrigir os campos. A aplicação nunca chama a OpenRouter diretamente: toda chamada passa pelo LiteLLM Proxy, e a chave da OpenRouter existe **apenas** no container do proxy.

## Arquitetura

```
                ┌──────────────┐   rewrite /api    ┌──────────────┐
   navegador ─► │   Next.js    │ ────────────────► │   FastAPI    │
                │  (frontend)  │                   │  (backend)   │
                └──────────────┘                   └──────┬───────┘
                                          ┌───────────────┼───────────────┐
                                          ▼               ▼               ▼
                                   ┌────────────┐  ┌────────────┐  ┌──────────┐
                                   │  SQLite    │  │  LiteLLM   │  │ uploads  │
                                   │ (aiosqlite)│  │   Proxy    │  │ (volume) │
                                   └────────────┘  └─────┬──────┘  └──────────┘
                                                         │ OPENROUTER_API_KEY (só aqui)
                                                         ▼
                                                   ┌────────────┐
                                                   │ OpenRouter │
                                                   └────────────┘
   Prometheus ◄── /metrics (backend + litellm) ──► Grafana
```

**Pipeline** (assíncrono, `BackgroundTasks` + polling): `parse` (pdfplumber/python-docx) → `extract` (Claude Haiku 4.5, `temperature=0`, structured output) → `analyze` (Claude Sonnet). Cada estágio persiste o progresso; falha grava `status=failed` + estágio + mensagem, visível na UI.

**Extração ≠ análise:** chamadas, prompts e modelos separados e versionados. Extração literal quer determinismo e custo baixo; análise quer capacidade.

**Output do LLM é candidato, não verdade:** structured output + validação Pydantic + validadores determinísticos (CNPJ com dígito verificador, UF nas 27 siglas, data BR dia/mês). Campo inválido é sinalizado na UI, nunca descartado. O usuário corrige na UI; o valor original do LLM é preservado para auditoria.

**Prompt injection:** o texto do contrato é input não confiável — entra delimitado em `<contract_text>` com reforço anti-injection, e a validação determinística limita o estrago mesmo se o modelo obedecer a um comando embutido.

## Como rodar

Pré-requisitos: Docker + Docker Compose, e uma chave da OpenRouter.

```bash
cp .env.example .env
# edite .env: preencha OPENROUTER_API_KEY e defina um LITELLM_MASTER_KEY qualquer
docker compose up --build
```

| Serviço    | URL                     |
|------------|-------------------------|
| Frontend   | http://localhost:3000   |
| Backend    | http://localhost:8000/docs |
| Grafana    | http://localhost:3001 (admin / `GRAFANA_ADMIN_PASSWORD`) |
| Prometheus | http://localhost:9090   |

O LiteLLM fica interno (porta não publicada) — só o backend o acessa. A chave da OpenRouter é injetada apenas no container do LiteLLM.

Roteiro de validação manual: envie um PDF de contrato na home → acompanhe o status mudar de "Processando" para "Concluído" → abra o contrato → confira metadados e análise → corrija um campo inválido (some a flag, aparece o badge "corrigido") → veja custo/tokens/latência por modelo no Grafana.

## Desenvolvimento

**Backend** (Python 3.12, [uv](https://docs.astral.sh/uv/)):

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload   # http://localhost:8000
uv run pytest --cov=app                 # testes + coverage
uv run ruff check . && uv run mypy --strict app
```

**Frontend** (Next.js 15):

```bash
cd frontend
npm ci
npm run dev      # http://localhost:3000 (proxy /api → localhost:8000)
npm test && npm run lint && npm run build
```

## Estrutura

```
backend/app/
├── main.py            # app factory, lifespan, /metrics, middleware de request_id
├── config.py          # pydantic-settings (env vars)
├── db.py / models.py  # SQLAlchemy 2.0 async (4 tabelas)
├── schemas.py         # Pydantic v2 (schemas do LLM e da API)
├── api/contracts.py   # upload, status, get, patch, lista
├── pipeline/          # runner, parsing, extraction, analysis
├── llm/               # client (→ LiteLLM), prompts versionados, loader
├── validators/        # cnpj, uf, dates (determinísticos, puros)
└── observability.py   # structlog + métricas Prometheus
frontend/src/
├── app/               # / (upload+lista), /contracts/[id] (detalhe)
├── components/        # UploadDropzone, ContractsTable, FieldRow, PartyCard, ...
└── lib/api.ts         # client tipado
docker/                # litellm, prometheus, grafana (config + provisioning)
docs/adr/              # decisões arquiteturais
```

## Testes e qualidade

- Backend: pytest + pytest-asyncio, SQLite in-memory; o **único** mock é a fronteira de rede do LLM — banco, parsing, validadores e a API rodam de verdade. Coverage mínimo de 90% no CI.
- Frontend: vitest + testing-library.
- Pre-commit: ruff (lint+format), mypy --strict, detect-secrets. CI verde obrigatório em toda PR.

## Limitações conhecidas

- **Sem OCR:** PDF escaneado (sem camada de texto) falha explicitamente no estágio de parse.
- **Jobs em voo não sobrevivem a restart:** o pipeline roda em `BackgroundTasks` (sem broker); reiniciar o backend deixa contratos presos em `processing`. Trade-off consciente para o escopo — ver [ADR-0001](docs/adr/0001-stack-inicial.md).
- **Sem autenticação de usuário:** escopo single-user local.

## Decisões

As escolhas de stack e seus trade-offs estão em [docs/adr/0001-stack-inicial.md](docs/adr/0001-stack-inicial.md).
