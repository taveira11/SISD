:- dynamic resposta/2.

limpar_respostas :-
    retractall(resposta(_, _)).

guardar_resposta(Pergunta, Valor) :-
    retractall(resposta(Pergunta, _)),
    assertz(resposta(Pergunta, Valor)).

caso_exemplo(1) :-
    limpar_respostas,
    guardar_resposta(tosse, sim),
    guardar_resposta(febre, moderada),
    guardar_resposta(dificuldade_respiratoria, nenhuma),
    guardar_resposta(dor_toracica, nenhuma),
    guardar_resposta(duracao_prolongada, sim),
    guardar_resposta(agravamento, nao).

caso_exemplo(2) :-
    limpar_respostas,
    guardar_resposta(tosse, sim),
    guardar_resposta(febre, alta),
    guardar_resposta(dificuldade_respiratoria, moderada),
    guardar_resposta(dor_toracica, nenhuma),
    guardar_resposta(duracao_prolongada, sim),
    guardar_resposta(agravamento, sim).

caso_exemplo(3) :-
    limpar_respostas,
    guardar_resposta(tosse, sim),
    guardar_resposta(febre, nenhuma),
    guardar_resposta(dificuldade_respiratoria, grave),
    guardar_resposta(dor_toracica, forte),
    guardar_resposta(agravamento, sim).