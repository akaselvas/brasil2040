# Brasil 2040

Aplicação web para explorar o risco climático da agricultura e da infraestrutura brasileira até 2040, com um assistente de IA (RAG) que responde apenas com base nos relatórios do governo federal.

O projeto tem três partes: um mapa interativo de municípios por cultura e cenário climático, painéis setoriais com os números principais dos relatórios e um chatbot cujas respostas precisam ser rastreáveis aos documentos originais. O chatbot é coberto por uma suíte de evals automatizada no GitHub Actions.

Feito para quem quer consultar os dados do relatório sem ler 42 PDFs e, do lado técnico, para quem quer ver um RAG construído do zero e testado como produto (retrieval, fidelidade ao contexto, alucinação e regressão de prompt).

[![AI Evals](https://github.com/akaselvas/brasil2040/actions/workflows/evals.yml/badge.svg?branch=main)](https://github.com/akaselvas/brasil2040/actions/workflows/evals.yml)

## TL;DR

- **O que é:** RAG construído do zero sobre 42 PDFs de relatórios climáticos do governo brasileiro, com mapa D3 de 5.570 municípios, painéis setoriais e chatbot que só responde com base nos documentos.
- **Stack:** FastAPI, `multilingual-e5-large`, Supabase (pgvector, HNSW), Gemini, D3.js, deploy em Docker no HuggingFace Spaces.
- **Foco em qualidade:** suíte de evals em GitHub Actions com 30 perguntas no golden set e 5 jobs (retrieval, fidelidade com LLM-as-judge, latência e custo, regressão de prompt e execução completa).
- **Achados reais:** 36% dos chunks eram ruído (802 de 2.203) e o prompt tratava a lista de temas como exaustiva, o que causava falsa recusa em 33 de 86 perguntas. Depois da correção, restaram 2, ambas lacunas reais do corpus.
- **Teste exploratório:** um agente ScoutQA achou o que a suíte não enxerga, como o contador de municípios oscilando entre 5.570 e 5.563.
- **Rodar:** `docker build -t brasil2040 .` e `docker run -p 7860:7860` com `SUPABASE_URL`, `SUPABASE_KEY` e `GEMINI_API_KEY`.

## Demo

- **Aplicação:** https://huggingface.co/spaces/aka-selvas/brasil2040
- **Workflow de evals:** https://github.com/akaselvas/brasil2040/actions/workflows/evals.yml
- **Relatório do agente ScoutQA (teste exploratório de 30 min):** https://app.scoutqa.ai/r/019eb901-dbdc-776a-80a8-867e9988ed96
- **Kaggle Notebook para o embedding:** (docs/brasil2040-embeddings.ipynb)
<!-- Troque pelo caminho real do screenshot ou GIF -->
![Mapa de risco agrícola](docs/screenshot-mapa.png)

## Funcionalidades

**Mapa de risco agrícola**
- 5.570 municípios renderizados com D3.js a partir de GeoJSON do IBGE
- 11 culturas: soja, milho, safrinha, arroz, feijão (verão, inverno e caupi), cana-de-açúcar, algodão, trigo e sorgo
- 3 cenários: Risco 90 (linha de base), RCP 4.5 e RCP 8.5
- Coloração por percentual da área municipal em baixo e alto risco, tooltip por município, fixação de município na sidebar, zoom e pan

**Painéis setoriais**
- Agricultura, Energia, Recursos Hídricos, Transportes, Infraestrutura Costeira e Infraestrutura Urbana
- KPIs, gráficos e quadros de cenários extraídos dos relatórios (ex.: custo operacional do SIN, risco de déficit, redução de ENA)
- Perguntas sugeridas por painel que alimentam o chat

**Chatbot com RAG**
- Busca vetorial no Supabase (pgvector) e geração com Gemini, com streaming da resposta
- Aceita perguntas em outros idiomas e responde em português
- Recusa perguntas fora do escopo e declara quando um dado específico não está nos trechos recuperados
- Histórico de conversa enviado a cada requisição

## Arquitetura

```
 BUILD (offline, notebook Kaggle com GPU)

 42 PDFs  ->  PyMuPDF + find_tables()  ->  chunking por sentença  ->  multilingual-e5-large  ->  Supabase pgvector
 (gov. BR)    (texto + tabelas)            (preserva "16,7×")        (1024 dims)               (índice HNSW)


 RUNTIME (HuggingFace Spaces, container Docker)

 Browser (D3.js + chat)
        |
        |  POST /chat  {question, history, top_k}
        v
 FastAPI
   1. embedding da pergunta ("query: " + texto, normalizado)
   2. rpc match_documents no Supabase (cosine, top_k)
   3. monta o contexto: [arquivo, pág.] + texto de cada chunk
   4. Gemini (generate_content_stream) com SYSTEM_PROMPT
        |
        v
 StreamingResponse (text/plain) -> chat
```

Pontos de design que valem a leitura:

- **A base de conhecimento é parte do produto.** O pipeline de ingestão foi tratado como código testável. Números como `16,7×` e `99%` precisam sobreviver a extração de PDF, limpeza, chunking, embedding, retrieval e geração. Uma regex de limpeza comum (`\b\w{1,2}\b`) quebrava decimais com vírgula em `"16,"` e `"7"`, e `get_text("text")` do PyMuPDF ignora células de tabela. Ambos foram corrigidos e verificados com um diagnóstico rodado antes do embedding.
- **Prefixo `query:` no e5.** O modelo multilingual-e5-large espera `query: ` nas perguntas e `passage: ` nos documentos. O endpoint aplica o prefixo e normaliza o vetor.
- **Retrieval e geração falham de formas parecidas.** Do ponto de vista do chat, "não encontrei" pode ser chunk errado ou prompt restritivo. Para separar as camadas existe o endpoint `/search`, que retorna só os chunks e é usado nos testes de retrieval.
- **Frontend servido pelo FastAPI.** `StaticFiles` monta o diretório raiz, então o mesmo container serve a API e o site (um único Space).

## Pipeline de ingestão

O notebook `ingestion/brasil2040-embeddings.ipynb` roda no Kaggle (GPU) e gera a base vetorial a partir dos 42 PDFs. Credenciais vêm de Kaggle Secrets (`SUPABASE_URL`, `SUPABASE_KEY`) e o modelo é carregado de um dataset local do Kaggle.

| Etapa | Implementação |
|---|---|
| Extração | PyMuPDF, página a página. `find_tables()` converte tabelas para linhas `a \| b \| c` (via pandas) e anexa ao texto da página sob o marcador `[TABELA]` |
| Limpeza | Whitelist de caracteres, junção de palavras hifenizadas na quebra de linha, colapso de espaços. Páginas com menos de 50 caracteres são descartadas |
| Chunking | Split por sentença (`(?<=[.!?])\s+(?=[A-Z...])`), que não quebra em decimais como `16,7`. Janela de 600 palavras, overlap de 100, chunks com menos de 30 palavras descartados |
| Embedding | `multilingual-e5-large`, 1024 dims, batch 32, `normalize_embeddings=True`, prefixo `passage: ` |
| Backup | `embeddings.npy` e `metadata.json` (file, page, chunk_idx, text) |
| Upload | Insert em lotes de 100 na tabela `documents`, com retry simples por lote |
| Verificação | Contagem de linhas e uma query de teste com `query: ` impressa com similaridade |

**Diagnóstico pré-embedding.** Antes de gerar os vetores, uma célula varre todos os PDFs procurando termos críticos (`16,7`, `74%`, `99%`, `112,3`, `34%`, `20,6` e outros) e marca onde eles somem após a limpeza (`destroyed_by_regex`) ou onde só existem dentro de tabelas (`only_in_table`). Foi assim que o bug da regex `\b\w{1,2}\b` e a ausência de números em tabelas foram encontrados.

Os chunks de ruído (802 de 2.203) foram removidos direto no banco depois da ingestão. O notebook não tem filtro de qualidade, então hoje isso é uma etapa manual.

## Tecnologias

| Camada | Stack |
|---|---|
| Frontend | HTML, CSS, JavaScript, D3.js 7 |
| Backend | FastAPI, Uvicorn |
| Embeddings | sentence-transformers, `intfloat/multilingual-e5-large` (1024 dims) |
| Vector store | Supabase (PostgreSQL + pgvector, índice HNSW) |
| LLM | Google Gemini via `google-genai` (modelo configurável) |
| Ingestão | PyMuPDF, pandas, notebook Kaggle com GPU |
| Testes | Pytest, LLM-as-judge (Gemini), pytest-html |
| CI/CD | GitHub Actions |
| Deploy | Docker, HuggingFace Spaces |

## Como rodar localmente

### Pré-requisitos

- Python 3.11
- Um projeto Supabase com a tabela `documents` populada e a função `match_documents` criada (ver [Banco de dados](#banco-de-dados) e [Pipeline de ingestão](#pipeline-de-ingestão))
- Uma chave da API do Gemini

### Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `SUPABASE_URL` | sim | URL do projeto Supabase |
| `SUPABASE_KEY` | sim | Chave de acesso ao Supabase |
| `GEMINI_API_KEY` | sim | Chave da API do Gemini |
| `GEMINI_ANSWER_MODEL` | não | Modelo de geração. Default: `gemini-3.5-flash-lite` |

```bash
export SUPABASE_URL="https://xxxx.supabase.co"
export SUPABASE_KEY="..."
export GEMINI_API_KEY="..."
```

### Com Python

```bash
git clone https://github.com/akaselvas/brasil2040.git
cd brasil2040

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

uvicorn main:app --reload --port 8000
```

Acesse http://localhost:8000. Na primeira execução o `sentence-transformers` baixa o modelo de embedding (cerca de 1 GB), então o start inicial demora.

### Com Docker

```bash
docker build -t brasil2040 .

docker run --rm -p 7860:7860 \
  -e SUPABASE_URL="$SUPABASE_URL" \
  -e SUPABASE_KEY="$SUPABASE_KEY" \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  brasil2040
```

Acesse http://localhost:7860. A imagem usa a porta 7860 por exigência do HuggingFace Spaces.

### Verificação rápida

```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"question": "O que é o fator de fricção?", "top_k": 3}'
```

## API

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/search` | Retorna os `top_k` chunks mais próximos da pergunta. Body: `{question, top_k}` |
| `POST` | `/chat` | Retrieval + geração com streaming (`text/plain`). Body: `{question, history, top_k}` |
| `GET` | `/health` | Healthcheck usado pelo CI para saber quando o servidor subiu |

`history` é uma lista de `{"role": "user" | "model", "parts": "texto"}`. O `top_k` padrão é 5 em `/search` e 8 em `/chat`.

### Banco de dados

Rode uma vez no SQL Editor do Supabase antes de executar o notebook de ingestão:

```sql
create extension if not exists vector;

create table if not exists documents (
  id         bigserial primary key,
  file       text not null,
  page       integer not null,
  chunk_idx  integer not null,
  text       text not null,
  embedding  vector(1024)
);

create index if not exists documents_embedding_idx
  on documents
  using hnsw (embedding vector_cosine_ops);

create or replace function match_documents (
  query_embedding vector(1024),
  match_count     int default 5
)
returns table (
  id         bigint,
  file       text,
  page       integer,
  text       text,
  similarity float
)
language sql stable
as $$
  select
    id, file, page, text,
    1 - (embedding <=> query_embedding) as similarity
  from documents
  order by embedding <=> query_embedding
  limit match_count;
$$;
```

O backend usa `file`, `page` e `text` do retorno. A distância é cosseno, e como os vetores são normalizados na ingestão e na busca, os dois lados ficam consistentes.

## Testes e evals

A suíte vive em `evals/` e roda no GitHub Actions via `workflow_dispatch`, com seleção do grupo de testes (`retrieval`, `faithfulness`, `latency`, `regression` ou `all`).

| Job | O que valida | Critério |
|---|---|---|
| `retrieval-evals` | O chunk certo volta no top-k? | Arquivo-fonte esperado presente e pelo menos 50% dos termos esperados no texto recuperado. Inclui pergunta em inglês contra corpus em português e casos de borda (string vazia, 3.200 caracteres) |
| `faithfulness-evals` | A resposta é sustentada pelo contexto? | LLM-as-judge (Gemini) sobre o trio pergunta, resposta, contexto. Limiar de 0,70 para perguntas factuais e 0,60 para sínteses |
| `latency-evals` | Tempo e custo | P95 de retrieval abaixo de 5 s, orçamento de tokens de contexto, custo estimado por query impresso no log |
| `prompt-regression` | Mudança de prompt quebrou algo? | Compara respostas atuais com um baseline JSON. Termos âncora ausentes indicam regressão. Números novos que não existem no baseline indicam afrouxamento das restrições factuais |
| `nightly-full-eval` | Execução completa com juiz real | Roda `evals/` inteiro com limiar de fidelidade de 0,75 |

Os jobs de fidelidade, latência e regressão dependem do sucesso do retrieval. Não faz sentido julgar uma resposta se o contexto recuperado está errado.

### Golden set

`evals/golden_set.json` tem 30 perguntas em 8 categorias, cada uma com `expected_answer_contains`, `expected_chunk_sources` e `notes` explicando as decisões de calibração. Categorias principais:

- **Factuais e conceituais** por setor (agricultura, energia, hídrico, transportes, costeira)
- **`hallucination_trap`**: perguntas sobre dados inexistentes (PIB agrícola de 2039, El Niño de 2038). Têm `must_not_contain`, verificado programaticamente antes do juiz, e `should_hedge`
- **`out_of_scope`**: receita de brigadeiro, Copa do Mundo. O esperado é a recusa padrão do prompt
- **Multilíngue, síntese entre setores e regressão de prompt**

### Rodando os evals localmente

```bash
pip install -r evals/requirements.txt

# terminal 1
uvicorn main:app --port 8000

# terminal 2
export SEARCH_ENDPOINT="http://localhost:8000/search"
export GEMINI_API_KEY="..."
export JUDGE_BACKEND="gemini"

pytest evals/test_retrieval.py -v
pytest evals/test_faithfulness.py -v
pytest evals/test_latency_cost.py -v -k "not end_to_end"
REGRESSION_MODE=compare pytest evals/test_prompt_regression.py -v
```

Variáveis de ajuste: `FAITHFULNESS_THRESHOLD`, `HALLUCINATION_THRESHOLD`, `SIMILARITY_THRESHOLD`, `RETRIEVAL_P95_MS`, `MAX_TOKENS_PER_QUERY`.

### Secrets do repositório

Para o workflow rodar no seu fork, cadastre `SUPABASE_URL`, `SUPABASE_KEY` e `GEMINI_API_KEY` em Settings > Secrets and variables > Actions.

### Bugs encontrados e o que cada camada enxerga

Um dos achados mais úteis veio de uma pergunta sugerida pela própria UI que retornava falsa recusa. Comparando `/search` com `/chat` nas mesmas 86 perguntas, ficou claro que havia chunks relevantes e o modelo recusava mesmo assim. Duas causas:

1. **Escopo no prompt.** A lista de temas do `SYSTEM_PROMPT` citava só agricultura, e o modelo tratou a lista como exaustiva. 33 de 86 perguntas falharam assim. O prompt passou a listar todos os setores do corpus.
2. **Chunks de ruído.** 802 de 2.203 chunks (36%) eram dumps de tabela (`"BAIXO 0 BAIXO BAIXO..."`) e cabeçalhos institucionais, que ganhavam similaridade alta contra quase qualquer pergunta. Foram removidos e as 33 falhas caíram para 2, ambas lacunas reais do corpus.

Um agente ScoutQA explorou a UI por 30 minutos sem script e encontrou o que a suíte não vê, como o contador de municípios oscilando entre 5.570 e 5.563 (5 perdidos no join com o CSV de risco e 2 na validação de geometria) e entradas que retornavam resposta vazia sem feedback ao usuário. O contrário também vale: nenhum agente de browser consegue avaliar fidelidade ao contexto.

Lacunas conhecidas, ainda sem cobertura: prompt injection, red-team adversarial, rate limit e quota de tokens, eventos de toque no mobile e verificação do streaming em E2E.


## Estrutura do repositório

```
.
├── main.py              # API FastAPI (/search, /chat, /health) e serve o frontend
├── index.html           # Shell da aplicação
├── app.js               # Mapa D3, filtros, painéis e chat
├── style.css
├── panels/              # Painéis setoriais carregados dinamicamente
│   ├── panel-agro.html
│   ├── panel-energia.html
│   ├── panel-hidro.html
│   ├── panel-transp.html
│   ├── panel-costa.html
│   ├── panel-urb.html
│   └── panel-sobre.html
├── ingestion/
│   └── brasil2040-embeddings.ipynb   # extração, chunking, embedding e upload
├── evals/
│   ├── golden_set.json
│   ├── test_retrieval.py
│   ├── test_faithfulness.py
│   ├── test_latency_cost.py
│   ├── test_prompt_regression.py
│   └── requirements.txt
├── .github/
│   ├── workflows/evals.yml
│   └── README.md        # este arquivo
├── Dockerfile
└── requirements.txt
```

## Limitações conhecidas

- CORS está aberto (`allow_origins=["*"]`) e não há rate limit nem autenticação nos endpoints. Aceitável para demo, não para produção.
- A resposta é limitada a 3 parágrafos e o prompt proíbe extrapolar números que não estejam nos trechos. Isso reduz alucinação, mas gera recusas em perguntas numéricas quando o chunk certo não é recuperado.
- O juiz é um LLM e compartilha modos de falha com o sistema testado. Por isso os limiares de fidelidade são tratados como estimativa de confiança e não como veredito binário.
- A qualidade do retrieval depende da qualidade da ingestão. Tabelas complexas dos PDFs ainda podem gerar chunks ruidosos, e a remoção dos 802 chunks de ruído foi manual, sem filtro automático no pipeline.
- O chunking é por página: um fato que começa no fim de uma página e termina na seguinte fica dividido em dois chunks.
- A limpeza de texto usa whitelist de caracteres e remove símbolos como `×`, `−` e `–`. Isso pode apagar o sinal de números (por exemplo `−30%`) e deve ser verificado contra o conteúdo do banco.
- O upload usa `insert`, não `upsert`. Rodar o notebook duas vezes duplica os chunks, e duplicatas ocupam vagas no top-k.

## Fontes de dados e créditos

- **ZARC (Zoneamento Agrícola de Risco Climático)**: Embrapa / MAPA. Classificação de risco por município, cultura e cenário
- **Malha municipal**: IBGE
- **Relatório Brasil 2040: Mudanças Climáticas e Vulnerabilidade Agrícola** e relatórios setoriais (energia, recursos hídricos, transportes, infraestrutura costeira e urbana), incluindo estudos de COPPE/UFRJ e PSR. Base de conhecimento do chatbot e dos painéis

Os números exibidos nos painéis vêm dos relatórios originais. Este projeto não é afiliado a nenhum dos órgãos citados. Em caso de divergência, vale o documento original.

## Licença

Defina a licença antes de publicar. Sugestão: MIT para o código. Os dados e relatórios de origem mantêm as licenças e termos de uso de seus autores.

```
MIT License. Veja o arquivo LICENSE.
```
