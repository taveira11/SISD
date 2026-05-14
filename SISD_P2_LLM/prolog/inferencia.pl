:- consult('basedeconhecimento.pl').
:- consult('basededados.pl').

% =========================================================
% 1. ENCAMINHAMENTOS
% =========================================================

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

% =========================================================
% 2. PONTUACAO TOTAL
% =========================================================

pontuacao_total(Total) :-
    findall(
        Pontos,
        (
            resposta(Pergunta, Valor),
            pontuacao_resposta(Pergunta, Valor, Pontos)
        ),
        ListaPontos
    ),
    sumlist(ListaPontos, Soma),
    limitar_pontuacao(Soma, Total).

limitar_pontuacao(Valor, 100) :-
    Valor >= 100, !.
limitar_pontuacao(Valor, Valor).

% =========================================================
% 3. FAIXA DE SCORE
% =========================================================

faixa_score(Score, autocuidados) :-
    Score >= 0,
    Score < 25.

faixa_score(Score, consulta_medica) :-
    Score >= 25,
    Score < 50.

faixa_score(Score, urgencia) :-
    Score >= 50,
    Score < 80.

faixa_score(Score, emergencia) :-
    Score >= 80,
    Score =< 100.

% =========================================================
% 4. RESULTADO COM SCORE
% =========================================================

resultado_triagem_com_score(Encaminhamento, Motivos, Outros, Score, Faixa) :-
    resultado_triagem(Encaminhamento, Motivos, Outros),
    pontuacao_total(Score),
    faixa_score(Score, Faixa),
    !.

resultado_triagem_com_score(sem_encaminhamento, [], [], Score, Faixa) :-
    pontuacao_total(Score),
    faixa_score(Score, Faixa).