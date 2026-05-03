# SISD - Triagem de Sintomas Respiratórios

## Descrição

Este projeto implementa um **Sistema Inteligente de Suporte à Decisão (SISD)** para **triagem de sintomas respiratórios**, inspirado na lógica do SNS24.

O projeto integra:

- **Prolog** para representação de conhecimento e inferência
- **Node.js** para execução da interface web
- **Python** para geração de base de dados sintética e modelação com árvores de decisão

O sistema encaminha cada caso para uma das seguintes classes:

- `autocuidados`
- `consulta_medica`
- `urgencia`
- `emergencia`

---

## Estrutura do projeto

### Prolog
- `basedeconhecimento.pl` — base de conhecimento em Prolog
- `basededados.pl` — base de dados dinâmica em Prolog
- `inferencia.pl` — motor de inferência

### Node.js
- `server.js` — servidor Node.js
- `public/` — interface web
- `package.json` — dependências Node.js

### Python
- `db.py` — geração da base de dados sintética para a Parte B em Python
- `triagem_sintetica.csv` — base de dados final para modelação
- `historico_triagens.csv` — histórico de triagens originado pela interface
- `modelagem.ipynb` — notebook com análise e árvores de decisão

---

## Requisitos

### Prolog
É necessário ter **SWI-Prolog** instalado.

### Python
É necessário ter **Python 3** instalado, com as bibliotecas:

- `pandas`
- `scikit-learn`
- `matplotlib`
- `jupyter`

### Node.js
É necessário ter **Node.js** instalado.

---

## Como executar a interface principal (Node.js)

A forma principal de testar o sistema é através da interface web.

### 1. Abrir a pasta do projeto no terminal

### 2. Executar no terminal
node server.js
