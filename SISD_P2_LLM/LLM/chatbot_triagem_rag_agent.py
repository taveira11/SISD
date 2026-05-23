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

        fez_pergunta = paciente_fez_pergunta(mensagem)
        respondeu_campo_pendente = mensagem_responde_ao_campo_pendente(
            mensagem,
            ultimo_campo_perguntado
        )

        pergunta_pura = fez_pergunta and not respondeu_campo_pendente

        decisao = chamar_llm_conversacional(
            vectorstore=vectorstore,
            estado=estado,
            historico=historico,
            mensagem=mensagem,
            idioma=idioma,
            ultimo_campo_perguntado=ultimo_campo_perguntado
        )

        if not pergunta_pura:
            decisao = corrigir_decisao_com_mensagem(mensagem, decisao)

            decisao = corrigir_por_contexto_da_pergunta(
                mensagem=mensagem,
                decisao=decisao,
                ultimo_campo_perguntado=ultimo_campo_perguntado
            )

        if DEBUG:
            print("\n[DEBUG DECISAO LLM]")
            print(json.dumps(decisao.get("raw", decisao), ensure_ascii=False, indent=2))
            print("[/DEBUG DECISAO LLM]\n")

        if not pergunta_pura:
            estado = atualizar_estado(
                estado=estado,
                estado_atualizado=decisao.get("estado_atualizado", {})
            )

        campos_falta = campos_obrigatorios_em_falta(estado)

        if campos_falta:
            decisao["terminar"] = False

            if DEBUG:
                print("\n[DEBUG CAMPOS EM FALTA]")
                print(campos_falta)
                print("[/DEBUG CAMPOS EM FALTA]\n")

        if not pergunta_pura:
            decisao = reparar_fala_se_nao_avanca(
                decisao=decisao,
                estado=estado,
                campos_falta=campos_falta,
                idioma=idioma
            )

        if DEBUG:
            print("\n[DEBUG DECISAO APÓS REPARAÇÃO]")
            print(json.dumps(decisao, ensure_ascii=False, indent=2))
            print("[/DEBUG DECISAO APÓS REPARAÇÃO]\n")

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
