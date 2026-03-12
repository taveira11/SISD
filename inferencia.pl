:- consult('basedeconhecimento.pl').
:- consult('basededados.pl').

obter_encaminhamentos(Lista) :-
    findall(E, regra(E), Lista).

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