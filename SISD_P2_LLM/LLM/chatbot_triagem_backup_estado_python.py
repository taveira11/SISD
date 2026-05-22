from pathlib import Path
import re
import json
import requests

DEBUG = True
# =========================================================
# CONFIGURAÇÃO
# =========================================================

MODELO = "qwen2.5:7b-instruct"
DEBUG = False

BASE_DIR = Path(__file__).resolve().parent
BASE_CONHECIMENTO_PATH = BASE_DIR / "sns24_kb.txt"


# =========================================================
# OLLAMA / BASE DE CONHECIMENTO
# =========================================================

def carregar_base_conhecimento():
    if not BASE_CONHECIMENTO_PATH.exists():
        raise FileNotFoundError(
            f"Não encontrei o ficheiro {BASE_CONHECIMENTO_PATH}."
        )

    return BASE_CONHECIMENTO_PATH.read_text(encoding="utf-8")


def chamar_ollama(prompt, num_predict=260):
    resposta = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": MODELO,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "30m",
            "options": {
                "temperature": 0.1,
                "num_predict": num_predict,
                "num_ctx": 4096,
                "stop": [
                    "\nPaciente:",
                    "\nAssistente:",
                    "\nUtilizador:",
                    "\nSNS24-Bot:",
                    "\nTu:",
                    "\nYou:",
                    "\nResposta adequada:",
                    "\nExemplo"
                ]
            }
        },
        timeout=180
    )

    resposta.raise_for_status()
    return resposta.json()["response"].strip()


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
            "nome": "Before we start, what is your name?",
            "idade": "Thank you, {nome}. How old are you?",
            "sintomas": "Thank you, {nome}. Now, could you tell me what symptoms you are experiencing?",
            "sair": "Thank you. I hope you feel better soon."
        }

    return {
        "idioma": "português de Portugal",
        "input_label": "Tu",
        "nome": "Antes de começarmos, como se chama?",
        "idade": "Obrigado, {nome}. Que idade tem?",
        "sintomas": "Obrigado, {nome}. Agora pode dizer-me o que está a sentir?",
        "sair": "Obrigado. As melhoras."
    }


def criar_estado(nome, idade):
    return {
        "nome": nome,
        "idade": idade,

        "tosse": None,
        "duracao_tosse": None,

        "febre": None,
        "temperatura": None,

        "falta_ar": None,
        "limitacao_respiratoria": None,
        
        "dor_peito": None,

        "dor_garganta": None,
        "dificuldade_engolir": None,

        "congestao_nasal": None,
        "pieira": None,

        "agravamento": None,
        "duracao_prolongada": None,

        "doenca_respiratoria_previa": None,
        "imunossupressao": None,

        "perguntas_feitas": set()
    }


# =========================================================
# UTILITÁRIOS DE TEXTO
# =========================================================

def normalizar(texto):
    texto = texto.lower()
    texto = texto.replace("não", "nao")
    texto = texto.replace("ã", "a").replace("á", "a").replace("à", "a")
    texto = texto.replace("é", "e").replace("ê", "e")
    texto = texto.replace("í", "i")
    texto = texto.replace("ó", "o").replace("ô", "o")
    texto = texto.replace("ú", "u")
    texto = texto.replace("ç", "c")
    return texto


def contem(texto, termos):
    return any(termo in texto for termo in termos)


def resposta_nao(texto):
    texto = normalizar(texto).strip()

    expressoes_nao = [
        "nao",
        "n",
        "no",
        "nope",
        "nao tenho",
        "nao sinto",
        "nao tenho nada",
        "nada",
        "nenhum",
        "nenhuma",
        "de todo",
        "zero",
        "nem por isso",
        "acho que nao",
        "penso que nao"
    ]

    return any(expr in texto for expr in expressoes_nao)


def resposta_sim(texto):
    texto = normalizar(texto).strip()

    if resposta_nao(texto):
        return False

    expressoes_sim = [
        "sim",
        "s",
        "yes",
        "y",
        "tenho",
        "sinto",
        "estou com",
        "ando com",
        "um bocado",
        "um bocadinho",
        "um pouco",
        "ligeiramente",
        "as vezes",
        "às vezes",
        "alguma coisa",
        "algum",
        "alguma",
        "pouco",
        "pouca",
        "mais ou menos"
    ]

    return any(expr in texto for expr in expressoes_sim)


def resposta_ligeira(texto):
    texto = normalizar(texto).strip()

    expressoes_ligeiras = [
        "um bocado",
        "um bocadinho",
        "um pouco",
        "pouco",
        "pouca",
        "ligeiro",
        "ligeira",
        "leve",
        "as vezes",
        "às vezes",
        "nao muito",
        "não muito",
        "mais ou menos"
    ]

    return any(expr in texto for expr in expressoes_ligeiras)


def adicionar_pendente(pendentes, sintoma):
    if sintoma not in pendentes:
        pendentes.append(sintoma)


def remover_pendente(pendentes, sintoma):
    while sintoma in pendentes:
        pendentes.remove(sintoma)


def limpar_resposta(resposta):
    resposta = resposta.strip()

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
            if resposta.startswith(prefixo):
                resposta = resposta[len(prefixo):].strip()
                mudou = True

    return resposta


# =========================================================
# INTERPRETAÇÃO DE SINTOMAS
# =========================================================

def classificar_temperatura(texto):
    texto = texto.replace(",", ".")
    match = re.search(r"\b(3[5-9]|4[0-2])(\.\d)?\b", texto)

    if not match:
        return None, None

    temperatura = float(match.group())

    if temperatura < 37.5:
        return "nenhuma", temperatura
    elif temperatura < 39:
        return "moderada", temperatura
    else:
        return "alta", temperatura


def classificar_intensidade(texto, tipo):
    texto = normalizar(texto)

    if tipo == "falta_ar":
        if contem(texto, ["intensa", "grave", "muito", "muita", "sufoco", "nao consigo respirar"]):
            return "grave"
        if contem(texto, ["moderada", "media", "bastante"]):
            return "moderada"
        if contem(texto, ["ligeira", "leve", "pouca", "um pouco"]):
            return "ligeira"

    if tipo == "dor_peito":
        if contem(texto, ["forte", "intensa", "insuportavel", "muito"]):
            return "forte"
        if contem(texto, ["moderada", "media", "bastante"]):
            return "moderada"
        if contem(texto, ["ligeira", "leve", "pouca", "um pouco"]):
            return "ligeira"

    if tipo == "febre":
        if contem(texto, ["alta", "muita", "muito", "arrepios"]):
            return "alta"
        if contem(texto, ["moderada", "media"]):
            return "moderada"
        if contem(texto, ["baixa", "ligeira", "leve", "pouca"]):
            return "moderada"
    
        if tipo == "limitacao_respiratoria":
            if contem(texto, [
                "significativa",
                "muito",
                "muita",
                "nao consigo andar",
                "não consigo andar",
                "mal consigo andar",
                "nao consigo subir escadas",
                "não consigo subir escadas",
                "tenho de parar",
                "preciso parar",
                "nao consigo fazer atividades",
                "não consigo fazer atividades",
                "limita muito"
            ]):
                return "significativa"

            if contem(texto, [
                "alguma",
                "um pouco",
                "ligeira",
                "leve",
                "canso-me",
                "canso me",
                "custa fazer esforco",
                "custa fazer esforço",
                "limita um pouco",
                "subir escadas custa"
            ]):
                return "alguma"

            if contem(texto, [
                "nenhuma",
                "nao limita",
                "não limita",
                "vida normal",
                "faco tudo",
                "faço tudo",
                "nao tenho limitacao",
                "não tenho limitação"
            ]):
                return "nenhuma"
    return None


def detetar_sintomas(mensagem, estado, pendentes):
    texto = normalizar(mensagem)

    # =====================================================
    # NEGAÇÕES PRIMEIRO
    # =====================================================

    if contem(texto, [
        "nao tenho dor no peito",
        "sem dor no peito",
        "nao sinto dor no peito"
    ]):
        estado["dor_peito"] = "nenhuma"
        remover_pendente(pendentes, "dor_peito")

    if contem(texto, [
        "nao tenho falta de ar",
        "sem falta de ar",
        "respiro bem",
        "nao tenho dificuldade em respirar",
        "sem dificuldade em respirar"
    ]):
        estado["falta_ar"] = "nenhuma"
        estado["limitacao_respiratoria"] = "nenhuma"
        remover_pendente(pendentes, "falta_ar")

    if contem(texto, [
        "nao tenho febre",
        "sem febre"
    ]):
        estado["febre"] = "nenhuma"
        remover_pendente(pendentes, "febre")

    if contem(texto, [
        "nao tenho tosse",
        "sem tosse"
    ]):
        estado["tosse"] = "nao"
        remover_pendente(pendentes, "tosse")

    # =====================================================
    # SINTOMAS POSITIVOS
    # =====================================================

    # Tosse
    if "tosse" in texto:
        if estado["tosse"] is None:
            estado["tosse"] = "sim"

        if estado["duracao_tosse"] is None:
            adicionar_pendente(pendentes, "tosse")

    # Febre
    if "febre" in texto:
        if estado["febre"] is None:
            estado["febre"] = "desconhecida"

        adicionar_pendente(pendentes, "febre")

    febre_classificada, temperatura = classificar_temperatura(texto)

    if febre_classificada is not None:
        estado["febre"] = febre_classificada
        estado["temperatura"] = temperatura
        remover_pendente(pendentes, "febre")

    # Falta de ar / dificuldade respiratória
    if contem(texto, [
        "falta de ar",
        "dificuldade em respirar",
        "respiracao pesada",
        "custa respirar",
        "sufoco",
        "nao consigo respirar",
        "mal consigo respirar"
    ]):
        if estado["falta_ar"] is None:
            estado["falta_ar"] = "desconhecida"

        adicionar_pendente(pendentes, "falta_ar")

    # =====================================================
    # LIMITAÇÃO RESPIRATÓRIA
    # =====================================================

    if contem(texto, [
        "nao consigo andar",
        "mal consigo andar",
        "nao consigo subir escadas",
        "mal consigo subir escadas",
        "tenho de parar",
        "preciso parar",
        "tenho de me sentar",
        "nao consigo fazer atividades",
        "nao consigo fazer as minhas atividades",
        "limita muito",
        "muito limitado",
        "muita limitacao"
    ]):
        estado["limitacao_respiratoria"] = "significativa"

    elif contem(texto, [
        "canso me",
        "canso-me",
        "fico cansado",
        "fico cansada",
        "custa fazer esforco",
        "custa fazer esforço",
        "limita um pouco",
        "alguma limitacao",
        "alguma limitação",
        "subir escadas custa",
        "tenho algum cansaco",
        "tenho algum cansaço"
    ]):
        estado["limitacao_respiratoria"] = "alguma"

    elif contem(texto, [
        "nao limita",
        "nao me limita",
        "vida normal",
        "faco tudo",
        "faço tudo",
        "consigo fazer tudo",
        "nao tenho limitacao",
        "nao tenho limitação"
    ]):
        estado["limitacao_respiratoria"] = "nenhuma"

    # Dor no peito / dor torácica
    if contem(texto, [
        "dor no peito",
        "pressao no peito",
        "aperto no peito",
        "dor toracica"
    ]):
        if estado["dor_peito"] is None:
            estado["dor_peito"] = "desconhecida"

        adicionar_pendente(pendentes, "dor_peito")

    # Dor de garganta
    if contem(texto, [
        "dor de garganta",
        "garganta inflamada",
        "garganta arranhada"
    ]):
        estado["dor_garganta"] = "sim"

        if estado["dificuldade_engolir"] is None:
            adicionar_pendente(pendentes, "dor_garganta")

    # Congestão nasal
    if contem(texto, [
        "nariz entupido",
        "nariz tapado",
        "congestao nasal",
        "corrimento nasal",
        "pingo no nariz"
    ]):
        estado["congestao_nasal"] = "sim"
        adicionar_pendente(pendentes, "congestao_nasal")

    # Pieira
    if contem(texto, [
        "pieira",
        "chiadeira",
        "assobio ao respirar",
        "sibilancia"
    ]):
        estado["pieira"] = "sim"

    # Agravamento
    if contem(texto, [
        "piorou",
        "a piorar",
        "agravou",
        "cada vez pior",
        "esta a piorar"
    ]):
        estado["agravamento"] = "sim"

    if contem(texto, [
        "nao piorou",
        "esta igual",
        "continua igual",
        "melhorou",
        "esta a melhorar"
    ]):
        estado["agravamento"] = "nao"

    # Doença respiratória prévia
    if contem(texto, [
        "asma",
        "bronquite",
        "dpoc",
        "doenca respiratoria",
        "doenca pulmonar"
    ]):
        estado["doenca_respiratoria_previa"] = "sim"

    # Imunossupressão
    if contem(texto, [
        "imunossupressao",
        "imunidade baixa",
        "defesas baixas",
        "imunossuprimido",
        "imunossuprimida"
    ]):
        estado["imunossupressao"] = "sim"


# =========================================================
# RESPOSTA À ÚLTIMA PERGUNTA
# =========================================================

def aplicar_resposta_ultima_pergunta(mensagem, ultima_pergunta, estado, pendentes):
    texto = normalizar(mensagem)

    if ultima_pergunta is None:
        return

    # =====================================================
    # DURAÇÃO DA TOSSE
    # =====================================================

    if ultima_pergunta == "duracao_tosse":
        estado["duracao_tosse"] = mensagem
        remover_pendente(pendentes, "tosse")
        return

    # =====================================================
    # FEBRE
    # =====================================================

    if ultima_pergunta == "temperatura_febre":
        febre_classificada, temperatura = classificar_temperatura(texto)

        if febre_classificada is not None:
            estado["febre"] = febre_classificada
            estado["temperatura"] = temperatura
            remover_pendente(pendentes, "febre")

        elif resposta_nao(texto) or contem(texto, [
            "nao medi",
            "não medi",
            "nao sei",
            "não sei",
            "nao consegui medir",
            "não consegui medir"
        ]):
            estado["febre"] = "desconhecida"
            adicionar_pendente(pendentes, "febre")

        else:
            estado["febre"] = "desconhecida"
            adicionar_pendente(pendentes, "febre")

        return

    if ultima_pergunta == "intensidade_febre":
        intensidade = classificar_intensidade(texto, "febre")

        if intensidade is not None:
            estado["febre"] = intensidade
        else:
            estado["febre"] = "desconhecida"

        remover_pendente(pendentes, "febre")
        return

    if ultima_pergunta == "febre_sim_nao":
        if resposta_nao(texto):
            estado["febre"] = "nenhuma"
            remover_pendente(pendentes, "febre")

        elif resposta_sim(texto):
            estado["febre"] = "desconhecida"
            adicionar_pendente(pendentes, "febre")

        return

    # =====================================================
    # FALTA DE AR / DIFICULDADE RESPIRATÓRIA
    # =====================================================

    if ultima_pergunta == "intensidade_falta_ar":
        intensidade = classificar_intensidade(texto, "falta_ar")

        if intensidade is not None:
            estado["falta_ar"] = intensidade

        elif resposta_ligeira(texto):
            estado["falta_ar"] = "ligeira"

        elif resposta_nao(texto):
            estado["falta_ar"] = "nenhuma"
            estado["limitacao_respiratoria"] = "nenhuma"

        elif resposta_sim(texto):
            estado["falta_ar"] = "moderada"

        else:
            estado["falta_ar"] = "moderada"

        if estado["falta_ar"] == "grave":
            estado["limitacao_respiratoria"] = "significativa"

        remover_pendente(pendentes, "falta_ar")
        return

    if ultima_pergunta == "falta_ar_sim_nao":
        if resposta_ligeira(texto):
            estado["falta_ar"] = "ligeira"
            remover_pendente(pendentes, "falta_ar")

        elif resposta_nao(texto):
            estado["falta_ar"] = "nenhuma"
            estado["limitacao_respiratoria"] = "nenhuma"
            remover_pendente(pendentes, "falta_ar")

        elif resposta_sim(texto):
            estado["falta_ar"] = "desconhecida"
            adicionar_pendente(pendentes, "falta_ar")

        return

    # =====================================================
    # LIMITAÇÃO RESPIRATÓRIA
    # =====================================================

    if ultima_pergunta == "limitacao_respiratoria":
        intensidade = classificar_intensidade(texto, "limitacao_respiratoria")

        if intensidade is not None:
            estado["limitacao_respiratoria"] = intensidade

        elif resposta_ligeira(texto):
            estado["limitacao_respiratoria"] = "alguma"

        elif resposta_nao(texto):
            estado["limitacao_respiratoria"] = "nenhuma"

        elif resposta_sim(texto):
            estado["limitacao_respiratoria"] = "alguma"

        else:
            estado["limitacao_respiratoria"] = "alguma"

        return

    # =====================================================
    # DOR NO PEITO / DOR TORÁCICA
    # =====================================================

    if ultima_pergunta == "intensidade_dor_peito":
        intensidade = classificar_intensidade(texto, "dor_peito")

        if intensidade is not None:
            estado["dor_peito"] = intensidade

        elif resposta_ligeira(texto):
            estado["dor_peito"] = "ligeira"

        elif resposta_nao(texto):
            estado["dor_peito"] = "nenhuma"

        elif resposta_sim(texto):
            estado["dor_peito"] = "moderada"

        else:
            estado["dor_peito"] = "moderada"

        remover_pendente(pendentes, "dor_peito")
        return

    if ultima_pergunta == "dor_peito_sim_nao":
        if resposta_ligeira(texto):
            estado["dor_peito"] = "ligeira"
            remover_pendente(pendentes, "dor_peito")

        elif resposta_nao(texto):
            estado["dor_peito"] = "nenhuma"
            remover_pendente(pendentes, "dor_peito")

        elif resposta_sim(texto):
            estado["dor_peito"] = "desconhecida"
            adicionar_pendente(pendentes, "dor_peito")

        return

    # =====================================================
    # DOR DE GARGANTA / ENGOLIR
    # =====================================================

    if ultima_pergunta == "dificuldade_engolir":
        if resposta_ligeira(texto):
            estado["dificuldade_engolir"] = "ligeira"

        elif resposta_sim(texto):
            estado["dificuldade_engolir"] = "sim"

        elif resposta_nao(texto):
            estado["dificuldade_engolir"] = "nao"

        else:
            estado["dificuldade_engolir"] = mensagem

        remover_pendente(pendentes, "dor_garganta")
        return

    # =====================================================
    # AGRAVAMENTO
    # =====================================================

    if ultima_pergunta == "agravamento":
        if resposta_nao(texto):
            estado["agravamento"] = "nao"

        elif resposta_sim(texto) or contem(texto, [
            "piorou",
            "esta pior",
            "a piorar",
            "agravou",
            "mais forte",
            "cada vez pior"
        ]):
            estado["agravamento"] = "sim"

        return

    # =====================================================
    # DURAÇÃO PROLONGADA
    # =====================================================

    if ultima_pergunta == "duracao_prolongada":
        if resposta_sim(texto):
            estado["duracao_prolongada"] = "sim"

        elif resposta_nao(texto):
            estado["duracao_prolongada"] = "nao"

        elif contem(texto, [
            "4 dias",
            "5 dias",
            "6 dias",
            "7 dias",
            "uma semana",
            "varios dias",
            "mais de 3 dias",
            "mais de tres dias"
        ]):
            estado["duracao_prolongada"] = "sim"

        else:
            estado["duracao_prolongada"] = "nao"

        return

    # =====================================================
    # PIEIRA
    # =====================================================

    if ultima_pergunta == "pieira_sim_nao":
        if resposta_ligeira(texto):
            estado["pieira"] = "sim"

        elif resposta_sim(texto):
            estado["pieira"] = "sim"

        elif resposta_nao(texto):
            estado["pieira"] = "nao"

        return

# =========================================================
# ESCOLHA DA PRÓXIMA PERGUNTA
# =========================================================

def proxima_pergunta(estado, pendentes, idioma):
    pt = idioma == "português de Portugal"

    prioridade_pendentes = [
        "falta_ar",
        "dor_peito",
        "febre",
        "tosse",
        "dor_garganta",
        "congestao_nasal"
    ]

    for sintoma in prioridade_pendentes:
        if sintoma not in pendentes:
            continue

        if sintoma == "falta_ar" and estado["falta_ar"] == "desconhecida":
            return (
                "Essa falta de ar é ligeira, moderada ou intensa?"
                if pt else
                "Is that shortness of breath mild, moderate, or severe?"
            ), "intensidade_falta_ar"

        if sintoma == "dor_peito" and estado["dor_peito"] == "desconhecida":
            return (
                "Essa dor no peito é ligeira, moderada ou forte?"
                if pt else
                "Is that chest pain mild, moderate, or severe?"
            ), "intensidade_dor_peito"

        if sintoma == "febre" and estado["febre"] == "desconhecida":
            if "temperatura_febre" not in estado["perguntas_feitas"]:
                estado["perguntas_feitas"].add("temperatura_febre")
                return (
                    "Qual foi a temperatura que mediu? Se não mediu, diga apenas que não mediu."
                    if pt else
                    "What temperature did you measure? If you did not measure it, just say you did not measure it."
                ), "temperatura_febre"

            return (
                "Diria que a febre é baixa, moderada ou alta?"
                if pt else
                "Would you say the fever feels low, moderate, or high?"
            ), "intensidade_febre"

        if sintoma == "tosse" and estado["duracao_tosse"] is None:
            return (
                "Há quanto tempo tem tosse?"
                if pt else
                "How long have you had the cough?"
            ), "duracao_tosse"

        if sintoma == "dor_garganta" and estado["dificuldade_engolir"] is None:
            return (
                "Tem dificuldade em engolir?"
                if pt else
                "Do you have difficulty swallowing?"
            ), "dificuldade_engolir"

        if sintoma == "congestao_nasal" and estado["febre"] is None:
            return (
                "Tem febre?"
                if pt else
                "Do you have a fever?"
            ), "febre_sim_nao"
    # Se já existe falta de ar ligeira/moderada, avaliar se limita atividades
    if (
        estado["falta_ar"] in ["ligeira", "moderada"]
        and estado["limitacao_respiratoria"] is None
    ):
        return (
            "Essa falta de ar limita as suas atividades normais?"
            if pt else
            "Does that shortness of breath limit your normal activities?"
        ), "limitacao_respiratoria"
        
    # Perguntas gerais, uma de cada vez
    if estado["febre"] is None:
        return (
            "Tem febre?"
            if pt else
            "Do you have a fever?"
        ), "febre_sim_nao"

    if estado["falta_ar"] is None:
        return (
            "Sente falta de ar?"
            if pt else
            "Do you feel shortness of breath?"
        ), "falta_ar_sim_nao"

    if estado["dor_peito"] is None:
        return (
            "Tem dor no peito?"
            if pt else
            "Do you have chest pain?"
        ), "dor_peito_sim_nao"

    if estado["agravamento"] is None:
        return (
            "Os sintomas têm vindo a piorar?"
            if pt else
            "Have the symptoms been getting worse?"
        ), "agravamento"
    
    if estado["duracao_prolongada"] is None:
        return (
            "Os sintomas duram há mais de 3 dias?"
            if pt else
            "Have the symptoms lasted more than 3 days?"
        ), "duracao_prolongada"

    if estado["falta_ar"] in ["ligeira", "moderada"] and estado["pieira"] is None:
        return (
            "Tem pieira ou chiadeira ao respirar?"
            if pt else
            "Do you have wheezing or a whistling sound when breathing?"
        ), "pieira_sim_nao"

    return None, None


# =========================================================
# RESUMO E ORIENTAÇÃO FINAL
# =========================================================

def existe_sintoma_principal(estado):
    return (
        estado["tosse"] == "sim"
        or estado["febre"] not in [None, "nenhuma"]
        or estado["falta_ar"] not in [None, "nenhuma"]
        or estado["dor_peito"] not in [None, "nenhuma"]
        or estado["dor_garganta"] == "sim"
        or estado["congestao_nasal"] == "sim"
    )


def tem_sinal_alarme(estado):
    return estado["falta_ar"] == "grave" or estado["dor_peito"] == "forte"


def pronto_para_orientacao(estado, pendentes):
    # Se houver sinal de alarme, pode orientar imediatamente
    if tem_sinal_alarme(estado):
        return True

    # Se ainda há sintomas pendentes por esclarecer, não pode terminar
    if pendentes:
        return False

    # Febre não pode estar desconhecida
    if estado["febre"] is None or estado["febre"] == "desconhecida":
        return False

    # Falta de ar tem de estar esclarecida
    if estado["falta_ar"] is None or estado["falta_ar"] == "desconhecida":
        return False

    # Se há falta de ar ligeira/moderada, é obrigatório saber se limita atividades
    if estado["falta_ar"] in ["ligeira", "moderada"] and estado["limitacao_respiratoria"] is None:
        return False

    # Dor no peito tem de estar esclarecida
    if estado["dor_peito"] is None or estado["dor_peito"] == "desconhecida":
        return False

    # Agravamento tem de estar esclarecido
    if estado["agravamento"] is None:
        return False

    # Duração tem de estar esclarecida
    if estado["duracao_prolongada"] is None:
        return False

    # Se há falta de ar, convém saber se existe pieira
    if estado["falta_ar"] in ["ligeira", "moderada", "grave"] and estado["pieira"] is None:
        return False

    return existe_sintoma_principal(estado)


def resumo_clinico(estado):
    linhas = [
        f"Nome: {estado['nome']}",
        f"Idade: {estado['idade']}",
        f"Tosse: {estado['tosse']}",
        f"Duração da tosse: {estado['duracao_tosse']}",
        f"Febre: {estado['febre']}",
        f"Temperatura: {estado['temperatura']}",
        f"Falta de ar: {estado['falta_ar']}",
        f"Limitação respiratória: {estado['limitacao_respiratoria']}",
        f"Dor no peito: {estado['dor_peito']}",
        f"Dor de garganta: {estado['dor_garganta']}",
        f"Dificuldade em engolir: {estado['dificuldade_engolir']}",
        f"Congestão nasal: {estado['congestao_nasal']}",
        f"Pieira: {estado['pieira']}",
        f"Agravamento: {estado['agravamento']}",
        f"Doença respiratória prévia: {estado['doenca_respiratoria_previa']}",
        f"Imunossupressão: {estado['imunossupressao']}",
    ]

    return "\n".join(linhas)


def orientacao_simples(estado, idioma):
    pt = idioma == "português de Portugal"

    if estado["falta_ar"] == "grave" or estado["dor_peito"] == "forte":
        return (
            "Pelos sinais descritos, isto pode justificar ajuda urgente. Como é uma simulação académica, não é um diagnóstico, mas numa situação real deveria contactar ajuda médica urgente."
            if pt else
            "Based on the symptoms described, this may require urgent help. This is an academic simulation, not a diagnosis, but in a real situation you should seek urgent medical help."
        )

    if estado["febre"] == "alta" and estado["falta_ar"] in ["moderada", "grave"]:
        return (
            "A combinação de febre alta com falta de ar pode justificar avaliação urgente. Esta é apenas uma simulação académica e não substitui avaliação médica real."
            if pt else
            "High fever combined with shortness of breath may require urgent assessment. This is only an academic simulation and does not replace real medical evaluation."
        )

    if estado["tosse"] == "sim" and estado["duracao_tosse"] is not None:
        return (
            "Pelo que descreveu, pode justificar vigilância e eventual contacto com um profissional de saúde se persistir ou agravar. Esta é apenas uma simulação académica."
            if pt else
            "Based on what you described, monitoring may be appropriate, and you should contact a healthcare professional if symptoms persist or worsen. This is only an academic simulation."
        )

    return (
        "Com a informação recolhida, parece um quadro sem sinais graves imediatos, mas deve vigiar a evolução e procurar apoio se piorar. Esta é apenas uma simulação académica."
        if pt else
        "Based on the information collected, there are no immediate severe signs, but you should monitor symptoms and seek help if they worsen. This is only an academic simulation."
    )


def gerar_orientacao_final(base_conhecimento, estado, idioma):
    resumo = resumo_clinico(estado)

    prompt = f"""
És um assistente académico de triagem respiratória.

Usa a base de conhecimento e o resumo clínico para escrever uma orientação final curta e clara.

Língua obrigatória:
{idioma}

Base de conhecimento:
{base_conhecimento}

Resumo clínico:
{resumo}

Regras:
- Não faças diagnóstico.
- Não recomendes medicação específica.
- Diz que é uma simulação académica.
- Indica o encaminhamento provável: autocuidados, consulta médica, urgência ou emergência.
- Justifica com os sintomas principais.
- Se houver sinais graves, recomenda ajuda urgente.
- Responde em 4 a 6 frases, sem listas.
- Considera apenas sintomas que aparecem no resumo clínico como presentes.
- Não menciones tosse se Tosse estiver None, nao ou não tiver sido referida.
- Não menciones febre se Febre estiver None ou nenhuma.
- Não menciones dor no peito se Dor no peito estiver None ou nenhuma.
- Não menciones falta de ar se Falta de ar estiver None ou nenhuma.
- Não inventes sintomas, duração, agravamento ou fatores de risco.
- Se um campo estiver None, não o uses como motivo clínico.
"""

    try:
        resposta = chamar_ollama(prompt, num_predict=320)
        return limpar_resposta(resposta)
    except Exception:
        return orientacao_simples(estado, idioma)
    
    
def gerar_pergunta_natural(pergunta_base, estado, idioma):
    """
    Usa o LLM apenas para transformar uma pergunta base numa fala natural.
    A lógica clínica continua a ser decidida pelo Python.
    """

    prompt = f"""
És um chatbot académico de triagem respiratória.

A tua tarefa é reescrever a pergunta base de forma natural, empática e conversacional.

Língua obrigatória:
{idioma}

Dados do paciente:
Nome: {estado.get("nome")}
Idade: {estado.get("idade")}

Pergunta base obrigatória:
{pergunta_base}

Regras:
- Mantém exatamente o mesmo objetivo clínico da pergunta base.
- Não acrescentes novas perguntas.
- Faz apenas uma pergunta clínica.
- Não faças diagnóstico.
- Não recomendes medicação.
- Não digas "SNS24-Bot:", "Paciente:", "Assistente:", "Tu:" ou "You:".
- Não inventes sintomas.
- Responde só com a fala natural do chatbot.
- Máximo duas frases curtas.
"""

    try:
        resposta = chamar_ollama(prompt, num_predict=90)
        resposta = limpar_resposta(resposta)

        if not resposta:
            return pergunta_base

        return resposta

    except Exception:
        return pergunta_base

def responder_duvida_sobre_termo(mensagem, ultima_pergunta, estado, idioma):
    """
    Deteta se o utilizador está a pedir explicação sobre um termo clínico.
    Se estiver, o LLM gera a resposta.
    O Python NÃO atualiza o estado clínico nesse turno.
    """

    texto = normalizar(mensagem)

    padroes_duvida = [
        "o que e",
        "o que significa",
        "nao sei o que e",
        "nao percebo",
        "podes explicar",
        "pode explicar",
        "explica",
        "o que quer dizer",
        "what is",
        "what does it mean"
    ]

    if not contem(texto, padroes_duvida):
        return None

    termo = None
    pergunta_original = None

    if "pieira" in texto or ultima_pergunta == "pieira_sim_nao":
        termo = "pieira / chiadeira ao respirar"
        pergunta_original = "Tem pieira ou chiadeira ao respirar?"

    elif "falta de ar" in texto or ultima_pergunta in ["falta_ar_sim_nao", "intensidade_falta_ar"]:
        termo = "falta de ar"
        pergunta_original = "Sente falta de ar?"

    elif "dor no peito" in texto or ultima_pergunta in ["dor_peito_sim_nao", "intensidade_dor_peito"]:
        termo = "dor no peito"
        pergunta_original = "Tem dor no peito?"

    elif "limitacao" in texto or ultima_pergunta == "limitacao_respiratoria":
        termo = "limitação respiratória"
        pergunta_original = "Essa falta de ar limita as suas atividades normais?"

    elif "temperatura" in texto or ultima_pergunta == "temperatura_febre":
        termo = "temperatura medida"
        pergunta_original = "Qual foi a temperatura que mediu?"

    else:
        termo = "termo clínico mencionado"
        pergunta_original = "Pode responder de forma simples com aquilo que está a sentir?"

    prompt = f"""
És um chatbot académico de triagem respiratória.

O paciente não respondeu diretamente à pergunta anterior. Em vez disso, pediu uma explicação sobre um termo clínico.

Língua obrigatória:
{idioma}

Nome do paciente:
{estado.get("nome")}

Termo a explicar:
{termo}

Pergunta clínica original:
{pergunta_original}

Regras:
- Explica o termo em linguagem simples.
- Não faças diagnóstico.
- Não recomendes medicação.
- Não inventes sintomas.
- Não atualizes nem assumes a resposta clínica do paciente.
- Depois da explicação, volta à pergunta original.
- Faz apenas uma pergunta clínica no fim.
- Usa português de Portugal se o idioma for português.
- Trata o paciente por "você", não por "tu".
- Não escrevas "SNS24-Bot:", "Paciente:", "Assistente:", "Tu:" ou "You:".
- Responde em no máximo duas frases curtas.

Resposta:
"""

    try:
        resposta = chamar_ollama(prompt, num_predict=120)
        return limpar_resposta(resposta)
    except Exception:
        return pergunta_original
# =========================================================
# FLUXO PRINCIPAL
# =========================================================

def main():
    base_conhecimento = carregar_base_conhecimento()
    config = escolher_idioma()

    idioma = config["idioma"]
    input_label = config["input_label"]

    nome = input(f"\nSNS24-Bot: {config['nome']}\n\n{input_label}: ").strip()

    idade = input(
        f"\nSNS24-Bot: {config['idade'].format(nome=nome)}\n\n{input_label}: "
    ).strip()

    estado = criar_estado(nome, idade)
    pendentes = []
    ultima_pergunta = None

    mensagem_inicial = config["sintomas"].format(nome=nome)
    print(f"\nSNS24-Bot: {mensagem_inicial}")

    while True:
        mensagem = input(f"\n{input_label}: ").strip()

        if mensagem.lower() in ["sair", "exit", "quit"]:
            print(f"\nSNS24-Bot: {config['sair']}")
            break
        duvida = responder_duvida_sobre_termo(
            mensagem=mensagem,
            ultima_pergunta=ultima_pergunta,
            estado=estado,
            idioma=idioma
        )

        if duvida is not None:
            print(f"\nSNS24-Bot: {duvida}")
            continue
        aplicar_resposta_ultima_pergunta(
            mensagem,
            ultima_pergunta,
            estado,
            pendentes
        )

        detetar_sintomas(mensagem, estado, pendentes)

        if DEBUG:
            print("\n[DEBUG estado]")
            debug_estado = estado.copy()
            debug_estado["perguntas_feitas"] = list(debug_estado["perguntas_feitas"])
            print(json.dumps(debug_estado, ensure_ascii=False, indent=2))
            print("Pendentes:", pendentes)
            print("[/DEBUG]\n")

        if pronto_para_orientacao(estado, pendentes):
            resposta_final = gerar_orientacao_final(
                base_conhecimento,
                estado,
                idioma
            )

            print(f"\nSNS24-Bot: {resposta_final}")
            break

        pergunta, campo = proxima_pergunta(estado, pendentes, idioma)

        if pergunta is None:
            resposta_final = gerar_orientacao_final(
                base_conhecimento,
                estado,
                idioma
            )

            print(f"\nSNS24-Bot: {resposta_final}")
            break

        ultima_pergunta = campo

        pergunta_natural = gerar_pergunta_natural(
            pergunta_base=pergunta,
            estado=estado,
            idioma=idioma
        )

        print(f"\nSNS24-Bot: {pergunta_natural}")


if __name__ == "__main__":
    main()