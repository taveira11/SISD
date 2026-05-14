"""
rag_sns24_simples.py
--------------------
Versão SIMPLES do chatbot RAG para o Projecto P2
TIA/SIAD · Universidade do Minho · 2025/2026

Antes de correr:
    pip install langchain langchain-community chromadb ollama
    ollama pull llama3.2
    ollama pull nomic-embed-text
"""

# ─── PASSO 1: Importar as bibliotecas ─────────────────────────────────────────
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.llms import Ollama
from langchain_classic.chains import ConversationalRetrievalChain
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.prompts import PromptTemplate


# ─── PASSO 2: Prompt Engineering ──────────────────────────────────────────────
# O {chat_history} é preenchido automaticamente pela memória com as trocas anteriores
# O {context} é preenchido com os 3 chunks mais relevantes encontrados na base de dados
# O {question} é preenchido com a pergunta actual do utilizador
prompt = PromptTemplate(
    input_variables=["chat_history", "context", "question"],
    template="""
Usa os protocolos SNS24 abaixo para responder.
Raciocina passo a passo ANTES de dar a classificação final.

Histórico da conversa:
{chat_history}

Protocolos: {context}

Sintomas actuais: {question}

Raciocínio:
1. Que sintomas foram reportados (incluindo os mencionados anteriormente)?
2. Existem sinais de alarme?
3. Qual a urgência clínica?

Resposta final: urgencia, encaminhamento, justificação
"""
)

# ─── PASSO 3: Indexar o ficheiro de conhecimento (correr só 1 vez) ────────────
print("A carregar os documentos SNS24...")

# Carrega o ficheiro de texto com os protocolos
documentos = TextLoader("sns24_kb.txt", encoding="utf-8").load()

# Corta o texto em pedaços de ~500 caracteres (chunks)
# Overlap de 50 caracteres para manter contexto entre chunks
# Overlap muito grande → chunks muito parecidos, a BD fica redundante e lenta
# Overlap muito pequeno → risco de perder contexto nas fronteiras
chunks = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50
).split_documents(documentos)
print(f"  → {len(chunks)} chunks criados")

# Converte cada chunk num vector numérico (embedding)
# e guarda tudo numa base de dados vectorial (ChromaDB)
print("A criar embeddings... (pode demorar 1-2 minutos na primeira vez)")
base_dados = Chroma.from_documents(
    documents=chunks,
    embedding=OllamaEmbeddings(model="nomic-embed-text"),
    persist_directory="./chroma_sns24_mem"  # guarda em disco
)
print("  → Base de dados pronta!")


# ─── PASSO 4: Criar o chatbot COM MEMÓRIA ─────────────────────────────────────
print("A carregar o LLM (llama3.1)...")

# A memória guarda todas as trocas (humano + bot) num buffer em RAM
# Quando o programa fechar, a memória perde-se
memoria = ConversationBufferMemory(
    memory_key="chat_history",  # nome da variável que o chain espera
    return_messages=True,       # devolve lista de mensagens em vez de string
    output_key="answer"         # diz à memória qual a chave da resposta a guardar
)

chatbot = ConversationalRetrievalChain.from_llm(
    llm=Ollama(model="llama3.1", temperature=0.1),  # temperatura baixa = mais consistente
    retriever=base_dados.as_retriever(search_kwargs={"k": 3}),  # vai buscar 3 chunks por pergunta
    memory=memoria,
    return_source_documents=True,                       # True = vemos os chunks usados (útil para debug)
    combine_docs_chain_kwargs={"prompt": prompt}        # usa o prompt personalizado que criámos
)
print("  → Chatbot com memória pronto!\n")


# ─── PASSO 5: Fazer perguntas ──────────────────────────────────────────────────
print("=" * 50)
print("Chatbot SNS24 — escreve os teus sintomas")
print("(escreve 'sair' para terminar)")
print("(escreve 'debug' para ver os chunks usados)")
print("=" * 50)

while True:
    sintomas = input("\nTu: ")

    if sintomas.lower() == "sair":
        break

    # O chatbot:
    # 1. Converte a pergunta em vector
    # 2. Encontra os 3 chunks mais parecidos na BD
    # 3. Junta o histórico da conversa + chunks + pergunta
    # 4. Envia tudo ao LLM
    # 5. Guarda a troca na memória para a próxima pergunta
    resposta = chatbot.invoke({"question": sintomas})
    print(f"\nSNS24-Bot: {resposta['answer']}")

    # Modo debug: mostra os chunks que o retriever foi buscar
    if sintomas.lower() == "debug":
        print("\n--- CHUNKS USADOS ---")
        for i, doc in enumerate(resposta['source_documents']):
            print(f"\nChunk {i+1}:\n{doc.page_content}")
        print("--- FIM DEBUG ---")