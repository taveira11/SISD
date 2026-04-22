const express = require("express");
const path = require("path");
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
      const motivosMatch = stdout.match(/MOTIVOS=(.*)/);
      const outrosMatch = stdout.match(/OUTROS=(.*)/);

      const resultado = resultadoMatch ? resultadoMatch[1].trim() : "indefinido";
      const motivos = motivosMatch ? motivosMatch[1].trim() : "[]";
      const outros = outrosMatch ? outrosMatch[1].trim() : "[]";

      const resultadoLabel = formatarTexto(resultado);
      const badgeClass = classeResultado(resultado);
      const descricao = descricaoResultado(resultado);

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
                  <p class="eyebrow">Projeto Académico · Técnicas de Inteligência Artificial</p>
                  <h1>Sistema de Triagem Respiratória</h1>
                  <p class="subtitle">
                    Resultado gerado automaticamente pelo sistema de inferência clínica.
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

                <div class="result-grid">
                  <section class="info-card">
                    <h3>Motivos principais</h3>
                    <pre class="result-box">${motivos}</pre>
                  </section>

                  <section class="info-card">
                    <h3>Outros encaminhamentos considerados</h3>
                    <pre class="result-box">${outros}</pre>
                  </section>
                </div>

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