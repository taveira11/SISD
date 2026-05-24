from pathlib import Path
import json
import re
import subprocess
import requests
import unicodedata

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

DEBUG = False

# =========================================================
# OLLAMA
# =========================================================

def chamar_ollama(prompt, num_predict=280):
    try:
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
                    "num_ctx": 3072
                }
            },
            timeout=180
        )

        resposta.raise_for_status()
        return resposta.json()["response"].strip()

    except requests.exceptions.HTTPError as e:
        print("\n[ERRO OLLAMA]")
        print(e)
        if e.response is not None:
            print(e.response.text)
        print("[/ERRO OLLAMA]\n")
        return ""

    except Exception as e:
        print("\n[ERRO OLLAMA]")
        print(e)
        print("[/ERRO OLLAMA]\n")
        return ""


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


def recuperar_contexto_rag(vectorstore, mensagem, estado, k=3):
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
    "idade_risco": ["sim", "nao"],
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

def calcular_idade_risco(idade):
    try:
        idade = int(idade)

        if idade <= 5 or idade >= 65:
            return "sim"

        return "nao"

    except Exception:
        return None

def criar_estado(nome, idade):
    return {
        "nome": nome,
        "idade": idade,
        "idade_risco": calcular_idade_risco(idade),

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
    """
    Atualiza o estado clínico com a informação devolvida pelo LLM.

    Regras importantes:
    - None significa "sem nova informação", logo não altera o estado.
    - O LLM não pode alterar campos calculados pelo Python, como idade_risco.
    - Um valor confirmado não pode voltar para "desconhecida".
    - Um valor confirmado não deve ser substituído por outro valor contraditório,
      a menos que essa correção tenha sido tratada explicitamente antes.
    """

    if not isinstance(estado_atualizado, dict):
        return estado

    for campo, valor in estado_atualizado.items():
        if campo not in estado:
            continue

        # Campos calculados pelo Python não devem ser alterados pelo LLM
        if campo == "idade_risco":
            continue

        valor_normalizado = normalizar_valor(campo, valor)

        # None significa "sem nova informação"
        if valor_normalizado is None:
            continue

        valor_atual = estado.get(campo)

        # Notas só devem ser atualizadas se tiverem conteúdo real
        if campo == "notas":
            if str(valor_normalizado).strip():
                estado["notas"] = str(valor_normalizado).strip()
            continue

        # Proteção 1:
        # não deixar um valor confirmado voltar para "desconhecida"
        if (
            valor_normalizado == "desconhecida"
            and valor_atual not in [None, "", "desconhecida"]
        ):
            continue

        # Proteção 2:
        # não deixar o LLM trocar um valor confirmado por outro contraditório.
        # Exemplo: dificuldade_respiratoria = "ligeira" não pode virar "nenhuma"
        # só porque o paciente disse "não, próxima pergunta".
        if (
            valor_atual not in [None, "", "desconhecida"]
            and valor_normalizado not in [None, "", "desconhecida"]
            and valor_normalizado != valor_atual
        ):
            continue

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
- dificuldade_respiratoria: nenhuma / ligeira / moderada / grave / desconhecida
- dor_toracica: nenhuma / ligeira / moderada / forte / desconhecida
- limitacao_respiratoria: nenhuma / alguma / significativa / desconhecida

Regras de conversa:
- Responde exclusivamente em {idioma}.
- Mantém um tom calmo, profissional e empático.
- Usa português de Portugal quando o idioma for português.
- Não escrevas "SNS24-Bot:", "Paciente:", "Assistente:", "Tu:" ou "You:".
- Não faças diagnóstico.
- Não recomendes medicação específica.
- Não inventes sintomas.
- Interpreta frases equivalentes com o mesmo significado clínico.
- Trata "não" e "nao" como equivalentes.
- Só atualizes o estado com informação explicitamente dita pelo paciente.
- Se o paciente corrigir algo, a correção deve prevalecer.
- A fala deve ser coerente com o estado_atualizado.

Regras de atualização do estado:
- Se o paciente disser que tem febre, mas não der temperatura nem intensidade, usa febre = "desconhecida".
- Se o paciente disser que tem falta de ar ou dificuldade em respirar, mas não der intensidade, usa dificuldade_respiratoria = "desconhecida".
- Se o paciente disser que tem dor no peito ou dor torácica, mas não der intensidade, usa dor_toracica = "desconhecida".
- Se o paciente der uma temperatura numérica válida, atualiza febre corretamente.
- Temperatura entre 37,5 ºC e 38,9 ºC = febre moderada.
- Temperatura igual ou superior a 39 ºC = febre alta.
- Se o paciente disser que não sente nada no peito, que não tem dor no peito, ou equivalente, atualiza dor_toracica = "nenhuma".
- Se o paciente responder a várias perguntas na mesma mensagem, atualiza todos os campos correspondentes.
- Não voltes a perguntar por um campo que o paciente acabou de responder.
- Se o paciente fizer uma pergunta sobre um termo clínico, explica o termo e não assumes que isso confirma o sintoma.
- O campo idade_risco é calculado automaticamente pelo Python a partir da idade.
- Não alteres idade_risco no estado_atualizado.
- Considera idade_risco = "sim" como fator de risco clínico.
- Idade de risco significa idade igual ou inferior a 5 anos ou idade igual ou superior a 65 anos.

Regras de prioridade:
- Dá prioridade a clarificar febre, dificuldade respiratória, limitação respiratória associada à falta de ar e só depois dor torácica, exceto se o paciente mencionar dor no peito espontaneamente.
- Se houver sintomas já mencionados mas ainda não clarificados, pergunta primeiro sobre esses sintomas antes de perguntar sobre sintomas novos.
- Não perguntes sintomas aleatórios se ainda há sintomas mencionados por clarificar.
- Faz apenas UMA pergunta clínica principal por resposta.
- A pergunta deve tentar preencher apenas UM campo clínico em falta.
- campos_perguntados deve conter apenas esse campo.
- Não perguntes vários sintomas na mesma fala, exceto se houver sinal grave claro.

Regras de progressão da conversa:
- Se terminar = false, a fala deve fazer a conversa avançar com pelo menos uma pergunta clínica concreta.
- Frases vagas como "podemos avaliar melhor os seus sintomas", "pode explicar melhor?" ou "vamos continuar a avaliação" podem ser usadas como introdução, mas nunca devem ser a única ação da resposta.
- Não peças apenas autorização para continuar; faz uma pergunta clínica útil.
- Se ainda há febre = "desconhecida", pergunta pela temperatura ou intensidade da febre.
- Se ainda há dificuldade_respiratoria = "desconhecida", pergunta pela intensidade da dificuldade respiratória.
- Se ainda há dor_toracica = "desconhecida", pergunta pela intensidade da dor torácica.
- Como regra geral, faz apenas uma pergunta clínica por resposta.
- Se fizeres uma pergunta clínica, campos_perguntados deve conter apenas esse campo.
- Não coloques vários campos em campos_perguntados, exceto se houver sinal grave claro.
- Não deixes campos_perguntados vazio se a fala contém perguntas clínicas.
- Não repitas literalmente a última fala do chatbot.
- Se o paciente responder apenas "sim" a uma fala vaga anterior, avança para uma pergunta clínica concreta.
- Se dificuldade_respiratoria já estiver preenchida como "ligeira", "moderada" ou "grave" e limitacao_respiratoria ainda estiver null, pergunta se a falta de ar limita atividades normais, como andar ou subir escadas.

Quando deves continuar a conversa:
- Continua a conversa enquanto existirem campos clínicos obrigatórios com valor null.
- Continua a conversa enquanto existirem campos críticos com valor "desconhecida".
- Os campos obrigatórios para o Prolog são: tosse, pieira, dor_garganta, congestao_nasal, agravamento, duracao_prolongada, doenca_respiratoria_previa, imunossupressao, febre, dificuldade_respiratoria, dor_toracica e limitacao_respiratoria.
- Se algum destes campos ainda estiver null, faz uma pergunta clínica útil para o preencher.
- Se febre, dificuldade_respiratoria ou dor_toracica estiverem "desconhecida", pede clarificação antes de terminar.
- Se o paciente fez uma pergunta ou deu uma resposta ambígua, responde à pergunta e continua a recolha.
- Não avances para terminar = true só porque já tens alguns sintomas principais; deves garantir que os campos necessários para o Prolog estão preenchidos.

Quando deves usar terminar = true:
- Usa terminar = true apenas quando todos os campos obrigatórios para o Prolog estiverem preenchidos.
- Usa terminar = true se houver um sinal grave claro, como dificuldade respiratória grave ou dor forte no peito.
- Não uses terminar = true se algum campo obrigatório ainda estiver null.
- Não uses terminar = true se febre, dificuldade_respiratoria ou dor_toracica ainda estiverem "desconhecida".
- Não uses terminar = true se a tua fala ainda estiver a fazer uma pergunta ao paciente.
- Não uses terminar = true se o paciente acabou de fazer uma pergunta sobre um termo clínico.

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
        k=3
    )

    prompt = construir_prompt_conversacional(
        contexto_rag=contexto_rag,
        estado=estado,
        historico=historico,
        mensagem=mensagem,
        idioma=idioma,
        ultimo_campo_perguntado=ultimo_campo_perguntado
    )

    resposta_bruta = chamar_ollama(prompt, num_predict=280)

    if not resposta_bruta:
        return {
            "fala": "Tive um problema técnico ao processar a resposta. Pode repetir a última informação de forma simples?",
            "estado_atualizado": {},
            "campos_perguntados": [],
            "terminar": False,
            "erro_ollama": True
        }
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
    

def corrigir_decisao_com_mensagem(mensagem, decisao):
    """
    Camada leve de validação.
    Não decide o encaminhamento.
    Não substitui o LLM.
    Apenas garante que informação explícita e objetiva do paciente não se perde.
    """

    texto = normalizar_texto_simples(mensagem)

    estado_atualizado = decisao.get("estado_atualizado", {})

    if not isinstance(estado_atualizado, dict):
        estado_atualizado = {}

    # =====================================================
    # FEBRE — validação objetiva
    # =====================================================

    texto_temp = texto.replace(",", ".")
    match = re.search(r"\b(3[5-9]|4[0-2])(\.\d)?\b", texto_temp)

    if match:
        temperatura = float(match.group())

        if temperatura < 37.5:
            estado_atualizado["febre"] = "nenhuma"
        elif temperatura < 39:
            estado_atualizado["febre"] = "moderada"
        else:
            estado_atualizado["febre"] = "alta"

    elif "nao tenho febre" in texto or "sem febre" in texto:
        estado_atualizado["febre"] = "nenhuma"

    elif "febre alta" in texto or "muita febre" in texto:
        estado_atualizado["febre"] = "alta"

    elif "febre moderada" in texto or "febre media" in texto or "febricula" in texto:
        estado_atualizado["febre"] = "moderada"

    elif "febre" in texto and estado_atualizado.get("febre") is None:
        estado_atualizado["febre"] = "desconhecida"

    # =====================================================
    # DOR TORÁCICA / PEITO — negações claras
    # =====================================================

    if (
        "no peito nao sinto nada" in texto
        or "nao sinto nada no peito" in texto
        or "nao tenho dor no peito" in texto
        or "sem dor no peito" in texto
        or "nao tenho dor toracica" in texto
        or "sem dor toracica" in texto
        or "dor toracica nenhuma" in texto
        or "dor no peito nenhuma" in texto
    ):
        estado_atualizado["dor_toracica"] = "nenhuma"

    elif (
        "dor no peito" in texto
        or "dor toracica" in texto
        or "aperto no peito" in texto
        or "pressao no peito" in texto
    ) and estado_atualizado.get("dor_toracica") is None:
        estado_atualizado["dor_toracica"] = "desconhecida"

    # =====================================================
    # DIFICULDADE RESPIRATÓRIA — casos objetivos
    # =====================================================

    if (
        "nao tenho falta de ar" in texto
        or "sem falta de ar" in texto
        or "respiro bem" in texto
        or "nao tenho dificuldade em respirar" in texto
    ):
        estado_atualizado["dificuldade_respiratoria"] = "nenhuma"

    elif (
        "nao consigo respirar" in texto
        or "mal consigo respirar" in texto
        or "estou a sufocar" in texto
        or "sufoco" in texto
    ):
        estado_atualizado["dificuldade_respiratoria"] = "grave"

    elif (
        "falta de ar" in texto
        or "dificuldade em respirar" in texto
        or "dificuldades em respirar" in texto
        or "dificuldade respiratoria" in texto
    ) and estado_atualizado.get("dificuldade_respiratoria") is None:
        estado_atualizado["dificuldade_respiratoria"] = "desconhecida"

    # =====================================================
    # SINTOMAS BINÁRIOS — presença/ausência explícita
    # =====================================================

    # Tosse
    if (
        "nao tenho tosse" in texto
        or "sem tosse" in texto
        or "tosse nao" in texto
    ):
        estado_atualizado["tosse"] = "nao"

    if (
        "tenho tosse" in texto
        or "ando com tosse" in texto
        or "tosse tenho" in texto
        or "tambem tenho tosse" in texto
    ):
        estado_atualizado["tosse"] = "sim"

    # Pieira
    if (
        "nao tenho pieira" in texto
        or "sem pieira" in texto
        or "nao tenho chiadeira" in texto
        or "pieira nao" in texto
        or "chiadeira nao" in texto
    ):
        estado_atualizado["pieira"] = "nao"

    if (
        "tenho pieira" in texto
        or "tenho chiadeira" in texto
        or "assobio ao respirar" in texto
        or "pieira tenho" in texto
        or "chiadeira tenho" in texto
    ):
        estado_atualizado["pieira"] = "sim"

    # Dor de garganta
    if (
        "nao tenho dor de garganta" in texto
        or "sem dor de garganta" in texto
        or "dor de garganta nao" in texto
        or "garganta nao" in texto
    ):
        estado_atualizado["dor_garganta"] = "nao"

    if (
        "tenho dor de garganta" in texto
        or "garganta inflamada" in texto
        or "garganta arranhada" in texto
        or "desconforto na garganta" in texto
        or "dor de garganta tenho" in texto
        or "garganta tenho" in texto
    ):
        estado_atualizado["dor_garganta"] = "sim"

    # Congestão nasal
        # Congestão nasal
    if (
        "nao tenho congestao nasal" in texto
        or "sem congestao nasal" in texto
        or "congestao nasal nao" in texto
        or "congestao nasal nem por isso" in texto
        or "nao tenho nariz entupido" in texto
        or "sem nariz entupido" in texto
        or "nariz entupido nao" in texto
        or "nariz entupido nem por isso" in texto
        or "nariz tapado nao" in texto
        or "nariz tapado nem por isso" in texto
        or "o nariz nao esta entupido" in texto
        or "o nariz nao esta tapado" in texto
    ):
        estado_atualizado["congestao_nasal"] = "nao"

    elif (
        "tenho congestao nasal" in texto
        or "tambem tenho congestao nasal" in texto
        or "congestao nasal tenho" in texto
        or "tenho nariz entupido" in texto
        or "tenho nariz tapado" in texto
        or "nariz entupido" in texto
        or "nariz tapado" in texto
        or "corrimento nasal" in texto
    ):
        estado_atualizado["congestao_nasal"] = "sim"

    # =====================================================
    # AGRAVAMENTO
    # =====================================================

    if (
        "nao tem piorado" in texto
        or "nao piorou" in texto
        or "nao pioraram" in texto
        or "esta igual" in texto
        or "melhorou" in texto
    ):
        estado_atualizado["agravamento"] = "nao"

    elif (
        "tem piorado" in texto
        or "piorou" in texto
        or "pioraram" in texto
        or "agravou" in texto
        or "cada vez pior" in texto
    ):
        estado_atualizado["agravamento"] = "sim"

    # =====================================================
    # DURAÇÃO PROLONGADA
    # =====================================================

    if (
        "mais de 3 dias" in texto
        or "mais de tres dias" in texto
        or "ha 4 dias" in texto
        or "ha quatro dias" in texto
        or "ha 5 dias" in texto
        or "ha cinco dias" in texto
        or "ha uma semana" in texto
        or "uma semana" in texto
    ):
        estado_atualizado["duracao_prolongada"] = "sim"

    elif (
        "ha 1 dia" in texto
        or "ha um dia" in texto
        or "desde ontem" in texto
        or "comecou hoje" in texto
        or "ha 2 dias" in texto
        or "ha dois dias" in texto
        or "ha 3 dias" in texto
        or "ha tres dias" in texto
    ):
        estado_atualizado["duracao_prolongada"] = "nao"

    # =====================================================
    # FATORES DE RISCO
    # =====================================================

    if (
        "nao tenho doenca respiratoria" in texto
        or "nao tenho asma" in texto
        or "sem doenca respiratoria" in texto
        or "nao tenho bronquite" in texto
        or "nao tenho dpoc" in texto
    ):
        estado_atualizado["doenca_respiratoria_previa"] = "nao"

    elif (
        "tenho asma" in texto
        or "tenho bronquite" in texto
        or "tenho dpoc" in texto
        or "tenho doenca respiratoria" in texto
        or "tenho doenca pulmonar" in texto
    ):
        estado_atualizado["doenca_respiratoria_previa"] = "sim"

    if (
        "nao tenho imunidade baixa" in texto
        or "nao tenho defesas baixas" in texto
        or "nao sou imunossuprimido" in texto
        or "nao sou imunossuprimida" in texto
        or "sem imunossupressao" in texto
    ):
        estado_atualizado["imunossupressao"] = "nao"

    elif (
        "tenho imunidade baixa" in texto
        or "tenho defesas baixas" in texto
        or "sou imunossuprimido" in texto
        or "sou imunossuprimida" in texto
        or "tratamento imunossupressor" in texto
    ):
        estado_atualizado["imunossupressao"] = "sim"

    decisao["estado_atualizado"] = estado_atualizado
    return decisao


def campos_obrigatorios_em_falta(estado):
    campos_obrigatorios = [
        "tosse",
        "pieira",
        "dor_garganta",
        "congestao_nasal",
        "agravamento",
        "duracao_prolongada",
        "doenca_respiratoria_previa",
        "imunossupressao",
        "febre",
        "dificuldade_respiratoria",
        "dor_toracica",
        "limitacao_respiratoria"
    ]

    em_falta = []

    for campo in campos_obrigatorios:
        valor = estado.get(campo)

        if valor is None:
            em_falta.append(campo)

        if valor == "desconhecida":
            em_falta.append(campo)

    return em_falta


def pergunta_direcionada_para_campo(campo, estado, idioma):
    pt = idioma == "português de Portugal"

    perguntas_pt = {
        "febre": "Consegue dizer-me que temperatura mediu? Se não mediu, diria que a febre parece moderada ou alta?",
        "dificuldade_respiratoria": "Quando sente falta de ar, diria que é ligeira, moderada ou grave?",
        "dor_toracica": "Tem sentido dor, pressão ou aperto no peito?",
        "limitacao_respiratoria": "Essa falta de ar limita atividades normais, como andar ou subir escadas?",
        "tosse": "Tem tido tosse?",
        "pieira": "Tem sentido pieira, chiadeira ou assobio ao respirar?",
        "dor_garganta": "Tem tido dor de garganta?",
        "congestao_nasal": "Tem tido nariz entupido, nariz tapado ou congestão nasal?",
        "agravamento": "Os sintomas têm vindo a piorar?",
        "duracao_prolongada": "Os sintomas duram há mais de 3 dias?",
        "doenca_respiratoria_previa": "Tem alguma doença respiratória prévia, como asma, bronquite ou DPOC?",
        "imunossupressao": "Tem imunidade baixa, defesas baixas ou faz algum tratamento imunossupressor?"
    }

    perguntas_en = {
        "febre": "Can you tell me what temperature you measured? If you did not measure it, would you say the fever feels moderate or high?",
        "dificuldade_respiratoria": "When you feel shortness of breath, would you say it is mild, moderate, or severe?",
        "dor_toracica": "Have you felt any pain, pressure, or tightness in your chest?",
        "limitacao_respiratoria": "Does that shortness of breath limit normal activities, such as walking or climbing stairs?",
        "tosse": "Have you had a cough?",
        "pieira": "Have you noticed wheezing, whistling, or a high-pitched sound when breathing?",
        "dor_garganta": "Have you had a sore throat?",
        "congestao_nasal": "Have you had a blocked nose, stuffy nose, or nasal congestion?",
        "agravamento": "Have the symptoms been getting worse?",
        "duracao_prolongada": "Have the symptoms lasted more than 3 days?",
        "doenca_respiratoria_previa": "Do you have any previous respiratory condition, such as asthma, bronchitis, or COPD?",
        "imunossupressao": "Do you have low immunity, reduced defenses, or take any immunosuppressive treatment?"
    }

    return perguntas_pt.get(campo) if pt else perguntas_en.get(campo)

def escolher_proximo_campo_para_perguntar(estado, campos_falta):
    """
    Escolhe o próximo campo a perguntar, respeitando a prioridade clínica
    e evitando repetir campos já preenchidos.
    """

    if not campos_falta:
        return None

    # 1. Primeiro clarificar febre, se ainda estiver em falta
    if "febre" in campos_falta:
        return "febre"

    # 2. Depois clarificar intensidade da dificuldade respiratória
    if "dificuldade_respiratoria" in campos_falta:
        return "dificuldade_respiratoria"

    # 3. Se já existe falta de ar confirmada, perguntar limitação respiratória antes da dor torácica
    if (
        "limitacao_respiratoria" in campos_falta
        and estado.get("dificuldade_respiratoria") in ["ligeira", "moderada", "grave"]
    ):
        return "limitacao_respiratoria"

    # 4. Depois perguntar dor torácica
    if "dor_toracica" in campos_falta:
        return "dor_toracica"

    # 5. Sintomas respiratórios principais
    prioridade_restante = [
        "tosse",
        "pieira",
        "dor_garganta",
        "congestao_nasal",
        "agravamento",
        "duracao_prolongada",
        "doenca_respiratoria_previa",
        "imunossupressao",
        "limitacao_respiratoria"
    ]

    for campo in prioridade_restante:
        if campo in campos_falta:
            return campo

    return campos_falta[0]

def reparar_fala_se_nao_avanca(decisao, estado, campos_falta, idioma):
    fala = decisao.get("fala", "")
    fala_lower = fala.lower()
    campos_perguntados = decisao.get("campos_perguntados", [])

    if decisao.get("terminar") is True:
        return decisao

    pt = idioma == "português de Portugal"

    # Garantir que campos_perguntados é lista
    if not isinstance(campos_perguntados, list):
        campos_perguntados = []

    # =====================================================
    # 0. Forçar UMA pergunta por vez
    # =====================================================

    if len(campos_perguntados) > 1:
        # Se o LLM perguntou vários campos, forçamos uma pergunta única.
        # Mantemos a prioridade clínica através dos campos em falta.
        campo = escolher_proximo_campo_para_perguntar(estado, campos_falta)

        if campo is None:
            return decisao

        pergunta = pergunta_direcionada_para_campo(campo, estado, idioma)

        if pergunta:
            decisao["fala"] = pergunta
            decisao["campos_perguntados"] = [campo]
            return decisao

    # =====================================================
    # 1. Remover perguntas sobre campos já preenchidos
    # =====================================================

    if campos_perguntados:
        campo_perguntado = campos_perguntados[0]
        valor_atual = estado.get(campo_perguntado)

        if valor_atual not in [None, "", "desconhecida"]:
            campo = escolher_proximo_campo_para_perguntar(estado, campos_falta)
            pergunta = pergunta_direcionada_para_campo(campo, estado, idioma)

            if pergunta:
                decisao["fala"] = pergunta
                decisao["campos_perguntados"] = [campo]
                return decisao

    # =====================================================
    # 2. Corrigir perguntas vagas sobre febre e falta de ar
    # =====================================================

    febre_desconhecida = estado.get("febre") == "desconhecida"
    falta_ar_desconhecida = estado.get("dificuldade_respiratoria") == "desconhecida"

    pergunta_febre_util = any(
        palavra in fala_lower
        for palavra in [
            "temperatura",
            "termómetro",
            "termometro",
            "moderada",
            "alta",
            "quantos graus"
        ]
    )

    pergunta_falta_ar_util = any(
        palavra in fala_lower
        for palavra in [
            "ligeira",
            "moderada",
            "grave",
            "intensa",
            "intensidade"
        ]
    )

    # Se febre e falta de ar estão desconhecidas, perguntar só uma delas.
    # Pela regra de uma pergunta por vez, começamos pela febre.
    if febre_desconhecida and falta_ar_desconhecida:
        if pt:
            decisao["fala"] = (
                "Consegue dizer-me que temperatura mediu? "
                "Se não mediu, diria que a febre parece moderada ou alta?"
            )
        else:
            decisao["fala"] = (
                "Can you tell me what temperature you measured? "
                "If you did not measure it, would you say the fever feels moderate or high?"
            )

        decisao["campos_perguntados"] = ["febre"]
        return decisao

    # Se só a febre está desconhecida, perguntar de forma útil.
    if febre_desconhecida and not pergunta_febre_util:
        if pt:
            decisao["fala"] = (
                "Consegue dizer-me que temperatura mediu? "
                "Se não mediu, diria que a febre parece moderada ou alta?"
            )
        else:
            decisao["fala"] = (
                "Can you tell me what temperature you measured? "
                "If you did not measure it, would you say the fever feels moderate or high?"
            )

        decisao["campos_perguntados"] = ["febre"]
        return decisao

    # Se só a falta de ar está desconhecida, perguntar de forma útil.
    if falta_ar_desconhecida and not pergunta_falta_ar_util:
        if pt:
            decisao["fala"] = (
                "Quando sente falta de ar, diria que é ligeira, moderada ou grave?"
            )
        else:
            decisao["fala"] = (
                "When you feel shortness of breath, would you say it is mild, moderate, or severe?"
            )

        decisao["campos_perguntados"] = ["dificuldade_respiratoria"]
        return decisao

    # =====================================================
    # 3. Se ainda há campos em falta e o LLM não perguntou nada útil
    # =====================================================

    if campos_falta and not campos_perguntados:
        campo = escolher_proximo_campo_para_perguntar(estado, campos_falta)
        pergunta = pergunta_direcionada_para_campo(campo, estado, idioma)

        if pergunta:
            decisao["fala"] = pergunta
            decisao["campos_perguntados"] = [campo]
            return decisao

    # =====================================================
    # 4. Se a fala é vaga, substituir por pergunta operacional
    # =====================================================

    frases_vagas = [
        "podemos avaliar melhor",
        "vamos avaliar melhor",
        "estado geral",
        "pode explicar melhor",
        "pode descrever melhor",
        "algum momento específico",
        "atividade que piora",
        "principalmente ao se exercitar",
        "principalmente ao exercitar",
        "sente-se confortável",
        "sente algum desconforto"
    ]

    if campos_falta and any(frase in fala_lower for frase in frases_vagas):
        campo = escolher_proximo_campo_para_perguntar(estado, campos_falta)
        pergunta = pergunta_direcionada_para_campo(campo, estado, idioma)

        if pergunta:
            decisao["fala"] = pergunta
            decisao["campos_perguntados"] = [campo]
            return decisao

    return decisao

def normalizar_texto_simples(texto):
    texto = texto.lower().strip()

    substituicoes = {
        "ã": "a",
        "á": "a",
        "à": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c"
    }

    for original, novo in substituicoes.items():
        texto = texto.replace(original, novo)

    return texto

def corrigir_por_contexto_da_pergunta(mensagem, decisao, ultimo_campo_perguntado):
    """
    Corrige respostas curtas usando o campo que o chatbot perguntou no turno anterior.
    Isto evita que o LLM entenda a fala, mas falhe o JSON.
    """

    texto = normalizar_texto_simples(mensagem)

    if ultimo_campo_perguntado is None:
        ultimo_campo_perguntado = []

    estado_atualizado = decisao.get("estado_atualizado", {})

    if not isinstance(estado_atualizado, dict):
        estado_atualizado = {}

    # =====================================================
    # DIFICULDADE RESPIRATÓRIA
    # =====================================================

    if "dificuldade_respiratoria" in ultimo_campo_perguntado:
        if (
            "ligeira" in texto
            or "leve" in texto
            or "um pouco" in texto
            or "um bocado" in texto
            or "nao muito" in texto
        ):
            estado_atualizado["dificuldade_respiratoria"] = "ligeira"

        elif (
            "moderada" in texto
            or "media" in texto
            or "mais ou menos" in texto
            or "bastante" in texto
        ):
            estado_atualizado["dificuldade_respiratoria"] = "moderada"

        elif (
            "grave" in texto
            or "intensa" in texto
            or "muito forte" in texto
            or "sufoco" in texto
            or "nao consigo respirar" in texto
            or "mal consigo respirar" in texto
        ):
            estado_atualizado["dificuldade_respiratoria"] = "grave"

        elif (
            "nao" in texto
            or "nenhuma" in texto
            or "respiro bem" in texto
        ):
            estado_atualizado["dificuldade_respiratoria"] = "nenhuma"

    # =====================================================
    # FEBRE
    # =====================================================

    if "febre" in ultimo_campo_perguntado:
        texto_temp = texto.replace(",", ".")
        match = re.search(r"\b(3[5-9]|4[0-2])(\.\d)?\b", texto_temp)

        if match:
            temperatura = float(match.group())

            if temperatura < 37.5:
                estado_atualizado["febre"] = "nenhuma"
            elif temperatura < 39:
                estado_atualizado["febre"] = "moderada"
            else:
                estado_atualizado["febre"] = "alta"

        elif "alta" in texto or "muita" in texto:
            estado_atualizado["febre"] = "alta"

        elif "moderada" in texto or "media" in texto or "febricula" in texto:
            estado_atualizado["febre"] = "moderada"

        elif "nao" in texto or "sem febre" in texto:
            estado_atualizado["febre"] = "nenhuma"

    # =====================================================
    # DOR TORÁCICA
    # =====================================================

    if "dor_toracica" in ultimo_campo_perguntado:
        if (
            "nao" in texto
            or "nenhuma" in texto
            or "sem dor" in texto
            or "nao sinto nada" in texto
        ):
            estado_atualizado["dor_toracica"] = "nenhuma"

        elif (
            "ligeira" in texto
            or "leve" in texto
            or "um pouco" in texto
            or "um bocadinho" in texto
        ):
            estado_atualizado["dor_toracica"] = "ligeira"

        elif (
            "moderada" in texto
            or "pressao" in texto
            or "aperto" in texto
        ):
            estado_atualizado["dor_toracica"] = "moderada"

        elif (
            "forte" in texto
            or "intensa" in texto
            or "insuportavel" in texto
        ):
            estado_atualizado["dor_toracica"] = "forte"

        # =====================================================
        # LIMITAÇÃO RESPIRATÓRIA
        # =====================================================

    if "limitacao_respiratoria" in ultimo_campo_perguntado:
        if (
            "nao" in texto
            or "nenhuma" in texto
            or "nao limita" in texto
            or "consigo fazer tudo" in texto
            or "vida normal" in texto
        ):
            estado_atualizado["limitacao_respiratoria"] = "nenhuma"

        elif (
            "muito" in texto
            or "bastante" in texto
            or "tenho de parar" in texto
            or "tenho que parar" in texto
            or "nao consigo andar" in texto
            or "nao consigo fazer" in texto
        ):
            estado_atualizado["limitacao_respiratoria"] = "significativa"

        elif (
            "sim" in texto
            or "ja te disse que sim" in texto
            or "limita" in texto
            or "um pouco" in texto
            or "um bocado" in texto
            or "canso" in texto
            or "cansa" in texto
            or "custa" in texto
            or "escadas" in texto
            or "subir escadas" in texto
            or "andar" in texto
        ):
            estado_atualizado["limitacao_respiratoria"] = "alguma"

    # =====================================================
    # CAMPOS BINÁRIOS
    # =====================================================

    campos_binarios = [
        "tosse",
        "pieira",
        "dor_garganta",
        "congestao_nasal",
        "agravamento",
        "duracao_prolongada",
        "doenca_respiratoria_previa",
        "imunossupressao"
    ]

    for campo in campos_binarios:
        if campo in ultimo_campo_perguntado:
            if (
                "sim" in texto
                or "tenho" in texto
                or "tenho tido" in texto
                or "tambem tenho" in texto
            ):
                estado_atualizado[campo] = "sim"

            if (
                "nao" in texto
                or "nunca" in texto
                or "sem" in texto
            ):
                estado_atualizado[campo] = "nao"

    decisao["estado_atualizado"] = estado_atualizado
    return decisao

def paciente_fez_pergunta(mensagem):
    texto = normalizar_texto_simples(mensagem)

    return (
        "?" in mensagem
        or "o que e" in texto
        or "o que significa" in texto
        or "nao percebi" in texto
        or "podes explicar" in texto
        or "pode explicar" in texto
    )
    
def mensagem_responde_ao_campo_pendente(mensagem, ultimo_campo_perguntado):
    """
    Deteta casos em que o paciente faz uma pergunta,
    mas também responde ao campo clínico pendente.
    Exemplo: "sim, porquê?"
    """

    texto = normalizar_texto_simples(mensagem)

    if not ultimo_campo_perguntado:
        return False

    respostas_contextuais = [
        "sim",
        "nao",
        "não",
        "nenhuma",
        "ligeira",
        "leve",
        "moderada",
        "grave",
        "forte",
        "um pouco",
        "um bocado",
        "bastante",
        "muito",
        "nem por isso",
        "tenho",
        "nao tenho",
        "não tenho"
    ]

    return any(resposta in texto for resposta in respostas_contextuais)

def aplicar_correcoes_explicitas_do_utilizador(estado, mensagem):
    """
    Aplica correções explícitas feitas pelo utilizador.
    Isto corrige casos como:
    "eu disse-te que não tinha congestão nasal"
    """

    texto = normalizar_texto_simples(mensagem)

    # Congestão nasal — correções e negações claras
    if (
        "congestao nasal nem por isso" in texto
        or "congestao nasal nao" in texto
        or "nao tenho congestao nasal" in texto
        or "nao tinha congestao nasal" in texto
        or "nao estou com congestao nasal" in texto
        or "nariz nao esta entupido" in texto
        or "nariz nao esta tapado" in texto
        or "nariz nao está entupido" in texto
        or "nariz nao está tapado" in texto
        or "o nariz nao esta entupido" in texto
        or "o nariz nao está entupido" in texto
        or "sem congestao nasal" in texto
        or "eu disse te que nao tinha congestao nasal" in texto
        or "eu disse-te que nao tinha congestao nasal" in texto
    ):
        estado["congestao_nasal"] = "nao"

    if (
        "tenho congestao nasal" in texto
        or "tenho nariz entupido" in texto
        or "nariz entupido" in texto
        or "nariz tapado" in texto
        or "corrimento nasal" in texto
    ) and "nao" not in texto:
        estado["congestao_nasal"] = "sim"

    return estado

# =========================================================
# DETEÇÃO DE RESPOSTAS AMBÍGUAS / VAGAS
# =========================================================
def normalizar_texto(texto):
    """
    Normaliza texto para facilitar comparações:
    - passa para minúsculas
    - remove acentos
    - remove espaços extra
    """
    if texto is None:
        return ""

    texto = str(texto).lower().strip()

    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        char for char in texto
        if unicodedata.category(char) != "Mn"
    )

    texto = " ".join(texto.split())

    return texto

def resposta_ambigua_para_campo(mensagem, campo):
    """
    Deteta respostas vagas quando o chatbot está à espera de
    um valor clínico específico.

    Exemplo:
    - Campo: dificuldade_respiratoria
    - Resposta: "às vezes"
    Neste caso, não se deve assumir ligeira/moderada/grave.
    Deve-se pedir clarificação.
    """

    if not campo:
        return False

    texto = normalizar_texto(mensagem)

    expressoes_vagas = [
        "as vezes",
        "às vezes",
        "um bocado",
        "um pouco",
        "mais ou menos",
        "nao sei",
        "não sei",
        "talvez",
        "depende",
        "so as vezes",
        "só às vezes",
        "de vez em quando",
        "nem sempre"
    ]

    tem_expressao_vaga = any(expr in texto for expr in expressoes_vagas)

    if not tem_expressao_vaga:
        return False

    # Campos que exigem uma intensidade/nível concreto
    campos_com_niveis = {
        "febre": ["nenhuma", "moderada", "alta", "37", "38", "39", "40"],
        "dificuldade_respiratoria": ["nenhuma", "ligeira", "leve", "moderada", "grave"],
        "dor_toracica": ["nenhuma", "ligeira", "leve", "moderada", "forte"],
        "limitacao_respiratoria": ["nenhuma", "alguma", "significativa"]
    }

    if campo in campos_com_niveis:
        valores_validos = campos_com_niveis[campo]
        tem_valor_valido = any(valor in texto for valor in valores_validos)

        # Se a resposta é vaga e não contém valor clínico válido, pedir clarificação
        if not tem_valor_valido:
            return True

    # Campos binários: se for apenas vago e não tiver sim/não explícito, pedir clarificação
    campos_binarios = [
        "tosse",
        "pieira",
        "dor_garganta",
        "congestao_nasal",
        "agravamento",
        "duracao_prolongada",
        "doenca_respiratoria_previa",
        "imunossupressao"
    ]

    if campo in campos_binarios:
        tem_sim = any(expr in texto for expr in ["sim", "tenho", "sinto", "estou com"])
        tem_nao = any(expr in texto for expr in ["nao", "não", "nunca", "sem"])

        if not tem_sim and not tem_nao:
            return True

    return False


def pergunta_clarificacao_para_campo(campo, idioma):
    """
    Gera uma pergunta de clarificação quando a resposta do utilizador
    é demasiado vaga para atualizar o estado clínico.
    """

    pt = idioma == "português de Portugal"

    perguntas_pt = {
        "febre": (
            "Percebo. Para conseguir registar corretamente, mediu a temperatura? "
            "Se sim, quantos graus tinha? Se não mediu, diria que a febre é moderada ou alta?"
        ),
        "dificuldade_respiratoria": (
            "Percebo. Mas em termos de intensidade, diria que a falta de ar é ligeira, moderada ou grave?"
        ),
        "dor_toracica": (
            "Percebo. Em termos de intensidade, diria que a dor no peito é ligeira, moderada ou forte?"
        ),
        "limitacao_respiratoria": (
            "Percebo. Essa falta de ar não limita as atividades, limita alguma coisa, "
            "ou limita de forma significativa?"
        ),
        "tosse": "Para confirmar: tem tosse, sim ou não?",
        "pieira": "Para confirmar: tem pieira, chiadeira ou assobio ao respirar, sim ou não?",
        "dor_garganta": "Para confirmar: tem dor de garganta, sim ou não?",
        "congestao_nasal": "Para confirmar: tem nariz entupido ou congestão nasal, sim ou não?",
        "agravamento": "Para confirmar: os sintomas têm vindo a piorar, sim ou não?",
        "duracao_prolongada": "Para confirmar: os sintomas duram há mais de 3 dias, sim ou não?",
        "doenca_respiratoria_previa": (
            "Para confirmar: tem alguma doença respiratória prévia, como asma, bronquite ou DPOC, sim ou não?"
        ),
        "imunossupressao": (
            "Para confirmar: tem imunidade baixa, defesas baixas ou faz tratamento imunossupressor, sim ou não?"
        )
    }

    perguntas_en = {
        "febre": (
            "I understand. To record this correctly, did you measure your temperature? "
            "If so, what temperature was it? If not, would you say the fever is moderate or high?"
        ),
        "dificuldade_respiratoria": (
            "I understand. In terms of intensity, would you say the shortness of breath is mild, moderate, or severe?"
        ),
        "dor_toracica": (
            "I understand. In terms of intensity, would you say the chest pain is mild, moderate, or strong?"
        ),
        "limitacao_respiratoria": (
            "I understand. Does the shortness of breath not limit activities, limit them somewhat, "
            "or limit them significantly?"
        ),
        "tosse": "To confirm: do you have a cough, yes or no?",
        "pieira": "To confirm: do you have wheezing or whistling when breathing, yes or no?",
        "dor_garganta": "To confirm: do you have a sore throat, yes or no?",
        "congestao_nasal": "To confirm: do you have a blocked or stuffy nose, yes or no?",
        "agravamento": "To confirm: have the symptoms been getting worse, yes or no?",
        "duracao_prolongada": "To confirm: have the symptoms lasted more than 3 days, yes or no?",
        "doenca_respiratoria_previa": (
            "To confirm: do you have any previous respiratory condition, such as asthma, bronchitis or COPD, yes or no?"
        ),
        "imunossupressao": (
            "To confirm: do you have low immunity, reduced defenses or take immunosuppressive treatment, yes or no?"
        )
    }

    if pt:
        return perguntas_pt.get(campo, "Pode esclarecer melhor essa resposta?")
    return perguntas_en.get(campo, "Could you clarify that answer?")

def interpretar_resposta_por_campo_pendente(mensagem, campo):
    """
    Interpreta respostas do utilizador com base no campo que estava pendente.
    Esta função só deve devolver valores clínicos quando a resposta é realmente clara.

    Importante:
    - pedidos de esclarecimento como "não percebi", "explica melhor", "o que significa?"
      nunca devem ser interpretados como resposta clínica negativa;
    - respostas vagas como "às vezes", "um bocado", "não sei bem" também não devem
      preencher automaticamente o estado.
    """

    if not campo:
        return {}

    texto = normalizar_texto(mensagem)

    # ---------------------------------------------------------
    # 0. Bloqueio absoluto para pedidos de esclarecimento
    # ---------------------------------------------------------
    padroes_esclarecimento = [
        "nao percebi",
        "não percebi",
        "nao entendi",
        "não entendi",
        "explica",
        "explica melhor",
        "podes explicar",
        "pode explicar",
        "o que e",
        "o que é",
        "o que significa",
        "que significa",
        "quer dizer",
        "o que quer dizer",
        "nao sei o que e",
        "não sei o que é",
        "nao sei o que significa",
        "não sei o que significa"
    ]

    if any(p in texto for p in padroes_esclarecimento):
        return {}

    # ---------------------------------------------------------
    # 1. Bloqueio para respostas demasiado vagas
    # ---------------------------------------------------------
    respostas_vagas = [
        "as vezes",
        "às vezes",
        "depende",
        "nao sei",
        "não sei",
        "nao sei bem",
        "não sei bem",
        "talvez",
        "mais ou menos",
        "um bocado",
        "um pouco",
        "acho que sim",
        "acho que nao",
        "acho que não",
        "nao tenho a certeza",
        "não tenho a certeza"
    ]

    # Algumas expressões vagas só podem ser aceites em campos onde fazem sentido.
    if any(x in texto for x in respostas_vagas):
        if campo == "limitacao_respiratoria":
            if any(x in texto for x in ["um pouco", "um bocado", "mais ou menos"]):
                return {"limitacao_respiratoria": "alguma"}

        if campo == "dificuldade_respiratoria":
            # "um pouco" pode significar ligeira, mas só se a frase estiver claramente
            # a falar de falta de ar.
            if any(x in texto for x in ["falta de ar", "respirar", "respiração", "respiracao"]):
                if any(x in texto for x in ["um pouco", "um bocado"]):
                    return {"dificuldade_respiratoria": "ligeira"}

        # Caso contrário, não assume nada.
        return {}

    # ---------------------------------------------------------
    # 2. Dificuldade respiratória
    # ---------------------------------------------------------
    if campo == "dificuldade_respiratoria":
        if any(x in texto for x in ["grave", "muito forte", "muita falta de ar", "nao consigo respirar", "não consigo respirar"]):
            return {"dificuldade_respiratoria": "grave"}

        if any(x in texto for x in ["moderada", "media", "média", "razoavel", "razoável"]):
            return {"dificuldade_respiratoria": "moderada"}

        if any(x in texto for x in ["ligeira", "leve", "pouca falta de ar"]):
            return {"dificuldade_respiratoria": "ligeira"}

        if any(x in texto for x in ["sem falta de ar", "nao sinto falta de ar", "não sinto falta de ar", "respiro bem"]):
            return {"dificuldade_respiratoria": "nenhuma"}

    # ---------------------------------------------------------
    # 3. Limitação respiratória
    # ---------------------------------------------------------
    if campo == "limitacao_respiratoria":
        if any(x in texto for x in ["significativa", "muito", "bastante", "nao consigo", "não consigo", "impede", "tenho de parar"]):
            return {"limitacao_respiratoria": "significativa"}

        if any(x in texto for x in ["alguma", "limita-me", "limita me", "fico cansado", "tenho de abrandar", "abrandar"]):
            return {"limitacao_respiratoria": "alguma"}

        if any(x in texto for x in ["nao limita", "não limita", "nenhuma", "consigo fazer tudo", "nao me limita", "não me limita"]):
            return {"limitacao_respiratoria": "nenhuma"}

    # ---------------------------------------------------------
    # 4. Dor torácica
    # ---------------------------------------------------------
    if campo == "dor_toracica":
        if any(x in texto for x in ["forte", "insuportavel", "insuportável", "aperto forte", "dor intensa", "muito forte"]):
            return {"dor_toracica": "forte"}

        if any(x in texto for x in ["moderada", "incomoda", "incomoda-me", "não é insuportável", "nao e insuportavel", "não é muito forte"]):
            return {"dor_toracica": "moderada"}

        if any(x in texto for x in ["ligeira", "leve", "fraca", "pequena dor"]):
            return {"dor_toracica": "ligeira"}

        if any(x in texto for x in ["sem dor", "nenhuma dor", "nao tenho dor", "não tenho dor", "nao sinto dor", "não sinto dor"]):
            return {"dor_toracica": "nenhuma"}

    # ---------------------------------------------------------
    # 5. Febre
    # ---------------------------------------------------------
    if campo == "febre":
        if any(x in texto for x in ["39", "40", "alta", "muito alta"]):
            return {"febre": "alta"}

        if any(x in texto for x in ["37", "38", "moderada", "baixa"]):
            return {"febre": "moderada"}

        if any(x in texto for x in ["sem febre", "nao tenho febre", "não tenho febre", "nenhuma febre"]):
            return {"febre": "nenhuma"}

    # ---------------------------------------------------------
    # 6. Campos sim/não
    # ---------------------------------------------------------
    campos_binarios = [
        "tosse",
        "pieira",
        "dor_garganta",
        "congestao_nasal",
        "agravamento",
        "duracao_prolongada",
        "doenca_respiratoria_previa",
        "imunossupressao"
    ]

    if campo in campos_binarios:
        respostas_sim = [
            "sim",
            "tenho",
            "sinto",
            "estou com",
            "tenho tido",
            "costumo ter",
            "piorou",
            "piorei"
        ]

        respostas_nao = [
            "nao",
            "não",
            "nunca",
            "sem",
            "nao tenho",
            "não tenho",
            "nao sinto",
            "não sinto"
        ]

        # Evita que "não percebi" seja apanhado como "não".
        if any(x in texto for x in respostas_sim):
            return {campo: "sim"}

        if any(x in texto for x in respostas_nao):
            return {campo: "nao"}

    return {}

# =========================================================
# ESCLARECIMENTO DE CONCEITOS CLÍNICOS
# =========================================================

def utilizador_pediu_esclarecimento(mensagem):
    """
    Deteta se o utilizador está a pedir uma explicação sobre um conceito.
    Exemplos:
    - "o que é pieira?"
    - "o que quer dizer imunossupressão?"
    - "não percebi"
    - "podes explicar?"
    """

    texto = normalizar_texto(mensagem)

    padroes = [
        "o que e",
        "o que significa",
        "que significa",
        "quer dizer",
        "nao percebi",
        "nao entendi",
        "podes explicar",
        "pode explicar",
        "explica",
        "explicar melhor",
        "o que quer dizer"
    ]

    return any(padrao in texto for padrao in padroes)


def explicacao_campo_clinico(campo, idioma):
    """
    Devolve uma explicação curta para o campo clínico atualmente perguntado.
    Depois da explicação, repete a pergunta original de forma objetiva.
    """

    pt = idioma == "português de Portugal"

    explicacoes_pt = {
        "pieira": (
            "Pieira é uma chiadeira, assobio ou som agudo ao respirar, "
            "normalmente sentido quando o ar passa com dificuldade."
        ),
        "dificuldade_respiratoria": (
            "Dificuldade respiratória significa sentir falta de ar ou dificuldade em respirar. "
            "Pode ser ligeira, moderada ou grave, conforme a intensidade."
        ),
        "limitacao_respiratoria": (
            "Limitação respiratória significa que a falta de ar interfere com atividades normais, "
            "como andar, subir escadas ou fazer pequenos esforços."
        ),
        "dor_toracica": (
            "Dor torácica é dor, pressão, aperto ou desconforto na zona do peito. "
            "Pode ser ligeira, moderada ou forte."
        ),
        "febre": (
            "Febre corresponde a uma temperatura corporal elevada. "
            "Neste sistema, interessa perceber se não tem febre, se é moderada ou se é alta."
        ),
        "tosse": (
            "Tosse é a expulsão súbita de ar pelos pulmões. "
            "Pode ser seca ou com expetoração, mas aqui basta confirmar se tem tosse."
        ),
        "dor_garganta": (
            "Dor de garganta é dor, irritação ou ardor na garganta, especialmente ao engolir."
        ),
        "congestao_nasal": (
            "Congestão nasal significa nariz entupido, dificuldade em respirar pelo nariz "
            "ou sensação de obstrução nasal."
        ),
        "agravamento": (
            "Agravamento significa que os sintomas pioraram desde que começaram, "
            "por exemplo febre mais alta, mais falta de ar ou maior mal-estar."
        ),
        "duracao_prolongada": (
            "Duração prolongada significa que os sintomas se mantêm há vários dias. "
            "Neste sistema, pretende-se saber se duram há mais de 3 dias."
        ),
        "doenca_respiratoria_previa": (
            "Doença respiratória prévia significa já ter uma condição respiratória conhecida, "
            "como asma, bronquite crónica, DPOC ou outra doença dos pulmões."
        ),
        "imunossupressao": (
            "Imunossupressão significa ter as defesas do organismo diminuídas, por doença "
            "ou por medicamentos, como quimioterapia, corticóides prolongados ou imunossupressores."
        )
    }

    repeticoes_pt = {
        "pieira": "Para confirmar: tem sentido chiadeira ou assobio ao respirar?",
        "dificuldade_respiratoria": "Em termos de intensidade, diria que a falta de ar é ligeira, moderada ou grave?",
        "limitacao_respiratoria": "Essa falta de ar não limita atividades, limita alguma coisa, ou limita de forma significativa?",
        "dor_toracica": "Em termos de intensidade, diria que a dor no peito é ligeira, moderada ou forte?",
        "febre": "Mediu a temperatura? Se sim, quantos graus tinha? Se não mediu, diria que a febre é moderada ou alta?",
        "tosse": "Para confirmar: tem tosse, sim ou não?",
        "dor_garganta": "Para confirmar: tem dor de garganta, sim ou não?",
        "congestao_nasal": "Para confirmar: tem nariz entupido ou congestão nasal, sim ou não?",
        "agravamento": "Para confirmar: os sintomas têm vindo a piorar, sim ou não?",
        "duracao_prolongada": "Para confirmar: os sintomas duram há mais de 3 dias, sim ou não?",
        "doenca_respiratoria_previa": "Para confirmar: tem alguma doença respiratória prévia, sim ou não?",
        "imunossupressao": "Para confirmar: tem imunidade baixa ou faz algum tratamento que baixe as defesas, sim ou não?"
    }

    explicacoes_en = {
        "pieira": "Wheezing is a whistling or high-pitched sound when breathing.",
        "dificuldade_respiratoria": "Shortness of breath means feeling difficulty breathing. It may be mild, moderate or severe.",
        "limitacao_respiratoria": "Respiratory limitation means that shortness of breath limits normal activities.",
        "dor_toracica": "Chest pain means pain, pressure, tightness or discomfort in the chest.",
        "febre": "Fever means an elevated body temperature.",
        "tosse": "Cough means a sudden expulsion of air from the lungs.",
        "dor_garganta": "Sore throat means pain, irritation or burning in the throat.",
        "congestao_nasal": "Nasal congestion means a blocked or stuffy nose.",
        "agravamento": "Worsening means the symptoms have become more intense since they started.",
        "duracao_prolongada": "Prolonged duration means the symptoms have lasted for several days.",
        "doenca_respiratoria_previa": "Previous respiratory disease means a known condition such as asthma, chronic bronchitis or COPD.",
        "imunossupressao": "Immunosuppression means having reduced immune defenses due to disease or medication."
    }

    repeticoes_en = {
        "pieira": "To confirm: have you noticed wheezing or a whistling sound when breathing?",
        "dificuldade_respiratoria": "In terms of intensity, would you say the shortness of breath is mild, moderate or severe?",
        "limitacao_respiratoria": "Does the shortness of breath not limit activities, limit them somewhat, or limit them significantly?",
        "dor_toracica": "In terms of intensity, would you say the chest pain is mild, moderate or strong?",
        "febre": "Did you measure your temperature? If so, what temperature was it?",
        "tosse": "To confirm: do you have a cough, yes or no?",
        "dor_garganta": "To confirm: do you have a sore throat, yes or no?",
        "congestao_nasal": "To confirm: do you have a blocked or stuffy nose, yes or no?",
        "agravamento": "To confirm: have the symptoms been getting worse, yes or no?",
        "duracao_prolongada": "To confirm: have the symptoms lasted more than 3 days, yes or no?",
        "doenca_respiratoria_previa": "To confirm: do you have any previous respiratory disease, yes or no?",
        "imunossupressao": "To confirm: do you have low immunity or take medication that lowers your defenses, yes or no?"
    }

    if pt:
        explicacao = explicacoes_pt.get(campo)
        repeticao = repeticoes_pt.get(campo)
    else:
        explicacao = explicacoes_en.get(campo)
        repeticao = repeticoes_en.get(campo)

    if explicacao and repeticao:
        return f"{explicacao} {repeticao}"

    if pt:
        return "Posso esclarecer melhor. Pode responder à pergunta anterior de forma simples?"
    return "I can clarify. Please answer the previous question simply."
# =========================================================
# FLUXO PRINCIPAL
# =========================================================


def normalizar_lista_campos(campos):
    """
    Garante que o campo campos_perguntados vem sempre como lista limpa.
    O LLM continua a decidir a pergunta, mas o Python valida a estrutura.
    """
    if campos is None:
        return []
    if isinstance(campos, str):
        return [campos]
    if isinstance(campos, list):
        return [c for c in campos if isinstance(c, str) and c.strip()]
    return []


def decisao_llm_tem_pergunta_util(decisao, campos_falta):
    """
    Verifica se a resposta do LLM avançou realmente a recolha de informação.
    Não escolhe a conversa por regra; apenas impede repetições ou campos já preenchidos.
    """
    campos = normalizar_lista_campos(decisao.get("campos_perguntados", []))
    if not campos:
        return False
    return any(campo in campos_falta for campo in campos)

def fala_menciona_campos_ja_preenchidos(fala, estado, campo_permitido=None):
    """
    Deteta se a fala do LLM está a voltar a perguntar por campos
    que já têm valor confirmado no estado clínico.

    Isto evita casos como:
    - tosse já está "sim" e o LLM volta a perguntar por tosse;
    - congestao_nasal já está "sim" e o LLM volta a perguntar por nariz entupido;
    - dor_garganta já está preenchida e o LLM volta a pedir confirmação.
    """

    texto = normalizar_texto(fala)

    palavras_por_campo = {
        "tosse": [
            "tosse",
            "tossir"
        ],
        "pieira": [
            "pieira",
            "chiadeira",
            "assobio ao respirar",
            "som ao respirar"
        ],
        "dor_garganta": [
            "dor de garganta",
            "garganta",
            "ardor na garganta"
        ],
        "congestao_nasal": [
            "congestao nasal",
            "nariz entupido",
            "nariz tapado",
            "desconforto nasal",
            "obstrucao nasal"
        ],
        "febre": [
            "febre",
            "temperatura",
            "graus"
        ],
        "dificuldade_respiratoria": [
            "falta de ar",
            "dificuldade em respirar",
            "dificuldade respiratoria"
        ],
        "dor_toracica": [
            "dor no peito",
            "dor toracica",
            "aperto no peito",
            "pressao no peito"
        ],
        "limitacao_respiratoria": [
            "limita",
            "limitacao",
            "atividades normais",
            "andar",
            "subir escadas"
        ],
        "agravamento": [
            "piorar",
            "piorou",
            "agravou",
            "agravamento"
        ],
        "duracao_prolongada": [
            "mais de 3 dias",
            "dura",
            "duracao",
            "ha quantos dias"
        ],
        "doenca_respiratoria_previa": [
            "asma",
            "bronquite",
            "dpoc",
            "doenca respiratoria",
            "doenca pulmonar"
        ],
        "imunossupressao": [
            "imunidade baixa",
            "defesas baixas",
            "imunossupressao",
            "tratamento imunossupressor"
        ]
    }

    for campo, palavras in palavras_por_campo.items():
        if campo == campo_permitido:
            continue

        valor = estado.get(campo)

        if valor not in [None, "", "desconhecida"]:
            if any(palavra in texto for palavra in palavras):
                return True

    return False

def aplicar_fallback_minimo_se_necessario(decisao, estado, campos_falta, idioma):
    """
    Fallback mínimo de segurança.

    O LLM continua a interpretar a conversa e a produzir a fala.
    O Python apenas valida se essa fala é útil, se não repete campos já respondidos
    e se aponta para um campo que ainda falta preencher.

    Se o LLM fizer uma pergunta misturada, por exemplo voltar a perguntar por tosse
    quando tosse já está preenchida, a fala é substituída por uma pergunta limpa
    sobre o próximo campo em falta.
    """

    campos_originais = normalizar_lista_campos(
        decisao.get("campos_perguntados", [])
    )

    decisao["campos_perguntados"] = campos_originais

    # Se já não faltam campos, preparar passagem para o Prolog.
    if not campos_falta:
        decisao["terminar"] = True
        decisao["campos_perguntados"] = []

        decisao["fala"] = (
            "Obrigado. Já recolhi a informação clínica necessária. "
            "Vou agora encaminhar estes dados para o motor de decisão em Prolog, "
            "que será responsável por determinar o encaminhamento final."
        )

        return decisao

    # Se ainda faltam campos, o chatbot não pode terminar.
    decisao["terminar"] = False

    # Manter apenas campos que ainda estão realmente em falta.
    campos_validos = [
        campo for campo in campos_originais
        if campo in campos_falta
    ]

    # Caso ideal:
    # o LLM perguntou exatamente um campo em falta
    # e a fala não mistura campos já preenchidos.
    if len(campos_originais) == 1 and len(campos_validos) == 1:
        campo = campos_validos[0]

        if not fala_menciona_campos_ja_preenchidos(
            fala=decisao.get("fala", ""),
            estado=estado,
            campo_permitido=campo
        ):
            decisao["campos_perguntados"] = [campo]
            return decisao

    # Caso problemático:
    # o LLM perguntou vários campos, perguntou campos já preenchidos,
    # ou a fala mistura informação já respondida.
    if campos_validos:
        campo = escolher_proximo_campo_para_perguntar(
            estado=estado,
            campos_falta=campos_validos
        )
    else:
        campo = escolher_proximo_campo_para_perguntar(
            estado=estado,
            campos_falta=campos_falta
        )

    pergunta = pergunta_direcionada_para_campo(
        campo=campo,
        estado=estado,
        idioma=idioma
    )

    if pergunta:
        decisao["fala"] = pergunta
        decisao["campos_perguntados"] = [campo]

    return decisao

    # Só aqui entra o controlo determinístico: evitar bloqueio da conversa.
    campo = escolher_proximo_campo_para_perguntar(estado, campos_falta)
    pergunta = pergunta_direcionada_para_campo(campo, estado, idioma)

    if pergunta:
        decisao["fala"] = pergunta
        decisao["campos_perguntados"] = [campo]

    return decisao

def finalizar_se_informacao_suficiente(decisao, campos_falta, idioma):
    """
    Garante que, quando já não existem campos clínicos obrigatórios em falta,
    o chatbot deixa de fazer perguntas e prepara a passagem para o motor Prolog.
    """

    if campos_falta:
        return decisao

    if idioma == "en":
        decisao["fala"] = (
            "Thank you. I have now collected the necessary clinical information. "
            "I will now send these data to the Prolog decision engine, which will determine "
            "the final triage recommendation."
        )
    else:
        decisao["fala"] = (
            "Obrigado. Já recolhi a informação clínica necessária. "
            "Vou agora encaminhar estes dados para o motor de decisão em Prolog, "
            "que será responsável por determinar o encaminhamento final."
        )

    decisao["campos_perguntados"] = []
    decisao["terminar"] = True

    return decisao

def mensagem_e_pedido_de_esclarecimento(mensagem):
    """
    Deteta mensagens em que o utilizador está a pedir explicação,
    e não a responder clinicamente à pergunta.

    Exemplo:
    - "como sei se a febre é moderada ou alta?"
    - "o que é febre moderada?"
    - "não percebi"
    - "explica melhor"
    - "o que quer dizer imunossupressão?"
    """

    texto = normalizar_texto(mensagem)

    padroes = [
        "nao percebi",
        "não percebi",
        "nao entendi",
        "não entendi",
        "explica",
        "explica melhor",
        "podes explicar",
        "pode explicar",
        "consegues explicar",
        "consegue explicar",
        "o que e",
        "o que é",
        "o que significa",
        "que significa",
        "quer dizer",
        "o que quer dizer",
        "como assim",
        "como sei",
        "como posso saber",
        "como é que sei",
        "qual e a diferenca",
        "qual é a diferença",
        "diferença entre",
        "nao sei responder",
        "não sei responder"
    ]

    return any(p in texto for p in padroes)
def utilizador_pediu_explicacao_clinica(mensagem):
    """
    Deteta perguntas em que o utilizador está a pedir explicação
    sobre um conceito clínico, e não a responder ao campo pendente.

    Exemplos:
    - "como sei se a febre é alta?"
    - "o que quer dizer imunossupressão?"
    - "não percebi, explica melhor"
    - "qual é a diferença entre moderada e alta?"
    - "o que é pieira?"
    """

    texto = normalizar_texto(mensagem)

    expressoes_explicacao = [
        "como sei",
        "como posso saber",
        "como e que sei",
        "como é que sei",
        "o que e",
        "o que é",
        "o que significa",
        "o que quer dizer",
        "quer dizer",
        "explica",
        "explique",
        "explica melhor",
        "nao percebi",
        "não percebi",
        "nao entendi",
        "não entendi",
        "podes explicar",
        "pode explicar",
        "qual e a diferenca",
        "qual é a diferença",
        "diferenca entre",
        "diferença entre",
        "quando e considerado",
        "quando é considerado"
    ]

    termos_clinicos = [
        "febre",
        "temperatura",
        "moderada",
        "alta",
        "tosse",
        "pieira",
        "falta de ar",
        "dificuldade respiratoria",
        "dificuldade respiratória",
        "dor toracica",
        "dor torácica",
        "dor no peito",
        "limitacao respiratoria",
        "limitação respiratória",
        "imunossupressao",
        "imunossupressão",
        "defesas baixas",
        "imunidade baixa",
        "doenca respiratoria",
        "doença respiratória",
        "congestao nasal",
        "congestão nasal",
        "agravamento",
        "duracao prolongada",
        "duração prolongada"
    ]

    tem_expressao_explicacao = any(expr in texto for expr in expressoes_explicacao)
    tem_termo_clinico = any(termo in texto for termo in termos_clinicos)

    return tem_expressao_explicacao and tem_termo_clinico
import subprocess
import re


def valor_para_prolog(valor, padrao):
    """
    Converte valores do estado Python para átomos Prolog.
    Se o valor estiver vazio, desconhecido ou indefinido, usa um valor padrão seguro.
    """
    if valor is None:
        return padrao

    valor = str(valor).strip().lower()

    valores_invalidos = ["", "null", "none", "desconhecido", "desconhecida", "não sei", "nao sei", "talvez"]

    if valor in valores_invalidos:
        return padrao

    return valor


def limpar_texto_prolog(texto):
    """
    Limpa listas/textos vindos do Prolog para ficarem mais apresentáveis.
    """
    if texto is None:
        return ""

    texto = texto.strip()
    texto = texto.replace("[", "").replace("]", "")
    texto = texto.replace("'", "")
    texto = texto.replace("_", " ")

    return texto


def chamar_prolog_triagem(estado):
    """
    Envia o estado clínico final para o ficheiro api.pl.
    O Prolog é responsável por decidir o encaminhamento final.
    O chatbot/LLM apenas recolhe dados e explica o resultado.
    """

    idade = re.sub(r"\D", "", str(estado.get("idade", "")))
    if idade == "":
        idade = "0"

    valores = {
        "idade": idade,
        "tosse": valor_para_prolog(estado.get("tosse"), "nao"),
        "pieira": valor_para_prolog(estado.get("pieira"), "nao"),
        "dor_garganta": valor_para_prolog(estado.get("dor_garganta"), "nao"),
        "congestao_nasal": valor_para_prolog(estado.get("congestao_nasal"), "nao"),
        "agravamento": valor_para_prolog(estado.get("agravamento"), "nao"),
        "duracao_prolongada": valor_para_prolog(estado.get("duracao_prolongada"), "nao"),
        "doenca_respiratoria_previa": valor_para_prolog(estado.get("doenca_respiratoria_previa"), "nao"),
        "imunossupressao": valor_para_prolog(estado.get("imunossupressao"), "nao"),
        "febre": valor_para_prolog(estado.get("febre"), "nenhuma"),
        "dificuldade_respiratoria": valor_para_prolog(estado.get("dificuldade_respiratoria"), "nenhuma"),
        "dor_toracica": valor_para_prolog(estado.get("dor_toracica"), "nenhuma"),
        "limitacao_respiratoria": valor_para_prolog(estado.get("limitacao_respiratoria"), "nenhuma"),
    }

    comando_prolog = (
        "executar_api("
        f"{valores['idade']},"
        f"{valores['tosse']},"
        f"{valores['pieira']},"
        f"{valores['dor_garganta']},"
        f"{valores['congestao_nasal']},"
        f"{valores['agravamento']},"
        f"{valores['duracao_prolongada']},"
        f"{valores['doenca_respiratoria_previa']},"
        f"{valores['imunossupressao']},"
        f"{valores['febre']},"
        f"{valores['dificuldade_respiratoria']},"
        f"{valores['dor_toracica']},"
        f"{valores['limitacao_respiratoria']}"
        "), halt."
    )

    resultado = subprocess.run(
        ["swipl", "-q", "-s", "../prolog/api.pl", "-g", comando_prolog],
        capture_output=True,
        text=True
    )

    if resultado.returncode != 0:
        return {
            "erro": True,
            "mensagem": resultado.stderr
        }

    linhas = resultado.stdout.strip().splitlines()

    saida = {
        "encaminhamento": "",
        "score": "",
        "faixa": "",
        "motivos": "",
        "outros": ""
    }

    for linha in linhas:
        if linha.startswith("RESULTADO="):
            saida["encaminhamento"] = linha.replace("RESULTADO=", "").strip()
        elif linha.startswith("SCORE="):
            saida["score"] = linha.replace("SCORE=", "").strip()
        elif linha.startswith("FAIXA="):
            saida["faixa"] = linha.replace("FAIXA=", "").strip()
        elif linha.startswith("MOTIVOS="):
            saida["motivos"] = limpar_texto_prolog(linha.replace("MOTIVOS=", "").strip())
        elif linha.startswith("OUTROS="):
            saida["outros"] = limpar_texto_prolog(linha.replace("OUTROS=", "").strip())

    saida["erro"] = False
    return saida

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

        # O utilizador pode fazer uma pergunta clínica sem estar a responder ao campo pendente.
        campo_pendente = ultimo_campo_perguntado[0] if ultimo_campo_perguntado else None

        pediu_esclarecimento = (
            campo_pendente is not None
            and utilizador_pediu_esclarecimento(mensagem)
    )

        if pediu_esclarecimento:
            fala = explicacao_campo_clinico(campo_pendente, idioma)

            print(f"\nSNS24-Bot: {fala}")

            historico += f"O utilizador pediu esclarecimento: {mensagem}\n"
            historico += f"O chatbot explicou o campo {campo_pendente}: {fala}\n"

            linhas = historico.strip().split("\n")
            historico = "\n".join(linhas[-10:]) + "\n"

            if DEBUG:
                print("\n[DEBUG ESCLARECIMENTO]")
                print(f"Campo pendente: {campo_pendente}")
                print(f"Mensagem do utilizador: {mensagem}")
                print("[/DEBUG ESCLARECIMENTO]\n")

            continue

        fez_pergunta = paciente_fez_pergunta(mensagem)

        pedido_explicacao_clinica = utilizador_pediu_explicacao_clinica(mensagem)

        respondeu_campo_pendente = mensagem_responde_ao_campo_pendente(
            mensagem,
            ultimo_campo_perguntado
        )

            # Se o utilizador está a pedir explicação, isso tem prioridade.
        # A mensagem não deve ser tratada como resposta clínica.
        pergunta_pura = pedido_explicacao_clinica or (
            fez_pergunta and not respondeu_campo_pendente
        )

        # Se a resposta ao campo pendente for vaga, não se inventa valor clínico.
        # O chatbot pede esclarecimento e só depois continua.
        campo_pendente = ultimo_campo_perguntado[0] if ultimo_campo_perguntado else None
        if (
            campo_pendente
            and not pergunta_pura
            and resposta_ambigua_para_campo(mensagem, campo_pendente)
        ):
            fala = pergunta_clarificacao_para_campo(campo_pendente, idioma)
            print(f"\nSNS24-Bot: {fala}")

            historico += f"O utilizador disse: {mensagem}\n"
            historico += f"O chatbot pediu esclarecimento: {fala}\n"

            if DEBUG:
                print("\n[DEBUG ESCLARECIMENTO]")
                print(f"Campo pendente: {campo_pendente}")
                print(f"Pergunta do utilizador: {mensagem}")
                print("[/DEBUG ESCLARECIMENTO]\n")

            continue

        # 1. O LLM interpreta a mensagem com apoio do RAG.
        decisao = chamar_llm_conversacional(
            vectorstore=vectorstore,
            estado=estado,
            historico=historico,
            mensagem=mensagem,
            idioma=idioma,
            ultimo_campo_perguntado=ultimo_campo_perguntado
        )

        # =====================================================
# Se for uma pergunta de esclarecimento, o LLM responde,
# mas o estado clínico não é alterado e a conversa não avança.
# =====================================================
        if pergunta_pura:
            fala = decisao.get("fala", "").strip()

            if not fala:
                if idioma == "en":
                    fala = "I can clarify that. Please tell me what part you would like me to explain."
                else:
                    fala = "Posso esclarecer melhor. Diga-me qual é a parte que pretende que explique."

            # Depois de explicar, retoma a pergunta clínica que estava pendente.
            if ultimo_campo_perguntado:
                campo_retomar = ultimo_campo_perguntado[0]
                pergunta_retomar = pergunta_direcionada_para_campo(
                    campo=campo_retomar,
                    estado=estado,
                    idioma=idioma
                )

                if pergunta_retomar:
                    if idioma == "en":
                        fala = f"{fala}\n\nReturning to the previous question: {pergunta_retomar}"
                    else:
                        fala = f"{fala}\n\nVoltando à pergunta anterior: {pergunta_retomar}"

            print(f"\nSNS24-Bot: {fala}")

            historico += f"O utilizador perguntou: {mensagem}\n"
            historico += f"O chatbot esclareceu: {fala}\n"

            linhas = historico.strip().split("\n")
            historico = "\n".join(linhas[-10:]) + "\n"

            if DEBUG:
                print("\n[DEBUG ESTADO — SEM ALTERAÇÃO POR SER PEDIDO DE ESCLARECIMENTO]")
                print(resumo_estado(estado))
                print("[/DEBUG ESTADO]\n")

            continue

        if DEBUG:
            print("\n[DEBUG DECISAO LLM]")
            print(json.dumps(decisao.get("raw", decisao), ensure_ascii=False, indent=2))
            print("[/DEBUG DECISAO LLM]\n")

        # 2. Se for uma pergunta pura do utilizador, não se altera o estado clínico.
        # O LLM deve responder à dúvida e depois retomar a recolha de dados.
        if not pergunta_pura:
            decisao = corrigir_decisao_com_mensagem(mensagem, decisao)

            decisao = corrigir_por_contexto_da_pergunta(
               mensagem=mensagem,
               decisao=decisao,
               ultimo_campo_perguntado=ultimo_campo_perguntado
            )

            estado = atualizar_estado(
                estado=estado,
                estado_atualizado=decisao.get("estado_atualizado", {})
            )

        

        campos_falta = campos_obrigatorios_em_falta(estado)

        if DEBUG:
            print("\n[DEBUG CAMPOS EM FALTA]")
            print(campos_falta)
            print("[/DEBUG CAMPOS EM FALTA]\n")

        # 3. Se já existe informação suficiente, não deixar o LLM fazer mais perguntas.
        decisao = finalizar_se_informacao_suficiente(
         decisao=decisao,
         campos_falta=campos_falta,
         idioma=idioma
        )

        # 4. Fallback mínimo: só entra se ainda faltarem campos e o LLM não avançar a conversa.
        if campos_falta:
         decisao = aplicar_fallback_minimo_se_necessario(
          decisao=decisao,
          estado=estado,
          campos_falta=campos_falta,
          idioma=idioma
     )

        if DEBUG:
            print("\n[DEBUG DECISAO FINAL CONTROLADA]")
            print(json.dumps(decisao, ensure_ascii=False, indent=2))
            print("[/DEBUG DECISAO FINAL CONTROLADA]\n")

        fala = decisao.get("fala", "")
        ultimo_campo_perguntado = normalizar_lista_campos(
            decisao.get("campos_perguntados", [])
        )

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
            resultado_prolog = chamar_prolog_triagem(estado)

            if resultado_prolog.get("erro"):
                print("\nSNS24-Bot: Ocorreu um problema técnico ao consultar o motor de decisão em Prolog.")
                print(resultado_prolog.get("mensagem"))
                break

            encaminhamento = resultado_prolog.get("encaminhamento", "")
            score = resultado_prolog.get("score", "")
            faixa = resultado_prolog.get("faixa", "")
            motivos = resultado_prolog.get("motivos", "")
            outros = resultado_prolog.get("outros", "")

            print("\nSNS24-Bot: Já recolhi a informação clínica necessária e encaminhei os dados para o motor de decisão em Prolog.")
            print("\n============================================================")
            print("RESULTADO FINAL DA TRIAGEM")
            print("============================================================")
            print(f"Encaminhamento recomendado: {encaminhamento}")
            print(f"Índice de gravidade: {score}%")
            print(f"Faixa de risco: {faixa}")

            if motivos:
                print(f"Motivos principais: {motivos}")

            if outros and outros != "":
                print(f"Outros encaminhamentos considerados: {outros}")

            print("\nNota: este resultado é uma simulação académica e não substitui avaliação clínica real.")
            break


if __name__ == "__main__":
    main()
