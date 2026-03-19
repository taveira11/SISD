% ---------------------------------
% BASE DE DADOS
% Triagem de Sintomas Respiratorios
% ---------------------------------

:- dynamic resposta/2.

% ---------------------------------
% LIMPEZA DE RESPOSTAS
% ---------------------------------

limpar_respostas :-
    retractall(resposta(_, _)).

remover_resposta(Pergunta) :-
    retractall(resposta(Pergunta, _)).

% ---------------------------------
% GUARDAR E ATUALIZAR RESPOSTAS
% ---------------------------------

guardar_resposta(Pergunta, Valor) :-
    pergunta_existe(Pergunta),
    valor_valido(Pergunta, Valor),
    retractall(resposta(Pergunta, _)),
    assertz(resposta(Pergunta, Valor)).

atualizar_resposta(Pergunta, NovoValor) :-
    guardar_resposta(Pergunta, NovoValor).

% ---------------------------------
% CONSULTA DE ESTADO
% ---------------------------------

respondeu(Pergunta) :-
    resposta(Pergunta, _).

nao_respondeu(Pergunta) :-
    pergunta_existe(Pergunta),
    \+ resposta(Pergunta, _).

obter_resposta(Pergunta, Valor) :-
    resposta(Pergunta, Valor).

% ---------------------------------
% LISTAGEM DE RESPOSTAS
% ---------------------------------

listar_respostas :-
    forall(
        resposta(Pergunta, Valor),
        (write(Pergunta), write(' = '), write(Valor), nl)
    ).

total_respostas(Total) :-
    findall(Pergunta, resposta(Pergunta, _), Lista),
    length(Lista, Total).

% ---------------------------------
% PERGUNTAS EXISTENTES
% ---------------------------------

pergunta_existe(Pergunta) :-
    pergunta(Pergunta, _).

todas_perguntas(Lista) :-
    findall(Pergunta, pergunta(Pergunta, _), Lista).

perguntas_respondidas(Lista) :-
    findall(Pergunta, resposta(Pergunta, _), Lista).

perguntas_em_falta(Lista) :-
    findall(Pergunta, nao_respondeu(Pergunta), Lista).

questionario_completo :-
    \+ nao_respondeu(_).

% ---------------------------------
% ORDEM DAS PERGUNTAS
% ---------------------------------

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

% ---------------------------------
% RESUMO DO CASO
% ---------------------------------

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

% ---------------------------------
% VALIDACAO DE CONSISTENCIA
% ---------------------------------

inconsistencia('Dificuldade respiratoria grave com limitacao respiratoria nenhuma: verificar respostas.') :-
    resposta(dificuldade_respiratoria, grave),
    resposta(limitacao_respiratoria, nenhuma).

inconsistencia('Dificuldade respiratoria nenhuma com limitacao respiratoria significativa: verificar respostas.') :-
    resposta(dificuldade_respiratoria, nenhuma),
    resposta(limitacao_respiratoria, significativa).

inconsistencia('Ausencia de tosse, pieira, dor de garganta e congestao nasal com agravamento assinalado: confirmar coerencia das respostas.') :-
    resposta(tosse, nao),
    resposta(pieira, nao),
    resposta(dor_garganta, nao),
    resposta(congestao_nasal, nao),
    resposta(agravamento, sim).

ha_inconsistencias :-
    inconsistencia_existe(_).

inconsistencia_existe(Mensagem) :-
    inconsistencia(Mensagem).

listar_inconsistencias :-
    forall(
        inconsistencia_existe(Mensagem),
        (write('- '), write(Mensagem), nl)
    ).

% ---------------------------------
% CASOS DE TESTE
% ---------------------------------

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

caso_exemplo(2) :-
    limpar_respostas,
    guardar_resposta(idade, 70),
    guardar_resposta(tosse, sim),
    guardar_resposta(febre, alta),
    guardar_resposta(dificuldade_respiratoria, ligeira),
    guardar_resposta(dor_toracica, nenhuma),
    guardar_resposta(limitacao_respiratoria, alguma),
    guardar_resposta(duracao_prolongada, nao),
    guardar_resposta(agravamento, sim),
    guardar_resposta(pieira, sim),
    guardar_resposta(dor_garganta, nao),
    guardar_resposta(congestao_nasal, nao),
    guardar_resposta(doenca_respiratoria_previa, sim),
    guardar_resposta(imunossupressao, nao).

caso_exemplo(3) :-
    limpar_respostas,
    guardar_resposta(idade, 45),
    guardar_resposta(tosse, sim),
    guardar_resposta(febre, alta),
    guardar_resposta(dificuldade_respiratoria, grave),
    guardar_resposta(dor_toracica, forte),
    guardar_resposta(limitacao_respiratoria, significativa),
    guardar_resposta(duracao_prolongada, nao),
    guardar_resposta(agravamento, sim),
    guardar_resposta(pieira, sim),
    guardar_resposta(dor_garganta, nao),
    guardar_resposta(congestao_nasal, nao),
    guardar_resposta(doenca_respiratoria_previa, nao),
    guardar_resposta(imunossupressao, nao).

caso_exemplo(4) :-
    limpar_respostas,
    guardar_resposta(idade, 30),
    guardar_resposta(tosse, nao),
    guardar_resposta(febre, nenhuma),
    guardar_resposta(dificuldade_respiratoria, nenhuma),
    guardar_resposta(dor_toracica, forte),
    guardar_resposta(limitacao_respiratoria, nenhuma),
    guardar_resposta(duracao_prolongada, nao),
    guardar_resposta(agravamento, nao),
    guardar_resposta(pieira, nao),
    guardar_resposta(dor_garganta, nao),
    guardar_resposta(congestao_nasal, nao),
    guardar_resposta(doenca_respiratoria_previa, nao),
    guardar_resposta(imunossupressao, nao).

caso_exemplo(5) :-
    limpar_respostas,
    guardar_resposta(idade, 19),
    guardar_resposta(tosse, nao),
    guardar_resposta(febre, nenhuma),
    guardar_resposta(dificuldade_respiratoria, nenhuma),
    guardar_resposta(dor_toracica, nenhuma),
    guardar_resposta(limitacao_respiratoria, nenhuma),
    guardar_resposta(duracao_prolongada, nao),
    guardar_resposta(agravamento, nao),
    guardar_resposta(pieira, nao),
    guardar_resposta(dor_garganta, sim),
    guardar_resposta(congestao_nasal, sim),
    guardar_resposta(doenca_respiratoria_previa, nao),
    guardar_resposta(imunossupressao, nao).

caso_exemplo(6) :-
    limpar_respostas,
    guardar_resposta(idade, 68),
    guardar_resposta(tosse, sim),
    guardar_resposta(febre, moderada),
    guardar_resposta(dificuldade_respiratoria, nenhuma),
    guardar_resposta(dor_toracica, nenhuma),
    guardar_resposta(limitacao_respiratoria, nenhuma),
    guardar_resposta(duracao_prolongada, sim),
    guardar_resposta(agravamento, sim),
    guardar_resposta(pieira, nao),
    guardar_resposta(dor_garganta, nao),
    guardar_resposta(congestao_nasal, nao),
    guardar_resposta(doenca_respiratoria_previa, nao),
    guardar_resposta(imunossupressao, nao).