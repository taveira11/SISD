import pandas as pd
import random

def one_hot_choice(options, chosen):
    return {opt: 1 if opt == chosen else 0 for opt in options}

def calcular_idade_risco(idade):
    return 1 if idade <= 5 or idade >= 65 else 0

def gerar_caso():
    idade = random.randint(1, 90)
    idade_risco = calcular_idade_risco(idade)

    # Variáveis binárias com probabilidades mais realistas
    tosse = random.choices([0, 1], weights=[0.30, 0.70])[0]
    pieira = random.choices([0, 1], weights=[0.82, 0.18])[0]
    dor_garganta = random.choices([0, 1], weights=[0.45, 0.55])[0]
    congestao_nasal = random.choices([0, 1], weights=[0.40, 0.60])[0]
    agravamento = random.choices([0, 1], weights=[0.87, 0.13])[0]
    duracao_prolongada = random.choices([0, 1], weights=[0.82, 0.18])[0]
    doenca_respiratoria_previa = random.choices([0, 1], weights=[0.84, 0.16])[0]
    imunossupressao = random.choices([0, 1], weights=[0.95, 0.05])[0]

    # Febre
    febre = random.choices(
        ["nenhuma", "moderada", "alta"],
        weights=[0.62, 0.28, 0.10]
    )[0]

    # Dificuldade respiratória
    if pieira == 1:
        dificuldade = random.choices(
            ["nenhuma", "ligeira", "moderada", "grave"],
            weights=[0.12, 0.45, 0.30, 0.13]
        )[0]
    else:
        dificuldade = random.choices(
            ["nenhuma", "ligeira", "moderada", "grave"],
            weights=[0.60, 0.24, 0.12, 0.04]
        )[0]

    # Limitação respiratória dependente da dificuldade
    if dificuldade == "grave":
        limitacao = random.choices(
            ["ligeira", "moderada", "grave"],
            weights=[0.10, 0.35, 0.55]
        )[0]
    elif dificuldade == "moderada":
        limitacao = random.choices(
            ["nenhuma", "ligeira", "moderada", "grave"],
            weights=[0.08, 0.32, 0.45, 0.15]
        )[0]
    elif dificuldade == "ligeira":
        limitacao = random.choices(
            ["nenhuma", "ligeira", "moderada", "grave"],
            weights=[0.45, 0.40, 0.13, 0.02]
        )[0]
    else:
        limitacao = random.choices(
            ["nenhuma", "ligeira", "moderada", "grave"],
            weights=[0.72, 0.22, 0.05, 0.01]
        )[0]

    # Dor torácica dependente da dificuldade e agravamento
    if agravamento == 1 or dificuldade in ["moderada", "grave"]:
        dor = random.choices(
            ["nenhuma", "ligeira", "moderada", "forte"],
            weights=[0.35, 0.30, 0.25, 0.10]
        )[0]
    else:
        dor = random.choices(
            ["nenhuma", "ligeira", "moderada", "forte"],
            weights=[0.70, 0.22, 0.07, 0.01]
        )[0]

    caso = {
        "idade": idade,
        "idade_risco": idade_risco,
        "tosse": tosse,
        "pieira": pieira,
        "dor_garganta": dor_garganta,
        "congestao_nasal": congestao_nasal,
        "agravamento": agravamento,
        "duracao_prolongada": duracao_prolongada,
        "doenca_respiratoria_previa": doenca_respiratoria_previa,
        "imunossupressao": imunossupressao,
    }

    caso.update({
        f"febre_{k}": v for k, v in one_hot_choice(
            ["nenhuma", "moderada", "alta"], febre
        ).items()
    })

    caso.update({
        f"dificuldade_respiratoria_{k}": v for k, v in one_hot_choice(
            ["nenhuma", "ligeira", "moderada", "grave"], dificuldade
        ).items()
    })

    caso.update({
        f"dor_toracica_{k}": v for k, v in one_hot_choice(
            ["nenhuma", "ligeira", "moderada", "forte"], dor
        ).items()
    })

    caso.update({
        f"limitacao_respiratoria_{k}": v for k, v in one_hot_choice(
            ["nenhuma", "ligeira", "moderada", "grave"], limitacao
        ).items()
    })

    caso["encaminhamento"] = atribuir_encaminhamento(caso)
    return caso

def atribuir_encaminhamento(caso):
    # Emergência
    if caso["dificuldade_respiratoria_grave"] == 1:
        return "emergencia"

    if caso["limitacao_respiratoria_grave"] == 1:
        return "emergencia"

    if (
        caso["dor_toracica_forte"] == 1 and
        (
            caso["dificuldade_respiratoria_moderada"] == 1 or
            caso["dificuldade_respiratoria_grave"] == 1 or
            caso["limitacao_respiratoria_moderada"] == 1 or
            caso["limitacao_respiratoria_grave"] == 1
        )
    ):
        return "emergencia"

    # Urgência
    if caso["dificuldade_respiratoria_moderada"] == 1:
        return "urgencia"

    if caso["limitacao_respiratoria_moderada"] == 1:
        return "urgencia"

    if (
        caso["febre_alta"] == 1 and
        (caso["idade_risco"] == 1 or caso["imunossupressao"] == 1)
    ):
        return "urgencia"

    if (
        caso["agravamento"] == 1 and
        (
            caso["pieira"] == 1 or
            caso["dificuldade_respiratoria_ligeira"] == 1 or
            caso["dificuldade_respiratoria_moderada"] == 1
        )
    ):
        return "urgencia"

    # Consulta médica
    if (
        caso["duracao_prolongada"] == 1 or
        caso["doenca_respiratoria_previa"] == 1 or
        caso["imunossupressao"] == 1
    ):
        return "consulta_medica"

    if (
        caso["pieira"] == 1 and
        caso["dificuldade_respiratoria_nenhuma"] == 1
    ):
        return "consulta_medica"

    if (
        caso["febre_alta"] == 1 and
        caso["idade_risco"] == 0 and
        caso["imunossupressao"] == 0 and
        caso["dificuldade_respiratoria_nenhuma"] == 1 and
        caso["limitacao_respiratoria_nenhuma"] == 1
    ):
        return "consulta_medica"

    if (
        caso["febre_moderada"] == 1 and
        caso["tosse"] == 1
    ):
        return "consulta_medica"

    # Autocuidados
    return "autocuidados"

# Gerar base
dados = [gerar_caso() for _ in range(1000)]
df = pd.DataFrame(dados)

pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.max_colwidth", None)

print(df.head(20).to_string())
print("\nDistribuição do encaminhamento:\n")
print(df["encaminhamento"].value_counts())

df.to_csv("triagem_sintetica.csv", index=False)