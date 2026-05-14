% ---------------------------------
% BASE DE DADOS
% Triagem de Sintomas Respiratorios
% ---------------------------------

:- dynamic resposta/2.

% =========================================================
% 1. LIMPEZA DE RESPOSTAS
% =========================================================

limpar_respostas :-
    retractall(resposta(_, _)).

remover_resposta(Pergunta) :-
    retractall(resposta(Pergunta, _)).

% =========================================================
% 2. GUARDAR E VALIDAR RESPOSTAS
% =========================================================

guardar_resposta(Pergunta, Valor) :-
    pergunta_existe(Pergunta),
    (   valor_valido(Pergunta, Valor)
    ->  retractall(resposta(Pergunta, _)),
        assertz(resposta(Pergunta, Valor))
    ;   write('Valor invalido para '), write(Pergunta), write('.'), nl,
        write('Resposta ignorada.'), nl,
        fail
    ).

atualizar_resposta(Pergunta, NovoValor) :-
    guardar_resposta(Pergunta, NovoValor).

% =========================================================
% 3. CONSULTA DE ESTADO
% =========================================================

respondeu(Pergunta) :-
    resposta(Pergunta, _).

nao_respondeu(Pergunta) :-
    pergunta_existe(Pergunta),
    \+ resposta(Pergunta, _).

obter_resposta(Pergunta, Valor) :-
    resposta(Pergunta, Valor).

% =========================================================
% 4. LISTAGEM DE RESPOSTAS
% =========================================================

listar_respostas :-
    forall(
        resposta(Pergunta, Valor),
        (write(Pergunta), write(' = '), write(Valor), nl)
    ).

total_respostas(Total) :-
    findall(P, resposta(P, _), Lista),
    length(Lista, Total).

% =========================================================
% 5. PERGUNTAS
% =========================================================

pergunta_existe(Pergunta) :-
    pergunta(Pergunta, _).

todas_perguntas(Lista) :-
    findall(P, pergunta(P, _), Lista).

perguntas_respondidas(Lista) :-
    findall(P, resposta(P, _), Lista).

perguntas_em_falta(Lista) :-
    findall(P, nao_respondeu(P), Lista).

questionario_completo :-
    \+ nao_respondeu(_).

% =========================================================
% 6. ORDEM DAS PERGUNTAS
% =========================================================

ordem_pergunta(1, idade).
ordem_pergunta(2, dificuldade_respiratoria).
ordem_pergunta(3, dor_toracica).
ordem_pergunta(4, limitacao_respiratoria).
ordem_pergunta(5, febre).
ordem_pergunta(6, tosse).
ordem_pergunta(7, pieira).
ordem_pergunta(8, agravamento).
ordem_pergunta(9, duracao_prolongada).
ordem_pergunta(10, doenca_respiratoria_previa).
ordem_pergunta(11, imunossupressao).
ordem_pergunta(12, dor_garganta).
ordem_pergunta(13, congestao_nasal).

proxima_pergunta(Pergunta) :-
    ordem_pergunta(_, Pergunta),
    nao_respondeu(Pergunta),
    !.

% =========================================================
% 7. RESUMO DO CASO
% =========================================================

resumo_caso :-
    write('--- RESUMO DO CASO ---'), nl,
    listar_respostas,
    nl,
    total_respostas(Total),
    write('Total de respostas: '), write(Total), nl,
    (questionario_completo ->
        write('Estado: questionario completo.'), nl
    ;
        write('Estado: questionario incompleto.'), nl
    ),
    (ha_inconsistencias ->
        write('Foram detetadas inconsistencias nas respostas.'), nl
    ;
        write('Nao foram detetadas inconsistencias.'), nl
    ).

% =========================================================
% 8. VALIDACAO DE CONSISTENCIA (MELHORADA)
% =========================================================

% Respiracao incoerente
inconsistencia('Dificuldade respiratoria grave com limitacao nenhuma.') :-
    resposta(dificuldade_respiratoria, grave),
    resposta(limitacao_respiratoria, nenhuma).

inconsistencia('Sem dificuldade respiratoria mas com limitacao significativa.') :-
    resposta(dificuldade_respiratoria, nenhuma),
    resposta(limitacao_respiratoria, significativa).

% Febre incoerente
inconsistencia('Febre alta sem qualquer agravamento ou duracao prolongada.') :-
    resposta(febre, alta),
    resposta(agravamento, nao),
    resposta(duracao_prolongada, nao).

% Agravamento sem sintomas
inconsistencia('Agravamento sem sintomas associados.') :-
    resposta(agravamento, sim),
    resposta(tosse, nao),
    resposta(pieira, nao),
    resposta(dor_garganta, nao),
    resposta(congestao_nasal, nao).

% Dor toracica incoerente
inconsistencia('Dor toracica forte sem qualquer compromisso respiratorio.') :-
    resposta(dor_toracica, forte),
    resposta(dificuldade_respiratoria, nenhuma),
    resposta(limitacao_respiratoria, nenhuma).

ha_inconsistencias :-
    inconsistencia_existe(_).

inconsistencia_existe(Mensagem) :-
    inconsistencia(Mensagem).

listar_inconsistencias :-
    forall(
        inconsistencia_existe(Mensagem),
        (write('- '), write(Mensagem), nl)
    ).

% =========================================================
% 9. EXPLICACAO (PREPARACAO)
% =========================================================

% Este predicado vai ser usado depois na inferencia
explicacao_respostas(Lista) :-
    findall(
        Pergunta=Valor,
        resposta(Pergunta, Valor),
        Lista
    ).

% =========================================================
% 10. CASOS DE TESTE
% =========================================================

caso_exemplo(1) :-
    limpar_respostas,
    guardar_resposta(idade, 22),
    guardar_resposta(tosse, sim),
    guardar_resposta(febre, moderada),
    guardar_resposta(dificuldade_respiratoria, nenhuma),
    guardar_resposta(dor_toracica, nenhuma),
    guardar_resposta(limitacao_respiratoria, nenhuma),
    guardar_resposta(duracao_prolongada, sim),
    guardar_resposta(agravamento, nao),
    guardar_resposta(pieira, nao),
    guardar_resposta(dor_garganta, nao),
    guardar_resposta(congestao_nasal, nao),
    guardar_resposta(doenca_respiratoria_previa, nao),
    guardar_resposta(imunossupressao, nao).