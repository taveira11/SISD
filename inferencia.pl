:- consult('basedeconhecimento.pl').
:- consult('basededados.pl').

% =========================================================
% 1. OBTER ENCAMINHAMENTOS COM MOTIVO
% =========================================================

obter_encaminhamentos_com_motivo(Lista) :-
    findall(
        Encaminhamento-Motivo,
        regra_com_motivo(Encaminhamento, Motivo),
        Lista
    ).

% =========================================================
% 2. ENCAMINHAMENTOS ATIVOS (SEM DUPLICADOS)
% =========================================================

obter_encaminhamentos(Lista) :-
    findall(E, regra(E), L),
    sort(L, Lista).

% =========================================================
% 3. VERIFICAR SE EXISTE ENCAMINHAMENTO
% =========================================================

ha_encaminhamento :-
    obter_encaminhamentos(Lista),
    Lista \= [].

% =========================================================
% 4. ESCOLHER MELHOR ENCAMINHAMENTO
% =========================================================

melhor_encaminhamento(Melhor) :-
    obter_encaminhamentos(Lista),
    Lista \= [],
    escolher_maior_prioridade(Lista, Melhor).

escolher_maior_prioridade([X], X).

escolher_maior_prioridade([H|T], Melhor) :-
    escolher_maior_prioridade(T, Temp),
    prioridade(H, PH),
    prioridade(Temp, PT),
    (PH >= PT -> Melhor = H ; Melhor = Temp).

% =========================================================
% 5. OBTER MOTIVOS DO MELHOR ENCAMINHAMENTO
% =========================================================

motivos_encaminhamento(Encaminhamento, Motivos) :-
    findall(
        Motivo,
        regra_com_motivo(Encaminhamento, Motivo),
        Motivos
    ).

% =========================================================
% 6. MOSTRAR TODOS OS ENCAMINHAMENTOS COM EXPLICACAO
% =========================================================

mostrar_encaminhamentos_detalhados :-
    write('--- ENCAMINHAMENTOS POSSIVEIS ---'), nl,
    obter_encaminhamentos_com_motivo(Lista),
    (Lista = [] ->
        write('Nenhum encaminhamento encontrado.'), nl
    ;
        mostrar_lista_encaminhamentos(Lista)
    ).

mostrar_lista_encaminhamentos([]).

mostrar_lista_encaminhamentos([Enc-Mot|T]) :-
    write('- '), write(Enc), write(': '), write(Mot), nl,
    mostrar_lista_encaminhamentos(T).

% =========================================================
% 7. MOSTRAR RESULTADO FINAL COM EXPLICACAO
% =========================================================

mostrar_resultado_final :-
    nl,
    write('===================================='), nl,
    write(' RESULTADO FINAL DA TRIAGEM'), nl,
    write('===================================='), nl,

    (ha_encaminhamento ->
        melhor_encaminhamento(Melhor),
        write('Encaminhamento recomendado: '), write(Melhor), nl, nl,

        write('Motivos principais:'), nl,
        motivos_encaminhamento(Melhor, Motivos),
        mostrar_motivos(Motivos),

        nl,
        write('Outros encaminhamentos considerados:'), nl,
        mostrar_encaminhamentos_detalhados
    ;
        write('Nao foi possivel determinar um encaminhamento.'), nl
    ).

mostrar_motivos([]) :-
    write('- Sem explicacao disponivel.'), nl.

mostrar_motivos([H|T]) :-
    write('- '), write(H), nl,
    mostrar_motivos(T).