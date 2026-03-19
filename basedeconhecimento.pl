 ---------------------------------
% BASE DE CONHECIMENTO
% Triagem de Sintomas Respiratorios
% ---------------------------------

% ---------------------------------
% SINTOMAS BINARIOS
% ---------------------------------
sintoma_binario(tosse).
sintoma_binario(pieira).
sintoma_binario(dor_garganta).
sintoma_binario(congestao_nasal).
sintoma_binario(agravamento).
sintoma_binario(duracao_prolongada).
sintoma_binario(doenca_respiratoria_previa).
sintoma_binario(imunossupressao).

% ---------------------------------
% DADOS NUMERICOS
% ---------------------------------
dado_numerico(idade).

% ---------------------------------
% SINTOMAS COM NIVEIS
% ---------------------------------
sintoma_nivel(febre, [nenhuma, moderada, alta]).
sintoma_nivel(dificuldade_respiratoria, [nenhuma, ligeira, moderada, grave]).
sintoma_nivel(dor_toracica, [nenhuma, ligeira, moderada, forte]).
sintoma_nivel(limitacao_respiratoria, [nenhuma, alguma, significativa]).

% ---------------------------------
% ENCAMINHAMENTOS POSSIVEIS
% ---------------------------------
encaminhamento(emergencia).
encaminhamento(urgencia).
encaminhamento(consulta_medica).
encaminhamento(autocuidados).

% ---------------------------------
% PERGUNTAS DO SISTEMA
% ---------------------------------
pergunta(idade, 'Qual e a sua idade?').
pergunta(tosse, 'Tem tosse?').
pergunta(pieira, 'Tem pieira ou chiadeira ao respirar?').
pergunta(dor_garganta, 'Tem dor de garganta?').
pergunta(congestao_nasal, 'Tem congestao nasal?').
pergunta(agravamento, 'Os sintomas tem vindo a piorar?').
pergunta(duracao_prolongada, 'Os sintomas duram ha mais de 3 dias?').
pergunta(doenca_respiratoria_previa, 'Tem alguma doenca respiratoria previa, como asma ou bronquite?').
pergunta(imunossupressao, 'Tem algum problema de imunidade reduzida?').

pergunta(febre, 'Qual o nivel de febre?').
pergunta(dificuldade_respiratoria, 'Qual o nivel de dificuldade respiratoria?').
pergunta(dor_toracica, 'Qual o nivel de dor toracica?').
pergunta(limitacao_respiratoria, 'Qual o nivel de limitacao respiratoria?').

% ---------------------------------
% VALIDACAO DE VALORES
% ---------------------------------
valor_valido(Sintoma, sim) :-
    sintoma_binario(Sintoma).

valor_valido(Sintoma, nao) :-
    sintoma_binario(Sintoma).

valor_valido(Sintoma, Valor) :-
    sintoma_nivel(Sintoma, Lista),
    member(Valor, Lista).

valor_valido(idade, Valor) :-
    integer(Valor),
    Valor >= 0,
    Valor =< 120.

% ---------------------------------
% PRIORIDADE DOS ENCAMINHAMENTOS
% ---------------------------------
prioridade(emergencia, 4).
prioridade(urgencia, 3).
prioridade(consulta_medica, 2).
prioridade(autocuidados, 1).

% ---------------------------------
% FATORES DE RISCO
% ---------------------------------
fator_risco :-
    resposta(doenca_respiratoria_previa, sim).

fator_risco :-
    resposta(imunossupressao, sim).

idade_risco :-
    resposta(idade, Idade),
    Idade =< 5.

idade_risco :-
    resposta(idade, Idade),
    Idade >= 65.

fator_risco :-
    idade_risco.

% ---------------------------------
% CONCEITOS CLINICOS INTERMEDIOS
% ---------------------------------
sinal_alarme :-
    resposta(dificuldade_respiratoria, grave).

sinal_alarme :-
    resposta(dificuldade_respiratoria, moderada),
    resposta(limitacao_respiratoria, significativa).

sinal_alarme :-
    resposta(dificuldade_respiratoria, moderada),
    resposta(dor_toracica, forte).

sinal_alarme :-
    resposta(dor_toracica, forte).

compromisso_respiratorio :-
    resposta(dificuldade_respiratoria, moderada).

compromisso_respiratorio :-
    resposta(pieira, sim),
    resposta(dificuldade_respiratoria, ligeira),
    resposta(limitacao_respiratoria, alguma).

compromisso_respiratorio :-
    resposta(limitacao_respiratoria, significativa).

quadro_infecioso_relevante :-
    resposta(febre, alta).

quadro_infecioso_relevante :-
    resposta(febre, moderada),
    resposta(duracao_prolongada, sim).

caso_persistente :-
    resposta(duracao_prolongada, sim).

caso_agravado :-
    resposta(agravamento, sim).

caso_ligeiro_vias_superiores :-
    resposta(congestao_nasal, sim),
    resposta(dor_garganta, sim),
    resposta(febre, nenhuma),
    resposta(dificuldade_respiratoria, nenhuma),
    resposta(agravamento, nao),
    resposta(duracao_prolongada, nao).

tosse_ligeira_isolada :-
    resposta(tosse, sim),
    resposta(febre, nenhuma),
    resposta(dificuldade_respiratoria, nenhuma),
    resposta(dor_toracica, nenhuma),
    resposta(agravamento, nao),
    resposta(duracao_prolongada, nao).

% ---------------------------------
% REGRAS DE EMERGENCIA
% ---------------------------------
regra(emergencia) :-
    sinal_alarme.
    
% ---------------------------------
% REGRAS DE URGENCIA
% ---------------------------------

regra(urgencia) :-
    quadro_infecioso_relevante,
    compromisso_respiratorio.

regra(urgencia) :-
    resposta(pieira, sim),
    resposta(dificuldade_respiratoria, moderada).

regra(urgencia) :-
    resposta(dor_toracica, moderada),
    compromisso_respiratorio.

regra(urgencia) :-
    fator_risco,
    resposta(febre, alta).

regra(urgencia) :-
    fator_risco,
    resposta(dificuldade_respiratoria, ligeira),
    resposta(agravamento, sim).

regra(urgencia) :-
    compromisso_respiratorio,
    caso_agravado.

% ---------------------------------
% REGRAS DE CONSULTA MEDICA
% ---------------------------------

regra(consulta_medica) :-
    resposta(tosse, sim),
    caso_agravado,
    resposta(dificuldade_respiratoria, nenhuma),
    resposta(dor_toracica, nenhuma).

regra(consulta_medica) :-
    resposta(tosse, sim),
    resposta(febre, moderada),
    caso_persistente.

regra(consulta_medica) :-
    resposta(febre, alta),
    resposta(dificuldade_respiratoria, nenhuma).

regra(consulta_medica) :-
    resposta(dor_toracica, ligeira),
    resposta(dificuldade_respiratoria, nenhuma).

regra(consulta_medica) :-
    resposta(limitacao_respiratoria, alguma),
    resposta(dificuldade_respiratoria, ligeira).

regra(consulta_medica) :-
    fator_risco,
    resposta(tosse, sim),
    caso_persistente.

regra(consulta_medica) :-
    fator_risco,
    resposta(tosse, sim),
    caso_agravado.

regra(consulta_medica) :-
    fator_risco,
    resposta(tosse, sim),
    resposta(febre, moderada).

regra(consulta_medica) :-
    fator_risco,
    resposta(tosse, sim),
    resposta(febre, alta).

regra(consulta_medica) :-
    fator_risco,
    caso_persistente.

regra(consulta_medica) :-
    resposta(pieira, sim),
    resposta(dificuldade_respiratoria, nenhuma).

regra(consulta_medica) :-
    caso_persistente,
    caso_agravado,
    resposta(dificuldade_respiratoria, nenhuma).

regra(consulta_medica) :-
    resposta(febre, moderada),
    caso_persistente,
    resposta(dificuldade_respiratoria, nenhuma).

% ---------------------------------
% REGRAS DE AUTOCUIDADOS
% ---------------------------------

regra(autocuidados) :-
    caso_ligeiro_vias_superiores.

regra(autocuidados) :-
    tosse_ligeira_isolada.%