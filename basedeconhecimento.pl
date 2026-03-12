% ---------------------------------
% BASE DE CONHECIMENTO
% Triagem de Sintomas Respiratorios
% ---------------------------------

% Sintomas binarios
sintoma_binario(tosse).
sintoma_binario(pieira).
sintoma_binario(dor_garganta).
sintoma_binario(congestao_nasal).
sintoma_binario(agravamento).
sintoma_binario(duracao_prolongada).

% Sintomas com niveis
sintoma_nivel(febre, [nenhuma, moderada, alta]).
sintoma_nivel(dificuldade_respiratoria, [nenhuma, ligeira, moderada, grave]).
sintoma_nivel(dor_toracica, [nenhuma, ligeira, moderada, forte]).
sintoma_nivel(limitacao_respiratoria, [nenhuma, alguma, significativa]).

% Encaminhamentos possiveis
encaminhamento(emergencia).
encaminhamento(urgencia).
encaminhamento(consulta_medica).
encaminhamento(autocuidados).

% Perguntas do sistema
pergunta(tosse, 'Tem tosse?').
pergunta(pieira, 'Tem pieira ou chiadeira ao respirar?').
pergunta(dor_garganta, 'Tem dor de garganta?').
pergunta(congestao_nasal, 'Tem congestao nasal?').
pergunta(agravamento, 'Os sintomas tem vindo a piorar?').
pergunta(duracao_prolongada, 'Os sintomas duram ha mais de 3 dias?').

pergunta(febre, 'Qual o nivel de febre?').
pergunta(dificuldade_respiratoria, 'Qual o nivel de dificuldade respiratoria?').
pergunta(dor_toracica, 'Qual o nivel de dor toracica?').
pergunta(limitacao_respiratoria, 'Qual o nivel de limitacao respiratoria?').



% ---------------------------------
% REGRAS DE EMERGENCIA
% ---------------------------------

regra(emergencia) :-
    resposta(dificuldade_respiratoria, grave).

regra(emergencia) :-
    resposta(dificuldade_respiratoria, moderada),
    resposta(dor_toracica, forte).

% ---------------------------------
% REGRAS DE URGENCIA
% ---------------------------------

regra(urgencia) :-
    resposta(febre, alta),
    resposta(dificuldade_respiratoria, moderada).

regra(urgencia) :-
    resposta(pieira, sim),
    resposta(dificuldade_respiratoria, moderada).

% ---------------------------------
% REGRAS DE CONSULTA MEDICA
% ---------------------------------

regra(consulta_medica) :-
    resposta(tosse, sim),
    resposta(agravamento, sim),
    resposta(dificuldade_respiratoria, nenhuma),
    resposta(dor_toracica, nenhuma).

regra(consulta_medica) :-
    resposta(tosse, sim),
    resposta(febre, moderada),
    resposta(duracao_prolongada, sim).

% ---------------------------------
% REGRAS DE AUTOCUIDADOS
% ---------------------------------

regra(autocuidados) :-
    resposta(congestao_nasal, sim),
    resposta(dor_garganta, sim),
    resposta(febre, nenhuma),
    resposta(dificuldade_respiratoria, nenhuma),
    resposta(agravamento, nao).

regra(autocuidados) :-
    resposta(tosse, sim),
    resposta(febre, nenhuma),
    resposta(dificuldade_respiratoria, nenhuma),
    resposta(dor_toracica, nenhuma),
    resposta(agravamento, nao),
    resposta(duracao_prolongada, nao).



% ---------------------------------
% PRIORIDADE DOS ENCAMINHAMENTOS
% ---------------------------------

prioridade(emergencia, 4).
prioridade(urgencia, 3).
prioridade(consulta_medica, 2).
prioridade(autocuidados, 1).