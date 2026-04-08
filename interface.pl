:- consult('basedeconhecimento.pl').
:- consult('basededados.pl').
:- consult('inferencia.pl').

% =========================================================
% 1. INICIAR TRIAGEM
% =========================================================

iniciar_triagem :-
    limpar_respostas,
    nl,
    write('===================================='), nl,
    write(' Sistema de Triagem Respiratoria'), nl,
    write('===================================='), nl, nl,
    fazer_perguntas,
    mostrar_resultado_interface,
    mostrar_inconsistencias_final.

% =========================================================
% 2. EXECUTAR QUESTIONARIO AUTOMATICO
% =========================================================

fazer_perguntas :-
    ordem_pergunta(_, Pergunta),
    fazer_pergunta(Pergunta),
    fail.
fazer_perguntas.

% =========================================================
% 3. TIPOS DE PERGUNTAS
% =========================================================

fazer_pergunta(Pergunta) :-
    dado_numerico(Pergunta),
    perguntar_numerico(Pergunta),
    !.

fazer_pergunta(Pergunta) :-
    sintoma_binario(Pergunta),
    perguntar_binario(Pergunta),
    !.

fazer_pergunta(Pergunta) :-
    sintoma_nivel(Pergunta, Opcoes),
    perguntar_nivel(Pergunta, Opcoes).

% =========================================================
% 4. PERGUNTAS COM VALIDACAO
% =========================================================

perguntar_binario(Sintoma) :-
    pergunta(Sintoma, Texto),
    repeat,
    write(Texto), write(' (sim/nao): '),
    read(Resposta),
    (   (Resposta = sim ; Resposta = nao),
        guardar_resposta(Sintoma, Resposta)
    ->  !
    ;   write('Resposta invalida. Escreve sim ou nao.'), nl,
        fail
    ).

perguntar_numerico(Campo) :-
    pergunta(Campo, Texto),
    repeat,
    write(Texto), write(' '),
    read(Resposta),
    (   integer(Resposta),
        guardar_resposta(Campo, Resposta)
    ->  !
    ;   write('Valor invalido. Introduz um numero inteiro.'), nl,
        fail
    ).

perguntar_nivel(Sintoma, Opcoes) :-
    pergunta(Sintoma, Texto),
    repeat,
    nl,
    write(Texto), nl,
    write('Opcoes: '), write(Opcoes), nl,
    write('Resposta: '),
    read(Resposta),
    (   member(Resposta, Opcoes),
        guardar_resposta(Sintoma, Resposta)
    ->  !
    ;   write('Resposta invalida. Escolhe uma das opcoes apresentadas.'), nl,
        fail
    ).

% =========================================================
% 5. RESULTADO FINAL
% =========================================================

mostrar_resultado_interface :-
    nl,
    write('===================================='), nl,
    write(' RESULTADO DA TRIAGEM'), nl,
    write('===================================='), nl,
    resumo_caso,
    nl,
    mostrar_resultado_final.

% =========================================================
% 6. INCONSISTENCIAS
% =========================================================

mostrar_inconsistencias_final :-
    nl,
    (   ha_inconsistencias
    ->  write('------------------------------------'), nl,
        write(' INCONSISTENCIAS DETETADAS'), nl,
        write('------------------------------------'), nl,
        listar_inconsistencias
    ;   true
    ).