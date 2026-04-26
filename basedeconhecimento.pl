% ---------------------------------
% BASE DE CONHECIMENTO
% Triagem de Sintomas Respiratorios
% ---------------------------------

% =========================================================
% 1. TIPOS DE DADOS
% =========================================================

% Sintomas / condicoes binarias
sintoma_binario(tosse).
sintoma_binario(pieira).
sintoma_binario(dor_garganta).
sintoma_binario(congestao_nasal).
sintoma_binario(agravamento).
sintoma_binario(duracao_prolongada).
sintoma_binario(doenca_respiratoria_previa).
sintoma_binario(imunossupressao).

% Dados numericos
dado_numerico(idade).

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

% =========================================================
% 2. PERGUNTAS DO SISTEMA
% =========================================================

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

% =========================================================
% 3. VALIDACAO DE VALORES
% =========================================================

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

% =========================================================
% 4. PRIORIDADE DOS ENCAMINHAMENTOS
% =========================================================

prioridade(emergencia, 4).
prioridade(urgencia, 3).
prioridade(consulta_medica, 2).
prioridade(autocuidados, 1).

% =========================================================
% 5. FATORES DE RISCO
% =========================================================

idade_risco :-
    resposta(idade, Idade),
    Idade =< 5.

idade_risco :-
    resposta(idade, Idade),
    Idade >= 65.

fator_risco :-
    idade_risco.

fator_risco :-
    resposta(doenca_respiratoria_previa, sim).

fator_risco :-
    resposta(imunossupressao, sim).

% =========================================================
% 6. CONCEITOS CLINICOS INTERMEDIOS
% =========================================================

% -------------------------
% 6.1 Sinais de alarme
% -------------------------

sinal_alarme :-
    resposta(dificuldade_respiratoria, grave).

sinal_alarme :-
    resposta(limitacao_respiratoria, significativa),
    resposta(dificuldade_respiratoria, moderada).

sinal_alarme :-
    resposta(dor_toracica, forte).

sinal_alarme :-
    resposta(dificuldade_respiratoria, moderada),
    resposta(dor_toracica, moderada),
    resposta(agravamento, sim).

% -------------------------
% 6.2 Compromisso respiratorio
% -------------------------

compromisso_respiratorio_importante :-
    resposta(dificuldade_respiratoria, moderada).

compromisso_respiratorio_importante :-
    resposta(limitacao_respiratoria, significativa).

compromisso_respiratorio_ligeiro :-
    resposta(dificuldade_respiratoria, ligeira).

compromisso_respiratorio_ligeiro :-
    resposta(limitacao_respiratoria, alguma).

compromisso_respiratorio_ligeiro :-
    resposta(pieira, sim),
    resposta(dificuldade_respiratoria, nenhuma).

sem_compromisso_respiratorio :-
    resposta(dificuldade_respiratoria, nenhuma),
    resposta(limitacao_respiratoria, nenhuma).

% -------------------------
% 6.3 Gravidade infecciosa
% -------------------------

febre_relevante :-
    resposta(febre, alta).

febre_relevante :-
    resposta(febre, moderada),
    resposta(duracao_prolongada, sim).

quadro_infecioso_relevante :-
    febre_relevante.

quadro_infecioso_relevante :-
    resposta(febre, moderada),
    resposta(agravamento, sim).

% -------------------------
% 6.4 Evolucao temporal
% -------------------------

caso_persistente :-
    resposta(duracao_prolongada, sim).

caso_agravado :-
    resposta(agravamento, sim).

% -------------------------
% 6.5 Dor toracica
% -------------------------

dor_toracica_relevante :-
    resposta(dor_toracica, moderada).

dor_toracica_relevante :-
    resposta(dor_toracica, forte).

% -------------------------
% 6.6 Casos ligeiros
% -------------------------

caso_ligeiro_vias_superiores :-
    resposta(dor_garganta, sim),
    resposta(congestao_nasal, sim),
    resposta(febre, nenhuma),
    sem_compromisso_respiratorio,
    resposta(dor_toracica, nenhuma),
    resposta(agravamento, nao),
    resposta(duracao_prolongada, nao).

tosse_ligeira_isolada :-
    resposta(tosse, sim),
    resposta(febre, nenhuma),
    sem_compromisso_respiratorio,
    resposta(dor_toracica, nenhuma),
    resposta(agravamento, nao),
    resposta(duracao_prolongada, nao),
    resposta(pieira, nao).

caso_ligeiro_sem_risco :-
    caso_ligeiro_vias_superiores,
    \+ fator_risco.

caso_ligeiro_sem_risco :-
    tosse_ligeira_isolada,
    \+ fator_risco.

% =========================================================
% 7. REGRAS DE ENCAMINHAMENTO COM MOTIVO
% =========================================================

% A ideia aqui e ter regras explicaveis:
% regra_com_motivo(Encaminhamento, Motivo).
% Mais tarde a inferencia pode reutilizar estes motivos.

% -------------------------
% 7.1 Emergencia
% -------------------------

regra_com_motivo(emergencia,
    'Presenca de sinal de alarme respiratorio ou toracico.') :-
    sinal_alarme.

% -------------------------
% 7.2 Urgencia
% -------------------------

regra_com_motivo(urgencia,
    'Febre relevante associada a compromisso respiratorio importante.') :-
    quadro_infecioso_relevante,
    compromisso_respiratorio_importante.

regra_com_motivo(urgencia,
    'Pieira associada a dificuldade respiratoria moderada.') :-
    resposta(pieira, sim),
    resposta(dificuldade_respiratoria, moderada).

regra_com_motivo(urgencia,
    'Dor toracica relevante associada a compromisso respiratorio.') :-
    dor_toracica_relevante,
    (compromisso_respiratorio_importante ; compromisso_respiratorio_ligeiro).

regra_com_motivo(urgencia,
    'Doente de risco com febre alta.') :-
    fator_risco,
    resposta(febre, alta).

regra_com_motivo(urgencia,
    'Doente de risco com agravamento e dificuldade respiratoria.') :-
    fator_risco,
    caso_agravado,
    (compromisso_respiratorio_importante ; compromisso_respiratorio_ligeiro).

regra_com_motivo(urgencia,
    'Compromisso respiratorio com agravamento clinico.') :-
    caso_agravado,
    compromisso_respiratorio_importante.

% -------------------------
% 7.3 Consulta medica
% -------------------------

regra_com_motivo(consulta_medica,
    'Tosse com agravamento, sem criterios de urgencia.') :-
    resposta(tosse, sim),
    caso_agravado,
    sem_compromisso_respiratorio,
    resposta(dor_toracica, nenhuma).

regra_com_motivo(consulta_medica,
    'Tosse com febre moderada e duracao prolongada.') :-
    resposta(tosse, sim),
    resposta(febre, moderada),
    caso_persistente,
    sem_compromisso_respiratorio.

regra_com_motivo(consulta_medica,
    'Febre alta sem dificuldade respiratoria.') :-
    resposta(febre, alta),
    sem_compromisso_respiratorio.

regra_com_motivo(consulta_medica,
    'Dor toracica ligeira sem compromisso respiratorio.') :-
    resposta(dor_toracica, ligeira),
    sem_compromisso_respiratorio.

regra_com_motivo(consulta_medica,
    'Limitacao respiratoria ligeira sem criterios de urgencia.') :-
    resposta(limitacao_respiratoria, alguma),
    resposta(dificuldade_respiratoria, ligeira).

regra_com_motivo(consulta_medica,
    'Doente de risco com tosse persistente ou em agravamento.') :-
    fator_risco,
    resposta(tosse, sim),
    (caso_persistente ; caso_agravado).

regra_com_motivo(consulta_medica,
    'Doente de risco com tosse e febre.') :-
    fator_risco,
    resposta(tosse, sim),
    (resposta(febre, moderada) ; resposta(febre, alta)).

regra_com_motivo(consulta_medica,
    'Doente de risco com duracao prolongada dos sintomas.') :-
    fator_risco,
    caso_persistente.

regra_com_motivo(consulta_medica,
    'Pieira sem dificuldade respiratoria marcada.') :-
    resposta(pieira, sim),
    resposta(dificuldade_respiratoria, nenhuma).

regra_com_motivo(consulta_medica,
    'Sintomas persistentes com agravamento, sem sinais de alarme.') :-
    caso_persistente,
    caso_agravado,
    sem_compromisso_respiratorio.

regra_com_motivo(consulta_medica,
    'Febre moderada persistente, sem compromisso respiratorio.') :-
    resposta(febre, moderada),
    caso_persistente,
    sem_compromisso_respiratorio.

% -------------------------
% 7.4 Autocuidados
% -------------------------

regra_com_motivo(autocuidados,
    'Quadro ligeiro de vias respiratorias superiores, sem fatores de risco.') :-
    caso_ligeiro_sem_risco,
    caso_ligeiro_vias_superiores.

regra_com_motivo(autocuidados,
    'Tosse ligeira isolada, sem fatores de risco nem sinais de gravidade.') :-
    caso_ligeiro_sem_risco,
    tosse_ligeira_isolada.

% =========================================================
% 8. REGRA FINAL (COMPATIBILIDADE COM O RESTO DO PROJETO)
% =========================================================

regra(Encaminhamento) :-
    regra_com_motivo(Encaminhamento, _).

% =========================================================
% 9. SISTEMA DE PONTUACAO CLINICA
% =========================================================

% -------------------------
% 9.1 Idade
% -------------------------

pontuacao_resposta(idade, Idade, 10) :-
    integer(Idade),
    (Idade =< 5 ; Idade >= 65), !.
pontuacao_resposta(idade, _, 0).

% -------------------------
% 9.2 Sintomas binarios
% -------------------------

pontuacao_resposta(tosse, sim, 5).
pontuacao_resposta(tosse, nao, 0).

pontuacao_resposta(pieira, sim, 12).
pontuacao_resposta(pieira, nao, 0).

pontuacao_resposta(dor_garganta, sim, 3).
pontuacao_resposta(dor_garganta, nao, 0).

pontuacao_resposta(congestao_nasal, sim, 2).
pontuacao_resposta(congestao_nasal, nao, 0).

pontuacao_resposta(agravamento, sim, 15).
pontuacao_resposta(agravamento, nao, 0).

pontuacao_resposta(duracao_prolongada, sim, 10).
pontuacao_resposta(duracao_prolongada, nao, 0).

pontuacao_resposta(doenca_respiratoria_previa, sim, 10).
pontuacao_resposta(doenca_respiratoria_previa, nao, 0).

pontuacao_resposta(imunossupressao, sim, 15).
pontuacao_resposta(imunossupressao, nao, 0).

% -------------------------
% 9.3 Sintomas por nivel
% -------------------------

pontuacao_resposta(febre, nenhuma, 0).
pontuacao_resposta(febre, moderada, 10).
pontuacao_resposta(febre, alta, 20).

pontuacao_resposta(dificuldade_respiratoria, nenhuma, 0).
pontuacao_resposta(dificuldade_respiratoria, ligeira, 15).
pontuacao_resposta(dificuldade_respiratoria, moderada, 30).
pontuacao_resposta(dificuldade_respiratoria, grave, 45).

pontuacao_resposta(dor_toracica, nenhuma, 0).
pontuacao_resposta(dor_toracica, ligeira, 8).
pontuacao_resposta(dor_toracica, moderada, 20).
pontuacao_resposta(dor_toracica, forte, 35).

pontuacao_resposta(limitacao_respiratoria, nenhuma, 0).
pontuacao_resposta(limitacao_respiratoria, alguma, 10).
pontuacao_resposta(limitacao_respiratoria, significativa, 25).


