from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
# from sentence_transformers import SentenceTransformer
from supabase import create_client
from google import genai
from google.genai import types
import os
import httpx
import asyncio
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

HF_API_URL = "https://api-inference.huggingface.co/models/intfloat/multilingual-e5-large"
HF_TOKEN = os.environ.get("HF_TOKEN", "")


# model = SentenceTransformer("intfloat/multilingual-e5-large")

async def get_embedding(text: str) -> list:
    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(3):
            try:
                response = await client.post(
                    HF_API_URL,
                    headers={"Authorization": f"Bearer {HF_TOKEN}"},
                    json={"inputs": "query: " + text}
                )
                response.raise_for_status()
                return response.json()[0]
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)  # 1s, 2s backoff

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"]
)
gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
GEMINI_MODEL = os.environ.get("GEMINI_ANSWER_MODEL", "gemma-4-31b-it")

SYSTEM_PROMPT = """Você é o assistente especializado do Brasil 2040, uma ferramenta de visualização do relatório "Brasil 2040 — Mudanças Climáticas e Vulnerabilidade Agrícola".

REGRAS DE ESCOPO E REDIRECIONAMENTO:
- Se a pergunta for completamente fora do escopo do Brasil 2040 ou irrelevante para o tema de risco climático (como receitas, piadas ou assuntos gerais), responda exatamente: "Esta pergunta está fora do escopo do assistente Brasil 2040. Só posso responder perguntas sobre o relatório de risco climático."
- Você pode receber perguntas em outros idiomas (como inglês). Traduza-as mentalmente para buscar as respostas no contexto em português, mas responda sempre em português do Brasil.

REGRAS DE CONTEXTO E FIDELIDADE:
- Responda APENAS com base nos trechos de texto fornecidos no contexto.
- Não tente adivinhar, estimar ou extrapolar números e porcentagens. Se qualquer dado numérico ou estatística exata solicitada na pergunta não estiver escrito de forma explícita e clara nos trechos fornecidos, você deve responder exatamente: "Não encontrei essa informação nos trechos fornecidos."
- Se houver símbolos de porcentagem (%) ou lacunas vazias nas tabelas e textos fornecidos no contexto, nunca tente preencher esses números por conta própria.
- Para questões conceituais, metodológicas ou descritivas, responda normalmente utilizando as explicações e conceitos presentes no contexto.
- Cite números e estatísticas exatamente como aparecem nos documentos. Não invente informações.

TEMAS DO RELATÓRIO:
Responda perguntas sobre:
- O ZARC (Zoneamento Agrícola de Risco Climático) e sua metodologia
- Os cenários climáticos: Risco 90 (linha de base atual), RCP 4.5 (aquecimento moderado ~+1,5-2°C) e RCP 8.5 (aquecimento elevado ~+3-4°C)
- As 11 culturas: soja, milho, safrinha, arroz, feijão verão, feijão inverno, feijão caupi, cana-de-açúcar, algodão, trigo e sorgo
- Impactos das mudanças climáticas na agricultura brasileira até 2040
- Regiões produtoras e sua vulnerabilidade climática
- Políticas de adaptação e seguro agrícola no Brasil

ESTILO DE RESPOSTA:
Responda sempre em português do Brasil. Seja conciso e técnico quando necessário, mas acessível. Máximo de 3 parágrafos
"""

class QueryRequest(BaseModel):
    question: str
    top_k: int = 5

class ChatRequest(BaseModel):
    question: str
    history: list[dict] = []   # [{"role": "user"|"model", "parts": "..."}]
    top_k: int = 5

@app.get("/")
async def root():
    return {"status": "ok", "message": "Brasil 2040 API is running"}

@app.post("/search")
async def search(req: QueryRequest):  # ← add async
    embedding = await get_embedding(req.question)  # ← was model.encode(...)

    result = supabase.rpc(
        "match_documents",
        {"query_embedding": embedding, "match_count": req.top_k}
    ).execute()
    return {"chunks": result.data}

@app.post("/chat")
async def chat(req: ChatRequest):
    # 1. Retrieve context
    embedding = await get_embedding(req.question)
    result = supabase.rpc(
        "match_documents",
        {"query_embedding": embedding, "match_count": req.top_k}
    ).execute()
    chunks = result.data
    context = "\n\n".join(
        f"[{c['file']} — pág. {c['page']}]\n{c['text']}" for c in chunks
    )

    # 2. Build message with context injected
    user_message = (
        f"Contexto extraído dos documentos Brasil 2040:\n\n{context}\n\n"
        f"Pergunta do usuário: {req.question}"
    )

    # 3. Rebuild history + new message for Gemini
    contents = []
    for msg in req.history:
        contents.append(types.Content(
            role=msg["role"],
            parts=[types.Part(text=msg["parts"])]
        ))
    contents.append(types.Content(
        role="user",
        parts=[types.Part(text=user_message)]
    ))

    # 4. Stream response back
    async def stream():
        for chunk in gemini_client.models.generate_content_stream(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7,
                top_p=0.95,
                top_k=30,
                max_output_tokens=1000,
            ),
        ):
            if chunk.text:
                yield chunk.text

    return StreamingResponse(stream(), media_type="text/plain")

app.mount("/", StaticFiles(directory=".", html=True), name="static")