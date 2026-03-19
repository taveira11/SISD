:- consult('basedeconhecimento.pl').
:- consult('basededados.pl').

obter_encaminhamentos(Lista) :-
    findall(E, regra(E), L),
    sort(L, Lista).

encaminhamentos_ativos :-
    obter_encaminhamentos(Lista),
    write('Encaminhamentos ativos: '), write(Lista), nl.

ha_encaminhamento :-
    obter_encaminhamentos(Lista),
    Lista \= [].

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