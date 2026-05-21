import requests
import re
import json

MODELO = "llama3.2:1b"

IDIOMAS = {
    "1": {
        "nome": "português de Portugal",
        "input_label": "Tu",
        "mensagem_inicial": "Olá. Vou fazer algumas perguntas rápidas para perceber melhor os seus sintomas. Pode começar por me dizer o que está a sentir?"
    },
    "2": {
        "nome": "English",
        "input_label": "You",
        "mensagem_inicial": "Hello. I will ask a few quick questions to better understand your symptoms. Could you start by telling me what you are feeling?"
    },
    "3": {
        "nome": "Español",
        "input_label": "Tú",
        "mensagem_inicial": "Hola. Haré algunas preguntas rápidas para entender mejor sus síntomas. ¿Puede empezar diciéndome qué siente?"
    },
    "4": {
        "nome": "Français",
        "input_label": "Vous",
        "mensagem_inicial": "Bonjour. Je vais poser quelques questions rapides pour mieux comprendre vos symptômes. Pouvez-vous commencer par me dire ce que vous ressentez ?"
    },
    "5": {
        "nome": "Mandarin Chinese using Simplified Chinese characters",
        "input_label": "你",
        "mensagem_inicial": "您好。我会问几个简短的问题，以便更好地了解您的症状。您可以先告诉我您现在感觉哪里不舒服吗？"
    }
}

ESTADO_INICIAL = {
    "idade": None,
    "tosse": None,
    "febre": None,
    "dificuldade_respiratoria": None,
    "dor_toracica": None,
    "pieira": None,
    "agravamento": None,
    "duracao_prolongada": None,
    "doenca_respiratoria_previa": None,
    "imunossupressao": None,
    "dor_garganta": None,
    "congestao_nasal": None
}


def classificar_febre_por_temperatura(texto):
    texto = texto.lower().replace(",", ".")

    match = re.search(r"\b(3[5-9]|4[0-2])(\.\d)?\b", texto)

    if not match:
        return None

    temperatura = float(match.group())

    if temperatura < 37.5:
        return "nenhuma"
    elif temperatura < 39:
        return "moderada"
    else:
        return "alta"


def extrair_informacao_clinica(mensagem, idioma):
    """
    Usa o LLM para transformar linguagem natural em informação clínica estruturada.
    A resposta deve ser JSON.
    """

    prompt = f"""
Extrai informação clínica da mensagem do paciente.

A mensagem pode estar em qualquer língua, mas deves devolver APENAS JSON válido.

Campos possíveis:
- idade: número inteiro ou null
- tosse: "sim", "nao" ou null
- febre: "nenhuma", "moderada", "alta", "desconhecida" ou null
- dificuldade_respiratoria: "nenhuma", "ligeira", "moderada", "grave" ou null
- dor_toracica: "nenhuma", "ligeira", "moderada", "forte" ou null
- pieira: "sim", "nao" ou null
- agravamento: "sim", "nao" ou null
- duracao_prolongada: "sim", "nao" ou null
- doenca_respiratoria_previa: "sim", "nao" ou null
- imunossupressao: "sim", "nao" ou null
- dor_garganta: "sim", "nao" ou null
- congestao_nasal: "sim", "nao" ou null

Regras:
- Se o paciente disser uma temperatura:
- abaixo de 37.0 = "nenhuma"
- entre 37.1 e 38.9 = "moderada"
- 39 ou mais = "alta"
- Se o paciente disser que tem febre mas não souber o valor, usa "desconhecida".
- Se a informação não estiver na mensagem, usa null.
- Não inventes sintomas.
- Não escrevas explicações.
- Não uses markdown.
- Devolve apenas JSON.

Mensagem do paciente:
{mensagem}
"""

    resposta = chamar_ollama(prompt)

    try:
        inicio = resposta.find("{")
        fim = resposta.rfind("}") + 1
        json_texto = resposta[inicio:fim]
        dados = json.loads(json_texto)
        return dados
    except Exception:
        return {}


def aplicar_regras_deterministicas(estado, mensagem):
    texto = mensagem.lower()

    # -------------------------
    # Congestão nasal / nariz entupido
    # -------------------------
    if any(expr in texto for expr in [
        "nariz entupido", "pingo no nariz", "nariz tapado",
        "congestão nasal", "congestao nasal", "ranho", "corrimento nasal"
    ]):
        estado["congestao_nasal"] = "sim"

    # -------------------------
    # Tosse
    # -------------------------
    if "tosse" in texto:
        if any(expr in texto for expr in ["não tenho tosse", "nao tenho tosse", "sem tosse"]):
            estado["tosse"] = "nao"
        else:
            estado["tosse"] = "sim"

    # -------------------------
    # Febre
    # -------------------------
    if any(expr in texto for expr in ["não tenho febre", "nao tenho febre", "sem febre"]):
        estado["febre"] = "nenhuma"
    elif "febre" in texto and estado.get("febre") is None:
        estado["febre"] = "desconhecida"

    # -------------------------
    # Dificuldade respiratória
    # -------------------------
    if any(expr in texto for expr in [
        "não tenho dificuldade respiratória",
        "nao tenho dificuldade respiratoria",
        "não tenho falta de ar",
        "nao tenho falta de ar",
        "sem dificuldade respiratória",
        "sem dificuldade respiratoria",
        "sem falta de ar"
    ]):
        estado["dificuldade_respiratoria"] = "nenhuma"

    elif any(expr in texto for expr in [
        "falta de ar", "dificuldade em respirar", "custa respirar",
        "respiração pesada", "respiracao pesada", "respiro fundo",
        "respirar mais fundo", "cansaço a respirar", "cansaco a respirar"
    ]):
        if any(expr in texto for expr in ["muita", "muito", "grave", "não consigo", "nao consigo", "sufoco"]):
            estado["dificuldade_respiratoria"] = "grave"
        elif any(expr in texto for expr in ["moderada", "bastante", "alguma dificuldade"]):
            estado["dificuldade_respiratoria"] = "moderada"
        else:
            estado["dificuldade_respiratoria"] = "ligeira"

    # -------------------------
    # Dor torácica / dor no peito
    # -------------------------
    if any(expr in texto for expr in [
        "não tenho dor no peito",
        "nao tenho dor no peito",
        "sem dor no peito",
        "dor no peito por enquanto não",
        "dor no peito por enquanto nao",
        "dor no peito não",
        "dor no peito nao"
    ]):
        estado["dor_toracica"] = "nenhuma"

    elif any(expr in texto for expr in [
        "dor no peito", "dor torácica", "dor toracica",
        "pressão no peito", "pressao no peito", "aperto no peito"
    ]):
        if any(expr in texto for expr in ["forte", "intensa", "insuportável", "insuportavel"]):
            estado["dor_toracica"] = "forte"
        elif any(expr in texto for expr in ["moderada", "média", "media"]):
            estado["dor_toracica"] = "moderada"
        else:
            estado["dor_toracica"] = "ligeira"

    # -------------------------
    # Dor de garganta
    # -------------------------
    if any(expr in texto for expr in ["dor de garganta", "garganta inflamada", "garganta arranhada"]):
        estado["dor_garganta"] = "sim"

    # -------------------------
    # Pieira
    # -------------------------
    if any(expr in texto for expr in ["pieira", "chiadeira", "assobio ao respirar"]):
        estado["pieira"] = "sim"

    # -------------------------
    # Agravamento
    # -------------------------
    if any(expr in texto for expr in ["piorou", "a piorar", "agravou", "agravamento", "cada vez pior"]):
        estado["agravamento"] = "sim"

    if any(expr in texto for expr in ["não piorou", "nao piorou", "está igual", "esta igual"]):
        estado["agravamento"] = "nao"

    # -------------------------
    # Duração prolongada
    # -------------------------
    if any(expr in texto for expr in [
        "há mais de 3 dias", "ha mais de 3 dias",
        "há uma semana", "ha uma semana",
        "há vários dias", "ha varios dias"
    ]):
        estado["duracao_prolongada"] = "sim"

    return estado


def atualizar_estado_paciente(estado, mensagem, idioma):
    dados_extraidos = extrair_informacao_clinica(mensagem, idioma)

    # Regra determinística extra para temperatura, caso o LLM falhe
    febre_temp = classificar_febre_por_temperatura(mensagem)
    if febre_temp is not None:
        dados_extraidos["febre"] = febre_temp

    for campo, valor in dados_extraidos.items():
        if campo in estado and valor is not None:
            estado[campo] = valor
    estado = aplicar_regras_deterministicas(estado, mensagem)
    return estado


def gerar_resumo_estado(estado):
    preenchidos = {
        campo: valor
        for campo, valor in estado.items()
        if valor is not None
    }

    if not preenchidos:
        return "Ainda não há informação clínica estruturada."

    return json.dumps(preenchidos, ensure_ascii=False, indent=2)


def gerar_proxima_pergunta(estado, idioma):
    """
    Escolhe uma pergunta natural com base no que ainda falta saber.
    Não é questionário rígido: só sugere a próxima pergunta mais útil.
    """

    if estado["dificuldade_respiratoria"] is None:
        return {
            "português de Portugal": "Sente alguma dificuldade em respirar ou falta de ar?",
            "English": "Are you having any difficulty breathing or shortness of breath?",
            "Español": "¿Tiene alguna dificultad para respirar o sensación de falta de aire?",
            "Français": "Avez-vous des difficultés à respirer ou un essoufflement ?",
            "Mandarin Chinese using Simplified Chinese characters": "您有呼吸困难或气短的感觉吗？"
        }.get(idioma, "Sente alguma dificuldade em respirar?")

    if estado["dor_toracica"] is None:
        return {
            "português de Portugal": "Tem alguma dor ou pressão no peito?",
            "English": "Do you have any chest pain or pressure?",
            "Español": "¿Tiene dolor o presión en el pecho?",
            "Français": "Avez-vous une douleur ou une pression dans la poitrine ?",
            "Mandarin Chinese using Simplified Chinese characters": "您有胸痛或胸口压迫感吗？"
        }.get(idioma, "Tem alguma dor no peito?")

    if estado["febre"] in [None, "desconhecida"]:
        return {
            "português de Portugal": "Conseguiu medir a temperatura, ou diria que a febre parece alta?",
            "English": "Have you measured your temperature, or would you say the fever feels high?",
            "Español": "¿Ha medido su temperatura, o diría que la fiebre parece alta?",
            "Français": "Avez-vous mesuré votre température, ou diriez-vous que la fièvre semble élevée ?",
            "Mandarin Chinese using Simplified Chinese characters": "您量过体温吗？或者您觉得发烧严重吗？"
        }.get(idioma, "Conseguiu medir a temperatura?")

    if estado["agravamento"] is None:
        return {
            "português de Portugal": "Os sintomas têm vindo a piorar desde que começaram?",
            "English": "Have the symptoms been getting worse since they started?",
            "Español": "¿Los síntomas han ido empeorando desde que empezaron?",
            "Français": "Les symptômes se sont-ils aggravés depuis leur apparition ?",
            "Mandarin Chinese using Simplified Chinese characters": "症状从开始以来有加重吗？"
        }.get(idioma, "Os sintomas têm vindo a piorar?")

    if estado["idade"] is None:
        return {
            "português de Portugal": "Só para avaliar melhor o risco, que idade tem?",
            "English": "To better assess the risk, how old are you?",
            "Español": "Para valorar mejor el riesgo, ¿qué edad tiene?",
            "Français": "Pour mieux évaluer le risque, quel âge avez-vous ?",
            "Mandarin Chinese using Simplified Chinese characters": "为了更好地评估风险，请问您多大年龄？"
        }.get(idioma, "Que idade tem?")

    return None

def escolher_idioma():
    print("=" * 60)
    print("Chatbot de Triagem Respiratória — Simulação Académica")
    print("=" * 60)
    print("\nSNS24-Bot: Antes de começarmos, em que língua prefere falar?")
    print("1. Português")
    print("2. English")
    print("3. Español")
    print("4. Français")
    print("5. 中文 / Mandarin")

    escolha = input("\nEscolha / Choice: ").strip()

    return IDIOMAS.get(escolha, IDIOMAS["1"])


def chamar_ollama(prompt):
    resposta = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": MODELO,
            "prompt": prompt,
            "stream": False
        },
        timeout=120
    )

    resposta.raise_for_status()
    return resposta.json()["response"]


def construir_prompt(historico, mensagem_utilizador, idioma, estado_paciente, pergunta_sugerida):
    return f"""
És um chatbot académico de triagem respiratória.

Estás a simular uma conversa natural entre um profissional de triagem e um paciente.

Objetivo:
- conversar com o paciente;
- perceber os sintomas aos poucos;
- fazer perguntas de seguimento relevantes;
- no fim, quando existir informação suficiente, indicar um encaminhamento provável.

Importante:
- Isto é uma simulação académica.
- Não és médico.
- Não fazes diagnóstico.
- Não substituis o SNS24, INEM ou avaliação clínica real.

Regras de comportamento:
- Responde exclusivamente na seguinte língua: {idioma}. Não mistures línguas.
- Mantém um tom calmo, profissional e empático.
- Não faças listas enormes de perguntas.
- Faz no máximo 1 ou 2 perguntas por resposta.
- Não perguntes tudo de uma vez.
- Faz a conversa parecer natural.
- Se o paciente disser poucos sintomas, pergunta por sintomas relacionados.
- Dá prioridade a sinais importantes: dificuldade respiratória, dor no peito, febre, agravamento, duração dos sintomas, pieira, idade e doenças respiratórias anteriores.
- Não dês logo um encaminhamento final na primeira resposta, exceto se existirem sinais claramente graves.
- Se houver sinais graves como dor forte no peito, falta de ar intensa, lábios azulados, perda de consciência ou dificuldade respiratória grave, recomenda ajuda urgente.
- Não digas simplesmente que não podes ajudar. Explica que é uma simulação académica e continua a conversa de triagem.
- Responde apenas com a tua fala enquanto assistente.
- Não escrevas "SNS24-Bot:", "Paciente:", "Tu:", "Utilizador:" ou "Assistente:".
- Não repitas a mensagem do paciente.
- Não continues a conversa pelo paciente.
- Não inventes uma nova fala do paciente.
- A tua resposta deve terminar depois da pergunta ou orientação ao utilizador.


Histórico da conversa:
{historico}

Informação clínica já interpretada:
{estado_paciente}

Próxima pergunta sugerida:
{pergunta_sugerida}

Mensagem atual do paciente:
{mensagem_utilizador}

Responde de forma curta, natural e conversacional.
"""


def gerar_mensagem_inicial(idioma):
    prompt = f"""
És um chatbot académico de triagem respiratória.

Cumprimenta o utilizador na seguinte língua: {idioma}.
Explica brevemente que vais fazer algumas perguntas para perceber melhor os sintomas respiratórios.
Não faças ainda perguntas clínicas específicas.
Sê curto, natural e profissional.
"""

    return chamar_ollama(prompt)

def limpar_resposta_bot(resposta, mensagem_utilizador=""):
    resposta = resposta.strip()

    prefixes = [
        "SNS24-Bot:",
        "Assistente:",
        "Paciente:",
        "Utilizador:",
        "Tu:",
        "Bot:"
    ]

    # Remove prefixos repetidos no início
    mudou = True
    while mudou:
        mudou = False
        for prefix in prefixes:
            if resposta.startswith(prefix):
                resposta = resposta[len(prefix):].strip()
                mudou = True

    # Corta se o modelo tentar criar outra fala
    cortes = [
        "\nSNS24-Bot:",
        "\nAssistente:",
        "\nPaciente:",
        "\nUtilizador:",
        "\nTu:",
        "\nBot:"
    ]

    for corte in cortes:
        if corte in resposta:
            resposta = resposta.split(corte)[0].strip()

    # Corta se repetir literalmente a mensagem do utilizador
    if mensagem_utilizador:
        if mensagem_utilizador in resposta:
            resposta = resposta.split(mensagem_utilizador)[0].strip()

    return resposta

def gerar_resposta_controlada(estado, pergunta_sugerida, idioma):
    if idioma == "português de Portugal":
        if pergunta_sugerida:
            return f"Percebo. Obrigado pela informação. {pergunta_sugerida}"

        return (
            "Obrigado pelas respostas. Com a informação que recolhi até agora, "
            "já é possível fazer uma avaliação provisória do caso. "
            "Ainda assim, isto é apenas uma simulação académica e não substitui avaliação médica real."
        )

    if idioma == "English":
        if pergunta_sugerida:
            return f"I understand. Thank you for the information. {pergunta_sugerida}"

        return (
            "Thank you for your answers. Based on the information collected so far, "
            "it is possible to make a provisional assessment. "
            "This is only an academic simulation and does not replace real medical evaluation."
        )

    if idioma == "Español":
        if pergunta_sugerida:
            return f"Entiendo. Gracias por la información. {pergunta_sugerida}"

        return (
            "Gracias por sus respuestas. Con la información recogida hasta ahora, "
            "es posible hacer una evaluación provisional. "
            "Esto es solo una simulación académica y no sustituye una evaluación médica real."
        )

    if idioma == "Français":
        if pergunta_sugerida:
            return f"Je comprends. Merci pour l'information. {pergunta_sugerida}"

        return (
            "Merci pour vos réponses. Avec les informations recueillies jusqu'à présent, "
            "il est possible de faire une évaluation provisoire. "
            "Ceci est seulement une simulation académique et ne remplace pas une évaluation médicale réelle."
        )

    if idioma == "Mandarin Chinese using Simplified Chinese characters":
        if pergunta_sugerida:
            return f"我明白了。谢谢您提供的信息。{pergunta_sugerida}"

        return (
            "谢谢您的回答。根据目前收集到的信息，可以进行一个初步评估。"
            "但这只是学术模拟，不能替代真实的医疗评估。"
        )

    if pergunta_sugerida:
        return f"Percebo. Obrigado pela informação. {pergunta_sugerida}"

    return "Obrigado pelas respostas. Já tenho alguma informação para avaliar o caso."


def main():
    config_idioma = escolher_idioma()
    idioma = config_idioma["nome"]
    input_label = config_idioma["input_label"]
    historico = ""
    estado_paciente = ESTADO_INICIAL.copy()
    
    mensagem_inicial = config_idioma["mensagem_inicial"]
    print(f"\nSNS24-Bot: {mensagem_inicial}")
    historico += f"SNS24-Bot: {mensagem_inicial}\n"

    while True:
        mensagem = input(f"\n{input_label}: ").strip()

        if mensagem.lower() in ["sair", "exit", "quit"]:
            print("\nSNS24-Bot: Obrigado. As melhoras.")
            break

        estado_paciente = atualizar_estado_paciente(estado_paciente, mensagem, idioma)
        pergunta_sugerida = gerar_proxima_pergunta(estado_paciente, idioma)

        resposta_bot = gerar_resposta_controlada(estado_paciente,pergunta_sugerida,idioma)

        print(f"\nSNS24-Bot: {resposta_bot}")

        historico += f"Utilizador: {mensagem}\n"
        historico += f"Assistente: {resposta_bot}\n"


if __name__ == "__main__":
    main()