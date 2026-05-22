from pathlib import Path
import requests
import json

# =========================================================
# CONFIGURAÇÃO
# =========================================================

MODELO = "qwen2.5:7b-instruct"

BASE_DIR = Path(__file__).resolve().parent
BASE_CONHECIMENTO_PATH = BASE_DIR / "sns24_kb.txt"


# =========================================================
# FUNÇÕES BASE
# =========================================================

def carregar_base_conhecimento():
    if not BASE_CONHECIMENTO_PATH.exists():
        raise FileNotFoundError(
            f"Não encontrei o ficheiro {BASE_CONHECIMENTO_PATH}."
        )

    return BASE_CONHECIMENTO_PATH.read_text(encoding="utf-8")


def chamar_ollama(prompt):
    resposta = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": MODELO,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "30m",
            "options": {
                "temperature": 0.1,
                "num_predict": 120,
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


def limpar_resposta(resposta):
    prefixos = [
        "SNS24-Bot:",
        "Assistente:",
        "Paciente:",
        "Utilizador:",
        "Tu:",
        "You:",
        "Bot:"
        "Resposta:"
    ]

    resposta = resposta.strip()

    mudou = True
    while mudou:
        mudou = False
        for prefixo in prefixos:
            if resposta.startswith(prefixo):
                resposta = resposta[len(prefixo):].strip()
                mudou = True

    return resposta

def extrair_json(texto):
    try:
        inicio = texto.find("{")
        fim = texto.rfind("}") + 1

        if inicio == -1 or fim <= inicio:
            return None

        return json.loads(texto[inicio:fim])

    except Exception:
        return None
    

def construir_prompt(base_conhecimento, historico, mensagem, idioma, nome, idade, resumo_caso):
    return f"""
Tu és um chatbot académico de triagem respiratória.

A tua fonte principal de regras é a base de conhecimento.
O teu objetivo é conduzir uma conversa natural, com uma pergunta clínica de cada vez, sem repetir perguntas já respondidas.

Língua obrigatória:
{idioma}

Dados fixos do paciente:
Nome: {nome}
Idade: {idade}

MEMÓRIA CLÍNICA ATUAL:
{resumo_caso}

Base de conhecimento:
{base_conhecimento}

Histórico recente apenas para contexto, não para copiar:
{historico}

Mensagem atual do paciente:
{mensagem}

Tarefa:
1. Interpreta a mensagem atual do paciente.
2. Atualiza a memória clínica.
3. Decide a próxima pergunta mais útil.
4. Não repitas perguntas já respondidas.
5. Se o paciente respondeu à última pergunta, guarda essa resposta na memória.

Regras obrigatórias:
- Responde exclusivamente em {idioma}.
- Dá apenas a próxima fala do chatbot.
- Faz exatamente uma pergunta clínica por resposta.
- Não juntes duas perguntas na mesma resposta.
- Não uses "ou" para juntar perguntas clínicas diferentes.
- Não copies o histórico.
- Não copies exemplos.
- Não simules falas do paciente.
- Não escrevas "Paciente:", "Assistente:", "SNS24-Bot:", "Tu:" ou "You:".
- Não repitas literalmente a mensagem do paciente.
- Não perguntes algo que já esteja respondido na memória clínica.
- Se o paciente já disse que a falta de ar é moderada, não perguntes outra vez a intensidade da falta de ar.
- Se o paciente já disse que a dor de garganta dura há 3 dias, não perguntes outra vez há quanto tempo tem dor de garganta.
- Se o paciente já disse que não tem dor no peito, não perguntes outra vez sobre dor no peito.
- Se existirem sintomas pendentes, volta a eles antes de perguntar por sintomas novos.
- Se a mensagem atual for curta, como "3 dias", "moderada", "sim" ou "não", interpreta como resposta à última pergunta feita.
- Não faças diagnóstico.
- Não recomendes medicação.

Formato obrigatório da resposta:
Responde APENAS com JSON válido, sem markdown e sem texto fora do JSON.

{{
  "resposta": "próxima fala natural do chatbot",
  "resumo_caso": "memória clínica atualizada, curta e clara"
}}

Como escrever o resumo_caso:
- incluir sintomas confirmados;
- incluir sintomas negados;
- incluir duração/intensidade já respondida;
- incluir sintomas pendentes;
- incluir última pergunta respondida.

Exemplo de resumo_caso:
"Nome: Pedro. Idade: 22. Sintomas confirmados: febre, falta de ar moderada, dor de garganta há 3 dias. Sintomas negados: dor no peito. Sintomas pendentes: temperatura da febre. Última pergunta respondida: duração da dor de garganta."

Agora responde apenas com JSON válido.
"""


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
    
    resumo_caso = (
        f"Nome: {nome}. "
        f"Idade: {idade}. "
        "Sintomas confirmados: nenhum. "
        "Sintomas negados: nenhum. "
        "Sintomas pendentes: nenhum. "
        "Última pergunta respondida: nenhuma."
    )
    
    mensagem_inicial = config["sintomas"].format(nome=nome)

    print(f"\nSNS24-Bot: {mensagem_inicial}")

    historico = f"O chatbot perguntou inicialmente: {mensagem_inicial}\n"

    while True:
        mensagem = input(f"\n{input_label}: ").strip()

        if mensagem.lower() in ["sair", "exit", "quit"]:
            print(f"\nSNS24-Bot: {config['sair']}")
            break

        prompt = construir_prompt(
            base_conhecimento=base_conhecimento,
            historico=historico,
            mensagem=mensagem,
            idioma=idioma,
            nome=nome,
            idade=idade,
            resumo_caso=resumo_caso
            )

        resposta_bruta = chamar_ollama(prompt)
        dados = extrair_json(resposta_bruta)

        if dados is not None:
            resposta = limpar_resposta(dados.get("resposta", ""))
            resumo_caso = dados.get("resumo_caso", resumo_caso)
        else:
            resposta = limpar_resposta(resposta_bruta)
        print("\n[DEBUG resumo_caso]")
        print(resumo_caso)
        print("[/DEBUG]\n")
        print(f"\nSNS24-Bot: {resposta}")

        historico += f"O utilizador disse: {mensagem}\n"
        historico += f"O chatbot respondeu: {resposta}\n"

        # Mantém o histórico curto para não ficar lento
        linhas = historico.strip().split("\n")
        historico = "\n".join(linhas[-10:]) + "\n"


if __name__ == "__main__":
    main()