const express = require("express");
const path = require("path");
const fs = require("fs");
const { execFile } = require("child_process");

const app = express();
const PORT = 3000;

app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, "public")));

function escaparAtom(valor) {
  return `'${String(valor).replace(/'/g, "\\'")}'`;
}

function formatarTexto(valor) {
  return String(valor || "")
    .replaceAll("_", " ")
    .trim();
}

function descricaoResultado(resultado) {
  switch (resultado) {
    case "emergencia":
      return "O caso apresenta critérios de gravidade elevada e requer observação imediata.";
    case "urgencia":
      return "O caso sugere necessidade de avaliação clínica urgente no próprio dia.";
    case "consulta_medica":
      return "O caso recomenda observação médica programada, sem critérios atuais de urgência máxima.";
    case "autocuidados":
      return "O caso aparenta ser ligeiro, sendo compatível com medidas de autocuidado e vigilância.";
    default:
      return "Não foi possível gerar uma descrição para o resultado obtido.";
  }
}

function classeResultado(resultado) {
  switch (resultado) {
    case "emergencia":
      return "badge badge-emergencia";
    case "urgencia":
      return "badge badge-urgencia";
    case "consulta_medica":
      return "badge badge-consulta";
    case "autocuidados":
      return "badge badge-autocuidados";
    default:
      return "badge badge-consulta";
  }
}

function classeFaixa(faixa) {
  switch (faixa) {
    case "emergencia":
      return "metric-card metric-emergencia";
    case "urgencia":
      return "metric-card metric-urgencia";
    case "consulta_medica":
      return "metric-card metric-consulta";
    case "autocuidados":
      return "metric-card metric-autocuidados";
    default:
      return "metric-card";
  }
}

function valorBarra(score) {
  const numero = Number(score);
  if (Number.isNaN(numero)) return 0;
  return Math.max(0, Math.min(100, numero));
}

function parseListaProlog(raw) {
  const texto = String(raw || "").trim();

  if (!texto || texto === "[]") return [];

  const semColchetes = texto.replace(/^\[/, "").replace(/\]$/, "").trim();
  if (!semColchetes) return [];

  return semColchetes
    .split(/,(?=(?:[^']*'[^']*')*[^']*$)/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const limpo = item.replace(/^'(.*)'$/, "$1");
      return formatarTexto(limpo);
    });
}

function parseParesEncaminhamento(raw) {
  const texto = String(raw || "").trim();

  if (!texto || texto === "[]") return [];

  const matches = [...texto.matchAll(/([a-z_]+)-'([^']+)'/g)];
  return matches.map((m) => ({
    encaminhamento: formatarTexto(m[1]),
    motivo: m[2].trim(),
  }));
}

function renderListaMotivos(motivos) {
  if (!motivos.length) {
    return `<li>Sem explicação disponível.</li>`;
  }

  return motivos.map((motivo) => `<li>${motivo}</li>`).join("");
}

function renderListaOutros(outros) {
  if (!outros.length) {
    return `<li>Nenhum encaminhamento adicional.</li>`;
  }

  return outros
    .map(
      (item) => `
        <li>
          <strong>${item.encaminhamento}</strong>
          <span>${item.motivo}</span>
        </li>
      `
    )
    .join("");
}

function guardarHistoricoTriagem(dados) {
  const ficheiro = path.join(__dirname, "historico_triagens.csv");

  if (!fs.existsSync(ficheiro)) {
    const header =
      "timestamp,idade,tosse,pieira,dor_garganta,congestao_nasal,agravamento,duracao_prolongada,doenca_respiratoria_previa,imunossupressao,febre,dificuldade_respiratoria,dor_toracica,limitacao_respiratoria,encaminhamento,score,faixa\n";
    fs.writeFileSync(ficheiro, header, "utf8");
  }

  const linha = [
    new Date().toISOString(),
    dados.idade,
    dados.tosse,
    dados.pieira,
    dados.dor_garganta,
    dados.congestao_nasal,
    dados.agravamento,
    dados.duracao_prolongada,
    dados.doenca_respiratoria_previa,
    dados.imunossupressao,
    dados.febre,
    dados.dificuldade_respiratoria,
    dados.dor_toracica,
    dados.limitacao_respiratoria,
    dados.encaminhamento,
    dados.score,
    dados.faixa,
  ].join(",") + "\n";

  fs.appendFileSync(ficheiro, linha, "utf8");
}

app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

app.post("/triagem", (req, res) => {
  const {
    idade,
    tosse,
    pieira,
    dor_garganta,
    congestao_nasal,
    agravamento,
    duracao_prolongada,
    doenca_respiratoria_previa,
    imunossupressao,
    febre,
    dificuldade_respiratoria,
    dor_toracica,
    limitacao_respiratoria,
  } = req.body;

  const goal = `
    executar_api(
      ${Number(idade)},
      ${escaparAtom(tosse)},
      ${escaparAtom(pieira)},
      ${escaparAtom(dor_garganta)},
      ${escaparAtom(congestao_nasal)},
      ${escaparAtom(agravamento)},
      ${escaparAtom(duracao_prolongada)},
      ${escaparAtom(doenca_respiratoria_previa)},
      ${escaparAtom(imunossupressao)},
      ${escaparAtom(febre)},
      ${escaparAtom(dificuldade_respiratoria)},
      ${escaparAtom(dor_toracica)},
      ${escaparAtom(limitacao_respiratoria)}
    )
  `;

  execFile(
    "swipl",
    ["-q", "-s", "api.pl", "-g", goal, "-t", "halt"],
    { cwd: __dirname },
    (error, stdout, stderr) => {
      if (error) {
        res.status(500).send(`
          <h1>Erro ao executar o Prolog</h1>
          <pre>${stderr || error.message}</pre>
        `);
        return;
      }

      const resultadoMatch = stdout.match(/RESULTADO=(.*)/);
      const scoreMatch = stdout.match(/SCORE=(.*)/);
      const faixaMatch = stdout.match(/FAIXA=(.*)/);
      const motivosMatch = stdout.match(/MOTIVOS=(.*)/);
      const outrosMatch = stdout.match(/OUTROS=(.*)/);

      const resultado = resultadoMatch ? resultadoMatch[1].trim() : "indefinido";
      const score = scoreMatch ? scoreMatch[1].trim() : "0";
      const faixa = faixaMatch ? faixaMatch[1].trim() : "autocuidados";
      const motivosRaw = motivosMatch ? motivosMatch[1].trim() : "[]";
      const outrosRaw = outrosMatch ? outrosMatch[1].trim() : "[]";

      const resultadoLabel = formatarTexto(resultado);
      const faixaLabel = formatarTexto(faixa);
      const badgeClass = classeResultado(resultado);
      const descricao = descricaoResultado(resultado);
      const metricClass = classeFaixa(faixa);
      const barra = valorBarra(score);

      const motivos = parseListaProlog(motivosRaw);
      const outros = parseParesEncaminhamento(outrosRaw);

      guardarHistoricoTriagem({
        idade,
        tosse,
        pieira,
        dor_garganta,
        congestao_nasal,
        agravamento,
        duracao_prolongada,
        doenca_respiratoria_previa,
        imunossupressao,
        febre,
        dificuldade_respiratoria,
        dor_toracica,
        limitacao_respiratoria,
        encaminhamento: resultado,
        score,
        faixa,
      });

      res.send(`
        <!DOCTYPE html>
        <html lang="pt">
        <head>
          <meta charset="UTF-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          <title>Resultado da Triagem</title>
          <link rel="stylesheet" href="/style.css" />
        </head>
        <body>
          <div class="page-shell">
            <header class="topbar">
              <div class="brand-wrap">
                <div class="brand-icon">+</div>
                <div>
                  <p class="eyebrow">Projeto Académico · Sistemas Inteligentes de Apoio à Decisão</p>
                  <h1>Sistema de Triagem Respiratória</h1>
                  <p class="subtitle">
                    Resultado gerado automaticamente com base nas regras de inferência e no índice de gravidade clínica.
                  </p>
                </div>
              </div>
            </header>

            <main class="main-content">
              <section class="result-card">
                <div class="result-header">
                  <div class="result-title">
                    <span class="section-tag">Resultado da triagem</span>
                    <h2>Encaminhamento recomendado</h2>
                    <p>${descricao}</p>
                  </div>

                  <div class="${badgeClass}">${resultadoLabel}</div>
                </div>

                <section class="score-panel">
                  <div class="${metricClass}">
                    <span class="metric-label">Índice de gravidade</span>
                    <strong class="metric-value">${score}%</strong>
                    <span class="metric-subtitle">Pontuação global estimada pelo sistema</span>
                  </div>

                  <div class="metric-card">
                    <span class="metric-label">Faixa por pontuação</span>
                    <strong class="metric-value metric-text">${faixaLabel}</strong>
                    <span class="metric-subtitle">Classificação complementar baseada no score</span>
                  </div>
                </section>

                <section class="score-bar-card">
                  <div class="score-bar-header">
                    <h3>Escala de gravidade</h3>
                    <span>${score}%</span>
                  </div>

                  <div class="score-bar-track">
                    <div class="score-bar-fill" style="width: ${barra}%"></div>
                  </div>

                  <div class="score-scale">
                    <span>Autocuidados</span>
                    <span>Consulta médica</span>
                    <span>Urgência</span>
                    <span>Emergência</span>
                  </div>
                </section>

                <div class="result-grid">
                  <section class="info-card">
                    <h3>Motivos principais</h3>
                    <ul class="result-list">
                      ${renderListaMotivos(motivos)}
                    </ul>
                  </section>

                  <section class="info-card">
                    <h3>Outros encaminhamentos considerados</h3>
                    <ul class="result-list result-list-secondary">
                      ${renderListaOutros(outros)}
                    </ul>
                  </section>
                </div>

                <p class="method-note">
                  O encaminhamento final é determinado por regras clínicas. A pontuação apresentada funciona como indicador complementar de gravidade.
                </p>

                <div class="result-actions">
                  <a class="primary-btn" href="/">Nova triagem</a>
                </div>
              </section>
            </main>
          </div>
        </body>
        </html>
      `);
    }
  );
});

app.listen(PORT, () => {
  console.log(`Servidor ativo em http://localhost:${PORT}`);
});