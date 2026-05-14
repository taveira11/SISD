import pandas as pd
import random


def one_hot_choice(options, chosen):
    return {opt: 1 if opt == chosen else 0 for opt in options}


def calcular_idade_risco(idade):
    return 1 if idade <= 5 or idade >= 65 else 0


def gerar_caso():
    idade = random.randint(0, 90)
    idade_risco = calcular_idade_risco(idade)

    # Variáveis binárias
    tosse = random.choices([0, 1], weights=[0.45, 0.55])[0]
    pieira = random.choices([0, 1], weights=[0.82, 0.18])[0]
    dor_garganta = random.choices([0, 1], weights=[0.45, 0.55])[0]
    congestao_nasal = random.choices([0, 1], weights=[0.40, 0.60])[0]
    agravamento = random.choices([0, 1], weights=[0.86, 0.14])[0]
    duracao_prolongada = random.choices([0, 1], weights=[0.82, 0.18])[0]
    doenca_respiratoria_previa = random.choices([0, 1], weights=[0.84, 0.16])[0]
    imunossupressao = random.choices([0, 1], weights=[0.95, 0.05])[0]

    # Febre
    if agravamento == 1 or duracao_prolongada == 1:
        febre = random.choices(
            ["nenhuma", "moderada", "alta"],
            weights=[0.45, 0.38, 0.17]
        )[0]
    else:
        febre = random.choices(
            ["nenhuma", "moderada", "alta"],
            weights=[0.62, 0.28, 0.10]
        )[0]

    # Dificuldade respiratória
    if pieira == 1:
        dificuldade = random.choices(
            ["nenhuma", "ligeira", "moderada", "grave"],
            weights=[0.10, 0.42, 0.32, 0.16]
        )[0]
    else:
        dificuldade = random.choices(
            ["nenhuma", "ligeira", "moderada", "grave"],
            weights=[0.62, 0.23, 0.11, 0.04]
        )[0]

    # Limitação respiratória - alinhada com Prolog
    if dificuldade == "grave":
        limitacao = random.choices(
            ["alguma", "significativa"],
            weights=[0.20, 0.80]
        )[0]
    elif dificuldade == "moderada":
        limitacao = random.choices(
            ["nenhuma", "alguma", "significativa"],
            weights=[0.10, 0.45, 0.45]
        )[0]
    elif dificuldade == "ligeira":
        limitacao = random.choices(
            ["nenhuma", "alguma", "significativa"],
            weights=[0.55, 0.40, 0.05]
        )[0]
    else:
        if pieira == 1:
            limitacao = random.choices(
                ["nenhuma", "alguma", "significativa"],
                weights=[0.55, 0.40, 0.05]
            )[0]
        else:
            limitacao = random.choices(
                ["nenhuma", "alguma", "significativa"],
                weights=[0.82, 0.16, 0.02]
            )[0]

    # Dor torácica
    if agravamento == 1 and dificuldade in ["moderada", "grave"]:
        dor = random.choices(
            ["nenhuma", "ligeira", "moderada", "forte"],
            weights=[0.20, 0.25, 0.35, 0.20]
        )[0]
    elif dificuldade in ["moderada", "grave"] or limitacao == "significativa":
        dor = random.choices(
            ["nenhuma", "ligeira", "moderada", "forte"],
            weights=[0.30, 0.35, 0.25, 0.10]
        )[0]
    else:
        dor = random.choices(
            ["nenhuma", "ligeira", "moderada", "forte"],
            weights=[0.72, 0.20, 0.07, 0.01]
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
            ["nenhuma", "alguma", "significativa"], limitacao
        ).items()
    })

    caso["encaminhamento"] = atribuir_encaminhamento(caso)
    return caso


def fator_risco(caso):
    return (
        caso["idade_risco"] == 1
        or caso["doenca_respiratoria_previa"] == 1
        or caso["imunossupressao"] == 1
    )


def sinal_alarme(caso):
    if caso["dificuldade_respiratoria_grave"] == 1:
        return True

    if (
        caso["limitacao_respiratoria_significativa"] == 1
        and caso["dificuldade_respiratoria_moderada"] == 1
    ):
        return True

    if caso["dor_toracica_forte"] == 1:
        return True

    if (
        caso["dificuldade_respiratoria_moderada"] == 1
        and caso["dor_toracica_moderada"] == 1
        and caso["agravamento"] == 1
    ):
        return True

    return False


def compromisso_respiratorio_importante(caso):
    return (
        caso["dificuldade_respiratoria_moderada"] == 1
        or caso["limitacao_respiratoria_significativa"] == 1
    )


def compromisso_respiratorio_ligeiro(caso):
    return (
        caso["dificuldade_respiratoria_ligeira"] == 1
        or caso["limitacao_respiratoria_alguma"] == 1
        or (caso["pieira"] == 1 and caso["dificuldade_respiratoria_nenhuma"] == 1)
    )


def sem_compromisso_respiratorio(caso):
    return (
        caso["dificuldade_respiratoria_nenhuma"] == 1
        and caso["limitacao_respiratoria_nenhuma"] == 1
    )


def febre_relevante(caso):
    return (
        caso["febre_alta"] == 1
        or (caso["febre_moderada"] == 1 and caso["duracao_prolongada"] == 1)
    )


def quadro_infecioso_relevante(caso):
    return (
        febre_relevante(caso)
        or (caso["febre_moderada"] == 1 and caso["agravamento"] == 1)
    )


def caso_persistente(caso):
    return caso["duracao_prolongada"] == 1


def caso_agravado(caso):
    return caso["agravamento"] == 1


def dor_toracica_relevante(caso):
    return (
        caso["dor_toracica_moderada"] == 1
        or caso["dor_toracica_forte"] == 1
    )


def caso_ligeiro_vias_superiores(caso):
    return (
        caso["dor_garganta"] == 1
        and caso["congestao_nasal"] == 1
        and caso["febre_nenhuma"] == 1
        and sem_compromisso_respiratorio(caso)
        and caso["dor_toracica_nenhuma"] == 1
        and caso["agravamento"] == 0
        and caso["duracao_prolongada"] == 0
    )


def tosse_ligeira_isolada(caso):
    return (
        caso["tosse"] == 1
        and caso["febre_nenhuma"] == 1
        and sem_compromisso_respiratorio(caso)
        and caso["dor_toracica_nenhuma"] == 1
        and caso["agravamento"] == 0
        and caso["duracao_prolongada"] == 0
        and caso["pieira"] == 0
    )


def caso_ligeiro_sem_risco(caso):
    return (
        (caso_ligeiro_vias_superiores(caso) or tosse_ligeira_isolada(caso))
        and not fator_risco(caso)
    )


def atribuir_encaminhamento(caso):
    # Emergência
    if sinal_alarme(caso):
        return "emergencia"

    # Urgência
    if quadro_infecioso_relevante(caso) and compromisso_respiratorio_importante(caso):
        return "urgencia"

    if caso["pieira"] == 1 and caso["dificuldade_respiratoria_moderada"] == 1:
        return "urgencia"

    if dor_toracica_relevante(caso) and (
        compromisso_respiratorio_importante(caso)
        or compromisso_respiratorio_ligeiro(caso)
    ):
        return "urgencia"

    if fator_risco(caso) and caso["febre_alta"] == 1:
        return "urgencia"

    if fator_risco(caso) and caso_agravado(caso) and (
        compromisso_respiratorio_importante(caso)
        or compromisso_respiratorio_ligeiro(caso)
    ):
        return "urgencia"

    if caso_agravado(caso) and compromisso_respiratorio_importante(caso):
        return "urgencia"

    # Consulta médica
    if (
        caso["tosse"] == 1
        and caso_agravado(caso)
        and sem_compromisso_respiratorio(caso)
        and caso["dor_toracica_nenhuma"] == 1
    ):
        return "consulta_medica"

    if (
        caso["tosse"] == 1
        and caso["febre_moderada"] == 1
        and caso_persistente(caso)
        and sem_compromisso_respiratorio(caso)
    ):
        return "consulta_medica"

    if caso["febre_alta"] == 1 and sem_compromisso_respiratorio(caso):
        return "consulta_medica"

    if caso["dor_toracica_ligeira"] == 1 and sem_compromisso_respiratorio(caso):
        return "consulta_medica"

    if (
        caso["limitacao_respiratoria_alguma"] == 1
        and caso["dificuldade_respiratoria_ligeira"] == 1
    ):
        return "consulta_medica"

    if fator_risco(caso) and caso["tosse"] == 1 and (
        caso_persistente(caso) or caso_agravado(caso)
    ):
        return "consulta_medica"

    if fator_risco(caso) and caso["tosse"] == 1 and (
        caso["febre_moderada"] == 1 or caso["febre_alta"] == 1
    ):
        return "consulta_medica"

    if fator_risco(caso) and caso_persistente(caso):
        return "consulta_medica"

    if caso["pieira"] == 1 and caso["dificuldade_respiratoria_nenhuma"] == 1:
        return "consulta_medica"

    if (
        caso_persistente(caso)
        and caso_agravado(caso)
        and sem_compromisso_respiratorio(caso)
    ):
        return "consulta_medica"

    if (
        caso["febre_moderada"] == 1
        and caso_persistente(caso)
        and sem_compromisso_respiratorio(caso)
    ):
        return "consulta_medica"

    # Autocuidados
    if caso_ligeiro_sem_risco(caso):
        return "autocuidados"

    # fallback coerente
    return "consulta_medica"


# -----------------------------
# Gerar muitos casos
# -----------------------------
dados = [gerar_caso() for _ in range(5000)]
df = pd.DataFrame(dados)

print("Distribuição inicial:")
print(df["encaminhamento"].value_counts())
print(df["encaminhamento"].value_counts(normalize=True))

# -----------------------------
# Construir base final random mas coerente
# Regras:
# - total final = 1000
# - cada classe entre 10% e 35%
# - contagens finais NÃO são fixas
# - respeita a disponibilidade real do gerador
# -----------------------------
total_final = 1000
min_por_classe = int(0.10 * total_final)   # 100
max_por_classe = int(0.35 * total_final)   # 350

classes = ["autocuidados", "consulta_medica", "urgencia", "emergencia"]
dfs = {classe: df[df["encaminhamento"] == classe].copy() for classe in classes}
disponiveis = {classe: len(dfs[classe]) for classe in classes}

# Verificar se todas as classes conseguem cumprir o mínimo
for classe in classes:
    if disponiveis[classe] < min_por_classe:
        raise ValueError(
            f"A classe '{classe}' só tem {disponiveis[classe]} casos disponíveis. "
            f"É menos do que o mínimo exigido de {min_por_classe}. "
            f"Tens de ajustar o gerador."
        )

def gerar_contagens_random(classes, total_final, min_por_classe, max_por_classe, disponiveis):
    """
    Gera contagens aleatórias por classe:
    - soma total = total_final
    - cada classe entre min e max
    - sem ultrapassar disponibilidade
    """
    while True:
        restantes = total_final
        contagens = {}

        # ordem aleatória para não enviesar sempre as mesmas classes
        ordem = classes[:]
        random.shuffle(ordem)

        for i, classe in enumerate(ordem):
            classes_restantes = len(ordem) - i - 1

            minimo_viavel = min_por_classe
            maximo_viavel = min(max_por_classe, disponiveis[classe])

            # garantir que sobra espaço para as restantes classes cumprirem o mínimo
            maximo_que_posso_dar = restantes - (classes_restantes * min_por_classe)
            maximo_final = min(maximo_viavel, maximo_que_posso_dar)

            # garantir que mesmo dando o mínimo aqui, ainda dá para as restantes
            minimo_que_devo_dar = max(
                minimo_viavel,
                restantes - sum(
                    min(max_por_classe, disponiveis[c])
                    for c in ordem[i+1:]
                )
            )

            if minimo_que_devo_dar > maximo_final:
                break

            contagens[classe] = random.randint(minimo_que_devo_dar, maximo_final)
            restantes -= contagens[classe]

        else:
            # se completou o for sem break e a soma bate certo
            if sum(contagens.values()) == total_final:
                # devolver na ordem original das classes
                return {classe: contagens[classe] for classe in classes}

# gerar contagens finais verdadeiramente aleatórias dentro dos limites
target_counts = gerar_contagens_random(
    classes=classes,
    total_final=total_final,
    min_por_classe=min_por_classe,
    max_por_classe=max_por_classe,
    disponiveis=disponiveis
)

print("\nContagens finais sorteadas:")
print(target_counts)

# amostrar os casos por classe
amostras = []
for classe in classes:
    amostras.append(
        dfs[classe].sample(n=target_counts[classe], random_state=random.randint(1, 100000))
    )

df_final = pd.concat(amostras, ignore_index=True)
df_final = df_final.sample(frac=1, random_state=random.randint(1, 100000)).reset_index(drop=True)

print("\nDistribuição final:")
print(df_final["encaminhamento"].value_counts())
print(df_final["encaminhamento"].value_counts(normalize=True))

pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.max_colwidth", None)

print("\nAmostra da base final:")
print(df_final.head(20).to_string())

df_final.to_csv("triagem_sintetica.csv", index=False)