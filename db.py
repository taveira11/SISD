import pandas as pd
import random

def one_hot_choice(options, chosen):
    return {opt: 1 if opt == chosen else 0 for opt in options}

def calcular_idade_risco(idade):
    return 1 if idade <= 5 or idade >= 65 else 0

def gerar_caso():
    idade = random.randint(1, 90)
    idade_risco = calcular_idade_risco(idade)

    tosse = random.choices([0, 1], weights=[0.35, 0.65])[0]
    pieira = random.choices([0, 1], weights=[0.80, 0.20])[0]
    dor_garganta = random.choices([0, 1], weights=[0.45, 0.55])[0]
    congestao_nasal = random.choices([0, 1], weights=[0.40, 0.60])[0]
    agravamento = random.choices([0, 1], weights=[0.85, 0.15])[0]
    duracao_prolongada = random.choices([0, 1], weights=[0.80, 0.20])[0]
    doenca_respiratoria_previa = random.choices([0, 1], weights=[0.82, 0.18])[0]
    imunossupressao = random.choices([0, 1], weights=[0.93, 0.07])[0]

    doenca_respiratoria_previa = random.choice([0, 1])
    imunossupressao = random.choice([0, 1])

    # Categorias com alguma lógica
    febre = random.choices(
    ["nenhuma", "moderada", "alta"],
    weights=[0.60, 0.30, 0.10]
)[0]

    if pieira == 1:
        dificuldade = random.choices(
            ["nenhuma", "ligeira", "moderada", "grave"],
            weights=[0.15, 0.40, 0.30, 0.15]
        )[0]
    else:
        dificuldade = random.choices(
            ["nenhuma", "ligeira", "moderada", "grave"],
            weights=[0.55, 0.25, 0.15, 0.05]
        )[0]

    if dificuldade == "grave":
        limitacao = random.choices(
            ["ligeira", "moderada", "grave"],
            weights=[0.15, 0.35, 0.50]
        )[0]
    elif dificuldade == "moderada":
        limitacao = random.choices(
            ["nenhuma", "ligeira", "moderada", "grave"],
            weights=[0.10, 0.35, 0.40, 0.15]
        )[0]
    else:
        limitacao = random.choices(
            ["nenhuma", "ligeira", "moderada", "grave"],
            weights=[0.55, 0.30, 0.12, 0.03]
        )[0]

    if agravamento == 1 or dificuldade in ["moderada", "grave"]:
        dor = random.choices(
            ["nenhuma", "ligeira", "moderada", "forte"],
            weights=[0.35, 0.30, 0.25, 0.10]
        )[0]
    else:
        dor = random.choices(
            ["nenhuma", "ligeira", "moderada", "forte"],
            weights=[0.65, 0.25, 0.08, 0.02]
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
        (caso["dificuldade_respiratoria_moderada"] == 1 or
        caso["dificuldade_respiratoria_grave"] == 1 or
        caso["limitacao_respiratoria_moderada"] == 1 or
        caso["limitacao_respiratoria_grave"] == 1)
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
        (caso["pieira"] == 1 or
        caso["dificuldade_respiratoria_ligeira"] == 1 or
        caso["dificuldade_respiratoria_moderada"] == 1)
    ):
        return "urgencia"

    # Consulta médica
    if caso["duracao_prolongada"] == 1:
        return "consulta_medica"

    if caso["doenca_respiratoria_previa"] == 1:
        return "consulta_medica"

    if caso["imunossupressao"] == 1:
        return "consulta_medica"

    if caso["pieira"] == 1:
        return "consulta_medica"

    if caso["febre_moderada"] == 1 or caso["febre_alta"] == 1:
        return "consulta_medica"

    # Autocuidados
    return "autocuidados"

# Gerar base
# Gerar base
dados = [gerar_caso() for _ in range(200)]
df = pd.DataFrame(dados)

pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', None)
pd.set_option('display.max_rows', None)

print(df.to_string())
print(df["encaminhamento"].value_counts())

df.to_csv("triagem_sintetica.csv", index=False)