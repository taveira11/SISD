:- consult('basedeconhecimento.pl').
:- consult('basededados.pl').
:- consult('inferencia.pl').

avaliar_caso(
    Idade,
    Tosse,
    Pieira,
    DorGarganta,
    CongestaoNasal,
    Agravamento,
    DuracaoProlongada,
    DoencaRespiratoriaPrevia,
    Imunossupressao,
    Febre,
    DificuldadeRespiratoria,
    DorToracica,
    LimitacaoRespiratoria
) :-
    limpar_respostas,

    guardar_resposta(idade, Idade),
    guardar_resposta(tosse, Tosse),
    guardar_resposta(pieira, Pieira),
    guardar_resposta(dor_garganta, DorGarganta),
    guardar_resposta(congestao_nasal, CongestaoNasal),
    guardar_resposta(agravamento, Agravamento),
    guardar_resposta(duracao_prolongada, DuracaoProlongada),
    guardar_resposta(doenca_respiratoria_previa, DoencaRespiratoriaPrevia),
    guardar_resposta(imunossupressao, Imunossupressao),
    guardar_resposta(febre, Febre),
    guardar_resposta(dificuldade_respiratoria, DificuldadeRespiratoria),
    guardar_resposta(dor_toracica, DorToracica),
    guardar_resposta(limitacao_respiratoria, LimitacaoRespiratoria).

executar_api(
    Idade,
    Tosse,
    Pieira,
    DorGarganta,
    CongestaoNasal,
    Agravamento,
    DuracaoProlongada,
    DoencaRespiratoriaPrevia,
    Imunossupressao,
    Febre,
    DificuldadeRespiratoria,
    DorToracica,
    LimitacaoRespiratoria
) :-
    avaliar_caso(
        Idade,
        Tosse,
        Pieira,
        DorGarganta,
        CongestaoNasal,
        Agravamento,
        DuracaoProlongada,
        DoencaRespiratoriaPrevia,
        Imunossupressao,
        Febre,
        DificuldadeRespiratoria,
        DorToracica,
        LimitacaoRespiratoria
    ),
    resultado_triagem(Encaminhamento, Motivos, Outros),
    write('RESULTADO='), write(Encaminhamento), nl,
    write('MOTIVOS='), write(Motivos), nl,
    write('OUTROS='), write(Outros), nl.