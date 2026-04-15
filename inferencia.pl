:- consult('basedeconhecimento.pl').
:- consult('basededados.pl').

obter_encaminhamentos(Lista) :-
    findall(E, regra(E), Repetidos),
    sort(Repetidos, Lista).

obter_encaminhamentos_com_motivo(Lista) :-
    findall(Enc-Mot, regra_com_motivo(Enc, Mot), Repetidos),
    sort(Repetidos, Lista).

ha_encaminhamento :-
    obter_encaminhamentos(Lista),
    Lista \= [].

melhor_encaminhamento(Melhor) :-
    obter_encaminhamentos(Lista),
    Lista \= [],
    escolher_maior_prioridade(Lista, Melhor),
    !.

escolher_maior_prioridade([X], X).
escolher_maior_prioridade([H|T], Melhor) :-
    escolher_maior_prioridade(T, Temp),
    prioridade(H, PH),
    prioridade(Temp, PT),
    (PH >= PT -> Melhor = H ; Melhor = Temp).

motivos_encaminhamento(Encaminhamento, Motivos) :-
    findall(Motivo, regra_com_motivo(Encaminhamento, Motivo), Repetidos),
    sort(Repetidos, Motivos).

resultado_triagem(Encaminhamento, Motivos, Outros) :-
    melhor_encaminhamento(Encaminhamento),
    motivos_encaminhamento(Encaminhamento, Motivos),
    obter_encaminhamentos_com_motivo(Outros),
    !.

resultado_triagem(sem_encaminhamento, [], []).