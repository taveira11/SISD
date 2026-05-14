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
from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate


# Passo 1 - Prompt Engineering: 


# O prompt é o "guia" que diz ao LLM como usar a informação dos protocolos SNS24 para responder às perguntas dos utilizadores.
#No prompt temos dentro do mesmo variaveis que são preenchidas automaticamente pela LLM quando se cria o RetrievalQA. O {context} é preenchido com os 3 chunks mais relevantes encontrados na base de dados, e o {question} é preenchido com a pergunta do utilizador (os sintomas que ele escreve).
prompt = PromptTemplate(
    input_variables=["context", "question"],
    template="""
Usa os protocolos SNS24 abaixo para responder.
Raciocina passo a passo ANTES de dar a classificação final.

Protocolos: {context} 

Sintomas: {question}

Raciocínio:
1. Que sintomas foram reportados?
2. Existem sinais de alarme?
3. Qual a urgência clínica?

Resposta final: urgencia, encaminhamento, justificação
"""
)
# ─── PASSO 2: Indexar o ficheiro de conhecimento (correr só 1 vez) ────────────
print("A carregar os documentos SNS24...")

# Carrega o ficheiro de texto com os protocolos
documentos = TextLoader("sns24_kb.txt", encoding="utf-8").load()

# Corta o texto em pedaços de ~500 caracteres (chunks)
chunks = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50).split_documents(documentos) #Overlap de 50 caracteres para manter contexto entre chunks Overlap muito grande → chunks muito parecidos, a BD fica redundante e lenta. Overlap muito pequeno → risco de perder contexto nas fronteiras.
print(f"  → {len(chunks)} chunks criados")

# Converte cada chunk num vector numérico (embedding)
# e guarda tudo numa base de dados vectorial (ChromaDB)
print("A criar embeddings... (pode demorar 1-2 minutos na primeira vez)")
base_dados = Chroma.from_documents(
    documents=chunks,
    embedding=OllamaEmbeddings(model="nomic-embed-text"),
    persist_directory="./chroma_sns24"  # guarda em disco
)
print("  → Base de dados pronta!")




# ─── PASSO 3: Criar o chatbot ──────────────────────────────────────────────────
print("A carregar o LLM (llama3.2)...")

chatbot = RetrievalQA.from_chain_type(
    llm=Ollama(model="llama3.1", temperature=0.1),  # temperatura baixa = mais consistente
    retriever=base_dados.as_retriever(search_kwargs={"k": 3}),  # busca 3 chunks por pergunta, Com k=3, quando o utilizador escreve os sintomas, o retriever calcula a similaridade entre a pergunta e todos os chunks da BD, e devolve os 3 mais parecidos. Esses 3 chunks é que vão para o {context} do prompt.
    chain_type_kwargs={"prompt": prompt}  # usa o prompt personalizado que criámos
)
print("  → Chatbot pronto!\n")


# ─── PASSO 4: Fazer perguntas ──────────────────────────────────────────────────
print("=" * 50)
print("Chatbot SNS24 — escreve os teus sintomas")
print("(escreve 'sair' para terminar)")
print("=" * 50)

while True:
    sintomas = input("\nTu: ")

    if sintomas.lower() == "sair":
        break

    # O chatbot:
    # 1. Converte a tua pergunta em vector
    # 2. Encontra os 3 chunks mais parecidos na BD
    # 3. Envia os chunks + a pergunta ao LLM
    # 4. O LLM gera a resposta
    resposta = chatbot.invoke(sintomas)
    print(f"\nSNS24-Bot: {resposta['result']}")



"""
Maneira convencional sem usar o RetrievalQA:

# O que o RetrievalQA faz por ti, escrito à mão:

# 1. Ir buscar os chunks
pergunta = "Tenho febre há 3 dias"  -> User query
chunks = base_dados.as_retriever().get_relevant_documents(pergunta)  - > Busca os 3 chunks mais relevantes para a pergunta "Tenho febre há 3 dias"
contexto = "\n".join([c.page_content for c in chunks]) -> Junta os 3 chunks num único texto para o {context} do prompt

# 2. Preencher o template
prompt_preenchido = prompt.format(context=contexto, question=pergunta) -> Preenche o prompt com o contexto (os 3 chunks) e a pergunta do utilizador.

# 3. Enviar ao LLM
resposta = Ollama(model="llama3.2").invoke(prompt_preenchido)

"""