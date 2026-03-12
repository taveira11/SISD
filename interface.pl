:- consult('basedeconhecimento.pl').
:- consult('basededados.pl').
:- consult('inferencia.pl').

iniciar_triagem :-
    limpar_respostas,
    nl,
    write('===================================='), nl,
    write(' Sistema de Triagem Respiratoria'), nl,
    write('===================================='), nl, nl,

    perguntar_binario(tosse),
    perguntar_binario(pieira),
    perguntar_binario(dor_garganta),
    perguntar_binario(congestao_nasal),
    perguntar_binario(agravamento),
    perguntar_binario(duracao_prolongada),

    perguntar_nivel(febre, [nenhuma, moderada, alta]),
    perguntar_nivel(dificuldade_respiratoria, [nenhuma, ligeira, moderada, grave]),
    perguntar_nivel(dor_toracica, [nenhuma, ligeira, moderada, forte]),
    perguntar_nivel(limitacao_respiratoria, [nenhuma, alguma, significativa]),

    mostrar_resultado.

perguntar_binario(Sintoma) :-
    pergunta(Sintoma, Texto),
    write(Texto), write(' (sim/nao): '),
    read(Resposta),
    guardar_resposta(Sintoma, Resposta).

perguntar_nivel(Sintoma, Opcoes) :-
    pergunta(Sintoma, Texto),
    nl,
    write(Texto), nl,
    write('Opcoes: '), write(Opcoes), nl,
    write('Resposta: '),
    read(Resposta),
    guardar_resposta(Sintoma, Resposta).

mostrar_resultado :-
    nl,
    write('===================================='), nl,
    write(' Resultado da Triagem'), nl,
    write('===================================='), nl,
    (   melhor_encaminhamento(Resultado)
    ->  write('Encaminhamento recomendado: '), write(Resultado), nl
    ;   write('Nao foi possivel determinar um encaminhamento.'), nl
    ).