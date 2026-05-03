# SISD


# SISD - Triagem de Sintomas Respiratórios (SNS24)

## Descrição do projeto

Este projeto consiste no desenvolvimento de um **Sistema Inteligente de Suporte à Decisão (SISD)** para a **triagem de sintomas respiratórios**, inspirado no serviço **SNS24**.

O sistema foi desenvolvido no contexto da unidade curricular de **Sistemas Inteligentes de Apoio à Decisão / Técnicas de Inteligência Artificial** e combina:

- **representação de conhecimento em Prolog**
- **inferência baseada em regras**
- **geração automática de base de dados sintética em Python**
- **aprendizagem automática com árvores de decisão**
- **extração de regras para apoio à construção da base de conhecimento**

---

## Objetivo

O objetivo principal é apoiar a decisão de encaminhamento clínico de um doente com sintomas respiratórios, classificando o caso num dos seguintes níveis:

- `autocuidados`
- `consulta_medica`
- `urgencia`
- `emergencia`

---

## Estrutura do projeto

O projeto encontra-se organizado da seguinte forma:

- `basedeconhecimento.pl`  
  Base de conhecimento principal em Prolog. Contém:
  - definição dos tipos de dados
  - sintomas binários
  - sintomas por níveis
  - fatores de risco
  - conceitos clínicos intermédios
  - regras de encaminhamento

- `basededados.pl`  
  Base de dados dinâmica usada pelo sistema para guardar respostas durante a triagem.

- `inferencia.pl`  
  Motor de inferência em Prolog, responsável por aplicar as regras e obter o encaminhamento final.

- `interface.pl`  
  Ficheiro de apoio à interação com o utilizador em Prolog.  
  **Nota:** dependendo da versão final do projeto, este ficheiro pode estar pouco utilizado ou redundante relativamente à interface web / servidor.

- `db.py`  
  Script em Python responsável por:
  - gerar casos sintéticos coerentes
  - aplicar regras de decisão
  - criar a base de dados final em CSV para modelação

- `triagem_sintetica.csv`  
  Base de dados sintética final usada na fase de aprendizagem automática.

- `historico_triagens.csv`  
  Histórico de triagens executadas na interface, caso essa funcionalidade esteja ativa.

- `modelagem.ipynb`  
  Notebook com a análise exploratória dos dados e treino de modelos de árvores de decisão.

- `server.js`  
  Servidor usado para ligar a interface web à lógica do sistema, se aplicável.

- `public/`  
  Ficheiros da interface web.

- `package.json` / `package-lock.json`  
  Dependências do ambiente Node.js.

---

## Lógica do sistema

A triagem é baseada em:

- sintomas binários:
  - tosse
  - pieira
  - dor de garganta
  - congestão nasal
  - agravamento
  - duração prolongada
  - doença respiratória prévia
  - imunossupressão

- dado numérico:
  - idade

- sintomas com níveis:
  - febre: `nenhuma`, `moderada`, `alta`
  - dificuldade respiratória: `nenhuma`, `ligeira`, `moderada`, `grave`
  - dor torácica: `nenhuma`, `ligeira`, `moderada`, `forte`
  - limitação respiratória: `nenhuma`, `alguma`, `significativa`

Com base nestes dados, o sistema determina o encaminhamento adequado.

---

## Requisitos

### Prolog
É necessário ter uma instalação de **SWI-Prolog**.

### Python
É necessário ter Python 3 instalado, com as bibliotecas:

- `pandas`
- `scikit-learn`
- `matplotlib`
- `jupyter`

### Node.js
Se for usada a interface web, é necessário ter **Node.js** instalado.

---

## Como executar a parte em Prolog

Abrir o SWI-Prolog e carregar os ficheiros principais:

```prolog
['basedeconhecimento.pl'].
['basededados.pl'].
['inferencia.pl'].
