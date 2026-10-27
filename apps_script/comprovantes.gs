/**
 * Controle de Veículo Granado - comprovantes de retorno.
 * Copie para Extensões > Apps Script na planilha oficial.
 * NÃO ENVIA EMAILS enquanto ATIVAR_ENVIOS for false.
 * Nunca usa gatilho onEdit: o Streamlit escreve via API.
 */
const CFG = Object.freeze({
  PLANILHA_ID: '1GJ6mor6s3-2CKxU_Rlt9_Dtv-b_G0t5atRW5QY1gZ2c',
  ABA_HISTORICO: 'HISTORICO_MONTANA',
  ABA_AUTORIZADOS: 'Autorizados ', // Há um espaço no final do nome real.
  ATIVAR_ENVIOS: false,
  REMETENTE_NOME: 'Controle de Veículo Granado',
  MAX_POR_EXECUCAO: 20,
});

function obterAbas_() {
  const planilha = SpreadsheetApp.openById(CFG.PLANILHA_ID);
  const historico = planilha.getSheetByName(CFG.ABA_HISTORICO);
  const autorizados = planilha.getSheetByName(CFG.ABA_AUTORIZADOS);
  if (!historico || !autorizados) {
    throw new Error('Confira os nomes das abas HISTORICO_MONTANA e Autorizados (com espaço final).');
  }
  return { historico, autorizados };
}

function normalizarNome_(valor) {
  return String(valor == null ? '' : valor).trim().replace(/\s+/g, ' ').toLocaleLowerCase('pt-BR');
}

function emailsAutorizados_(aba) {
  const mapa = new Map();
  const ultima = aba.getLastRow();
  if (ultima < 7) return mapa;
  const linhas = aba.getRange(7, 2, ultima - 6, 2).getDisplayValues(); // B:C
  linhas.forEach(([nome, email]) => {
    const chave = normalizarNome_(nome);
    const destino = String(email || '').trim();
    if (!chave || !destino) return;
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(destino)) {
      throw new Error('E-mail inválido para motorista: ' + nome);
    }
    if (mapa.has(chave) && mapa.get(chave) !== destino) {
      throw new Error('E-mails divergentes para o mesmo motorista: ' + nome);
    }
    mapa.set(chave, destino);
  });
  return mapa;
}

function prepararComprovante_(linha) {
  const [data, motorista, destino, saida, kmSaida, retorno, kmRetorno,
    obsSaida, obsRetorno, aceite, , dataAceite, status, combustivel] = linha;
  const numero = valor => Number(String(valor).replace(/\./g, '').replace(',', '.'));
  const kmInicial = numero(kmSaida);
  const kmFinal = numero(kmRetorno);
  const distancia = Number.isFinite(kmInicial) && Number.isFinite(kmFinal) && kmFinal >= kmInicial
    ? String(kmFinal - kmInicial) + ' km' : 'Não calculada';
  const campos = [
    ['Data', data], ['Motorista', motorista], ['Destino', destino],
    ['Hora de saída', saida], ['Hora de retorno', retorno],
    ['KM de saída', kmSaida], ['KM de retorno', kmRetorno],
    ['Distância percorrida', distancia],
    ['Combustível no retorno', combustivel],
    ['Observações na saída', obsSaida || 'Nenhuma'],
    ['Observações no retorno', obsRetorno || 'Nenhuma'],
    ['Política de utilização aceita', aceite || 'Não informado'],
  ];
  const corpo = 'Olá, ' + motorista + '!\n\n' +
    'Seu registro de utilização do veículo Montana foi concluído.\n\n' +
    campos.map(([chave, valor]) => chave + ': ' + String(valor || '')).join('\n') +
    '\n\nEste é um comprovante automático do Controle de Veículo Granado.';
  return {
    assunto: 'Comprovante de utilização da Montana - ' + data,
    corpo,
  };
}

function registrosPendentes_() {
  const { historico, autorizados } = obterAbas_();
  const mapa = emailsAutorizados_(autorizados);
  const ultima = historico.getLastRow();
  if (ultima < 2) return { historico, pendentes: [] };
  const linhas = historico.getRange(2, 1, ultima - 1, 14).getDisplayValues(); // A:N
  const pendentes = [];
  linhas.forEach((linha, indice) => {
    const numeroLinha = indice + 2;
    const motorista = linha[1];
    const horaRetorno = linha[5]; // F
    const kmRetorno = linha[6]; // G
    const status = String(linha[12] || '').trim().toUpperCase(); // M
    const combustivel = linha[13]; // N
    // Apenas retornos completos com combustível. Nunca reenviar ENVIADO/ERRO.
    if (!motorista || !horaRetorno || !kmRetorno || !combustivel || status) return;
    pendentes.push({
      numeroLinha, motorista, email: mapa.get(normalizarNome_(motorista)) || '',
      comprovante: prepararComprovante_(linha),
    });
  });
  return { historico, pendentes };
}

/** Primeiro teste: apenas mostra no log, NÃO envia nem altera células. */
function simularEnvios() {
  const { pendentes } = registrosPendentes_();
  Logger.log('Registros elegíveis: ' + pendentes.length);
  pendentes.slice(0, CFG.MAX_POR_EXECUCAO).forEach(item => {
    Logger.log('Linha ' + item.numeroLinha + ' | ' + item.motorista +
      ' | ' + (item.email || 'SEM EMAIL') + '\n' +
      item.comprovante.assunto + '\n' + item.comprovante.corpo);
  });
}

/**
 * Executar manualmente só após aprovação do teste.
 * Instalar gatilho baseado em tempo de 5 minutos somente após habilitar envios.
 */
function processarComprovantes() {
  if (!CFG.ATIVAR_ENVIOS) {
    Logger.log('Envios desativados. Execute simularEnvios para conferir.');
    return;
  }
  const bloqueio = LockService.getScriptLock();
  if (!bloqueio.tryLock(1000)) return;
  try {
    const { historico, pendentes } = registrosPendentes_();
    let enviados = 0;
    for (const item of pendentes) {
      if (enviados >= CFG.MAX_POR_EXECUCAO) break;
      const celulaStatus = historico.getRange(item.numeroLinha, 13); // M
      if (String(celulaStatus.getDisplayValue()).trim()) continue;
      if (!item.email) {
        celulaStatus.setValue('ERRO: email não encontrado');
        continue;
      }
      try {
        MailApp.sendEmail({
          to: item.email,
          subject: item.comprovante.assunto,
          body: item.comprovante.corpo,
          name: CFG.REMETENTE_NOME,
        });
        celulaStatus.setValue('ENVIADO ' +
          Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'dd/MM/yyyy HH:mm:ss'));
        enviados++;
      } catch (erro) {
        celulaStatus.setValue('ERRO: ' + String(erro.message || erro).slice(0, 160));
        console.error('Falha na linha ' + item.numeroLinha + ': ' + erro);
      }
    }
  } finally {
    bloqueio.releaseLock();
  }
}
