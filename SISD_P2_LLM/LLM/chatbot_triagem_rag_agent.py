from pathlib import Path
import json
import re
import subprocess
import requests

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import Chroma

# =========================================================
# CONFIGURAÇÃO
# =========================================================

MODELO_LLM = "qwen2.5:7b-instruct"
MODELO_EMBEDDINGS = "nomic-embed-text"

BASE_DIR = Path(__file__).resolve().parent

BASE_CONHECIMENTO_PATH = BASE_DIR / "sns24_kb_rag_agent.txt"
CHROMA_DIR = BASE_DIR / "chroma_sns24_rag"
PROLOG_DIR = BASE_DIR.parent / "prolog"
PROLOG_API = PROLOG_DIR / "api.pl"

DEBUG = True

# =========================================================
# OLLAMA
# =========================================================

def chamar_ollama(prompt, num_predict=350):
    resposta = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": MODELO_LLM,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "0",
            "options": {
                "temperature": 0.1,
                "num_predict": num_predict,
                "num_ctx": 4096
            }
        },
        timeout=180
    )

    resposta.raise_for_status()
    return resposta.json()["response"].strip()


def extrair_json(texto):
    try:
        inicio = texto.find("{")
        fim = texto.rfind("}") + 1

        if inicio == -1 or fim <= inicio:
            return None

        return json.loads(texto[inicio:fim])

    except Exception:
        return None


def limpar_resposta(texto):
    if not texto:
        return ""

    texto = texto.strip()

    prefixos = [
        "SNS24-Bot:",
        "Assistente:",
        "Paciente:",
        "Utilizador:",
        "Tu:",
        "You:",
        "Bot:",
        "Resposta:"
    ]

    mudou = True
    while mudou:
        mudou = False
        for prefixo in prefixos:
            if texto.startswith(prefixo):
                texto = texto[len(prefixo):].strip()
                mudou = True

    return texto.strip()

# =========================================================
# RAG — BASE DE CONHECIMENTO
# =========================================================

def carregar_ou_criar_rag():
    if not BASE_CONHECIMENTO_PATH.exists():
        raise FileNotFoundError(
            f"Não encontrei o ficheiro {BASE_CONHECIMENTO_PATH}"
        )

    embeddings = OllamaEmbeddings(model=MODELO_EMBEDDINGS)

    if CHROMA_DIR.exists():
        return Chroma(
            persist_directory=str(CHROMA_DIR),
            embedding_function=embeddings
        )

    loader = TextLoader(
        str(BASE_CONHECIMENTO_PATH),
        encoding="utf-8"
    )

    documentos = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=900,
        chunk_overlap=180
    )

    chunks = splitter.split_documents(documentos)

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(CHROMA_DIR)
    )

    return vectorstore


def recuperar_contexto_rag(vectorstore, mensagem, estado, k=5):
    consulta = f"""
    Mensagem do paciente:
    {mensagem}

    Estado clínico atual:
    {json.dumps(estado, ensure_ascii=False, indent=2)}
    """

    resultados = vectorstore.similarity_search(consulta, k=k)

    contexto = "\n\n--- CHUNK ---\n\n".join(
        doc.page_content for doc in resultados
    )

    return contexto


# =========================================================
# ESTADO CLÍNICO
# =========================================================

VALORES_VALIDOS = {
    "tosse": ["sim", "nao"],
    "pieira": ["sim", "nao"],
    "dor_garganta": ["sim", "nao"],
    "congestao_nasal": ["sim", "nao"],
    "agravamento": ["sim", "nao"],
    "duracao_prolongada": ["sim", "nao"],
    "doenca_respiratoria_previa": ["sim", "nao"],
    "imunossupressao": ["sim", "nao"],

    # "desconhecida" é aceite só durante a conversa.
    # Antes de chamar Prolog, a febre terá de ficar nenhuma/moderada/alta.
    "febre": ["nenhuma", "moderada", "alta", "desconhecida"],

    "dificuldade_respiratoria": ["nenhuma", "ligeira", "moderada", "grave", "desconhecida"],
    "dor_toracica": ["nenhuma", "ligeira", "moderada", "forte", "desconhecida"],
    "limitacao_respiratoria": ["nenhuma", "alguma", "significativa", "desconhecida"]
}


def criar_estado(nome, idade):
    return {
        "nome": nome,
        "idade": idade,

        "tosse": None,
        "pieira": None,
        "dor_garganta": None,
        "congestao_nasal": None,
        "agravamento": None,
        "duracao_prolongada": None,
        "doenca_respiratoria_previa": None,
        "imunossupressao": None,

        "febre": None,
        "dificuldade_respiratoria": None,
        "dor_toracica": None,
        "limitacao_respiratoria": None,

        "notas": ""
    }


def normalizar_valor(campo, valor):
    if valor is None:
        return None

    if campo == "idade":
        try:
            idade = int(valor)
            if 0 <= idade <= 120:
                return idade
        except Exception:
            return None

    if isinstance(valor, str):
        valor = valor.strip().lower()
        valor = valor.replace("não", "nao")

    if campo in VALORES_VALIDOS:
        if valor in VALORES_VALIDOS[campo]:
            return valor
        return None

    if campo in ["nome", "notas"]:
        return str(valor)

    return None


def atualizar_estado(estado, estado_atualizado):
    if not isinstance(estado_atualizado, dict):
        return estado

    for campo, valor in estado_atualizado.items():
        if campo not in estado:
            continue

        valor_normalizado = normalizar_valor(campo, valor)

        if valor_normalizado is not None:
            estado[campo] = valor_normalizado

    return estado


def resumo_estado(estado):
    return json.dumps(estado, ensure_ascii=False, indent=2)

# =========================================================
# CONFIGURAÇÃO DA CONVERSA
# =========================================================

def escolher_idioma():
    print("=" * 60)
    print("Chatbot de Triagem Respiratória — Simulação Académica")
    print("=" * 60)

    print("\nSNS24-Bot: Antes de começarmos, prefere falar em português ou inglês?")
    print("1. Português")
    print("2. English")

    escolha = input("\nEscolha / Choice: ").strip()

    if escolha == "2":
        return {
            "idioma": "English",
            "input_label": "You",
            "mensagem_nome": "Before we start, what is your name?",
            "mensagem_idade": "Thank you, {nome}. How old are you?",
            "mensagem_sintomas": "Thank you, {nome}. Now, could you tell me what symptoms you are experiencing?",
            "mensagem_saida": "Thank you. I hope you feel better soon."
        }

    return {
        "idioma": "português de Portugal",
        "input_label": "Tu",
        "mensagem_nome": "Antes de começarmos, como se chama?",
        "mensagem_idade": "Obrigado, {nome}. Que idade tem?",
        "mensagem_sintomas": "Obrigado, {nome}. Agora pode dizer-me o que está a sentir?",
        "mensagem_saida": "Obrigado. As melhoras."
    }
    
    
# =========================================================
# AGENTE CONVERSACIONAL COM RAG
# =========================================================

def construir_prompt_conversacional(
    contexto_rag,
    estado,
    historico,
    mensagem,
    idioma,
    ultimo_campo_perguntado
):
    return f"""
És um agente conversacional académico de triagem respiratória.

A tua função é conversar com o paciente, recolher informação clínica gradualmente e manter uma conversa natural.
Deves usar as regras recuperadas da base de conhecimento RAG.

Atenção:
- O utilizador só deve ver a fala natural do chatbot.
- Internamente, tens de responder em JSON válido para o Python conseguir atualizar o estado.

Língua obrigatória:
{idioma}

Estado clínico atual:
{json.dumps(estado, ensure_ascii=False, indent=2)}

Último campo perguntado:
{ultimo_campo_perguntado}

Histórico recente:
{historico}

Mensagem atual do paciente:
{mensagem}

Contexto recuperado do RAG:
{contexto_rag}

Campos clínicos disponíveis:
- tosse: sim / nao
- pieira: sim / nao
- dor_garganta: sim / nao
- congestao_nasal: sim / nao
- agravamento: sim / nao
- duracao_prolongada: sim / nao
- doenca_respiratoria_previa: sim / nao
- imunossupressao: sim / nao
- febre: nenhuma / moderada / alta / desconhecida
- dificuldade_respiratoria: nenhuma / ligeira / moderada / grave
- dor_toracica: nenhuma / ligeira / moderada / forte
- limitacao_respiratoria: nenhuma / alguma / significativa

Regras de conversa:
- Responde exclusivamente em {idioma}.
- Podes fazer entre 1 e 3 perguntas clínicas na mesma resposta, se forem necessárias para clarificar sintomas já mencionados.
- Se fizeres várias perguntas, devem ser curtas, claras e diretamente relacionadas com a mensagem do paciente.
- Não faças perguntas desnecessárias.
- Não perguntes sobre sintomas aleatórios se ainda há sintomas mencionados por clarificar.
- Não repitas perguntas já respondidas no estado clínico.
- Não inventes sintomas.
- Só atualizes o estado com informação que o paciente disse explicitamente.
- Se o paciente fizer uma pergunta, por exemplo "o que é pieira?", explica o termo e volta à pergunta clínica original.
- Se o paciente responder de forma natural, como "um bocado", "ligeira", "não muito", interpreta no contexto do último campo perguntado.
- Se existir falta de ar, dor no peito ou febre, dá prioridade a clarificar esses sintomas.
- Se houver sinais graves, podes terminar a recolha e preparar encaminhamento.
- Não faças diagnóstico.
- Não recomendes medicação específica.
- Não escrevas "SNS24-Bot:", "Paciente:", "Assistente:", "Tu:" ou "You:".

Quando deves terminar:
- Só usa terminar = true quando já houver informação suficiente para chamar o Prolog.
- Se ainda faltar clarificar febre, dificuldade respiratória, dor torácica, agravamento, duração ou pieira, continua a conversa.
- Se houver sinal grave claro, podes usar terminar = true.

Formato obrigatório:
Responde APENAS com JSON válido, sem markdown e sem texto fora do JSON.

{{
  "fala": "fala natural do chatbot para o paciente",
  "estado_atualizado": {{
    "tosse": null,
    "pieira": null,
    "dor_garganta": null,
    "congestao_nasal": null,
    "agravamento": null,
    "duracao_prolongada": null,
    "doenca_respiratoria_previa": null,
    "imunossupressao": null,
    "febre": null,
    "dificuldade_respiratoria": null,
    "dor_toracica": null,
    "limitacao_respiratoria": null,
    "notas": null
  }},
  "campos_perguntados": [],
  "terminar": false
}}
"""


def chamar_llm_conversacional(
    vectorstore,
    estado,
    historico,
    mensagem,
    idioma,
    ultimo_campo_perguntado
):
    contexto_rag = recuperar_contexto_rag(
        vectorstore=vectorstore,
        mensagem=mensagem,
        estado=estado,
        k=5
    )

    prompt = construir_prompt_conversacional(
        contexto_rag=contexto_rag,
        estado=estado,
        historico=historico,
        mensagem=mensagem,
        idioma=idioma,
        ultimo_campo_perguntado=ultimo_campo_perguntado
    )

    resposta_bruta = chamar_ollama(prompt, num_predict=450)
    dados = extrair_json(resposta_bruta)

    if dados is None:
        return {
            "fala": "Desculpe, não consegui interpretar bem. Pode repetir de forma simples o que está a sentir?",
            "estado_atualizado": {},
            "campos_perguntados": ultimo_campo_perguntado if isinstance(ultimo_campo_perguntado, list) else [],
            "terminar": False,
            "erro_json": resposta_bruta
        }

    fala = limpar_resposta(dados.get("fala", ""))

    if not fala:
        fala = "Pode explicar um pouco melhor o que está a sentir?"

    return {
        "fala": fala,
        "estado_atualizado": dados.get("estado_atualizado", {}),
        "campos_perguntados": dados.get("campos_perguntados", []),
        "terminar": bool(dados.get("terminar", False)),
        "raw": dados
    }
    
    
# =========================================================
# FLUXO PRINCIPAL
# =========================================================

def main():
    vectorstore = carregar_ou_criar_rag()
    config = escolher_idioma()

    idioma = config["idioma"]
    input_label = config["input_label"]

    nome = input(f"\nSNS24-Bot: {config['mensagem_nome']}\n\n{input_label}: ").strip()

    idade = input(
        f"\nSNS24-Bot: {config['mensagem_idade'].format(nome=nome)}\n\n{input_label}: "
    ).strip()

    estado = criar_estado(nome, idade)

    mensagem_inicial = config["mensagem_sintomas"].format(nome=nome)
    print(f"\nSNS24-Bot: {mensagem_inicial}")

    historico = f"O chatbot perguntou inicialmente: {mensagem_inicial}\n"
    ultimo_campo_perguntado = []

    while True:
        mensagem = input(f"\n{input_label}: ").strip()

        if mensagem.lower() in ["sair", "exit", "quit"]:
            print(f"\nSNS24-Bot: {config['mensagem_saida']}")
            break

        decisao = chamar_llm_conversacional(
            vectorstore=vectorstore,
            estado=estado,
            historico=historico,
            mensagem=mensagem,
            idioma=idioma,
            ultimo_campo_perguntado=ultimo_campo_perguntado
        )
        if DEBUG:
            print("\n[DEBUG DECISAO LLM]")
            print(json.dumps(decisao.get("raw", decisao), ensure_ascii=False, indent=2))
            print("[/DEBUG DECISAO LLM]\n")

        estado = atualizar_estado(
            estado=estado,
            estado_atualizado=decisao.get("estado_atualizado", {})
        )

        fala = decisao.get("fala", "")
        ultimo_campo_perguntado = decisao.get("campos_perguntados", [])
        
        print(f"\nSNS24-Bot: {fala}")

        historico += f"O utilizador disse: {mensagem}\n"
        historico += f"O chatbot respondeu: {fala}\n"

        linhas = historico.strip().split("\n")
        historico = "\n".join(linhas[-10:]) + "\n"

        if DEBUG:
            print("\n[DEBUG ESTADO]")
            print(resumo_estado(estado))
            print("[/DEBUG ESTADO]\n")

        if decisao.get("terminar") is True:
            print("\n[DEBUG]")
            print("O LLM indicou que já existe informação suficiente para chamar o Prolog.")
            print("[/DEBUG]\n")
            break


if __name__ == "__main__":
    main()