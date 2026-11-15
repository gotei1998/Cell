// Бот «Клетки» для Cloudflare Workers: открывает приложение, принимает добровольную поддержку в Telegram Stars.
// Состояния у бота нет: всё, что нужно для возврата платежа, приходит владельцу сообщением.
// Настройка и запуск описаны в bot/README.md.

const API = 'https://api.telegram.org';
const DAY = 86400;
const STARS_MAX = 10000;

const TEXT = {
  start: (name) => `<b>Привет${name ? ', ' + name : ''}!</b>

Я «Клетка» — решаю задачи высшей математики <b>по шагам</b> и проверяю ответ.

<b>Что умею</b>
• производные и интегралы
• пределы, ряды, формула Тейлора
• матрицы, уравнения и системы
• логарифмы и дифференциальные уравнения

Нажмите кнопку ниже, введите задачу или загрузите её фото.`,
  help: `<b>Как пользоваться</b>

1. Откройте приложение кнопкой «Открыть Клетку».
2. Выберите тему и введите задачу как на бумаге:
<code>x^2 sin x</code>, <code>e^(2x)</code>, <code>ln(x+1)</code>, <code>|x-1|</code>, <code>n!</code>
3. Нажмите «Решить». Появятся ответ, шаги решения, график и теория по теме.

Бесконечность пишется как <code>oo</code>, число π как <code>pi</code>. Задачу можно сфотографировать.

<b>Команды</b>
/start — открыть приложение
/help — эта справка
/donate — поддержать проект
/paysupport — вопросы по оплате
/terms — условия`,
  donate: `<b>Поддержать проект</b>

«Клетка» бесплатна и останется бесплатной. Если она вам помогла, можно поддержать разработку звёздами Telegram. Это добровольно и ничего не открывает: все возможности доступны и так.

Выберите сумму:`,
  invoiceTitle: 'Поддержка «Клетки»',
  invoiceText: 'Добровольная поддержка проекта. Все возможности остаются бесплатными.',
  invoiceLabel: 'Поддержка проекта',
  thanks: (n) => `<b>Спасибо!</b> Получено ${n} ⭐.\n\nПоддержка помогает развивать «Клетку». Если платёж был ошибкой, напишите /paysupport — звёзды вернём.`,
  paysupport: (contact) => `<b>Вопросы по оплате</b>

Поддержка проекта добровольная, взамен ничего не продаётся. Если вы заплатили по ошибке, звёзды можно вернуть в течение 21 дня: ${contact ? 'напишите ' + contact : 'ответьте на это сообщение'} и укажите дату платежа.

Поддержка Telegram и BotFather с платежами этого бота не помогают.`,
  terms: `<b>Условия</b>

1. «Клетка» — бесплатный учебный инструмент. Ответы проверяются автоматически, но ошибки возможны: сверяйте важные решения сами.
2. Платежи в Telegram Stars — добровольная поддержка автора. Они не дают дополнительных функций и не являются покупкой товара или услуги.
3. Ошибочный платёж возвращается по обращению через /paysupport в течение 21 дня.
4. Бот не хранит ваши задачи: вычисления идут на вашем устройстве.`,
  fallback: 'Задачи решаются в приложении: там есть ввод формул, шаги решения и график.',
  groups: 'Я работаю в личном чате. Откройте меня и нажмите «Запустить».',
  open: 'Открыть Клетку',
  support: '⭐ Поддержать проект',
  about: 'Что умею',
  badAmount: 'Такой суммы нет. Выберите одну из предложенных.',
  badInvoice: 'Этот счёт устарел. Выберите сумму заново: /donate',
  refundUsage: 'Формат: /refund <id пользователя> <id платежа>',
  refundDone: 'Звёзды возвращены.',
  refundFail: (why) => `Вернуть не удалось: ${why}`,
};

const COMMANDS = [
  { command: 'start', description: 'Открыть приложение' },
  { command: 'help', description: 'Как пользоваться' },
  { command: 'donate', description: 'Поддержать проект' },
  { command: 'paysupport', description: 'Вопросы по оплате' },
  { command: 'terms', description: 'Условия' },
];

const DESCRIPTION = `«Клетка» решает задачи высшей математики по шагам и проверяет ответ.

Производные, интегралы, пределы, ряды, матрицы, уравнения, логарифмы и дифференциальные уравнения. Задачу можно ввести или сфотографировать.

Бесплатно. Нажмите «Запустить».`;
const SHORT_DESCRIPTION = 'Решает задачи высшей математики по шагам и проверяет ответ. Бесплатно.';

export function amounts(env) {
  const list = String(env.DONATE_AMOUNTS || '50,150,500').split(',').map((v) => parseInt(v, 10))
    .filter((n) => Number.isInteger(n) && n >= 1 && n <= STARS_MAX);
  return list.length ? list : [50, 150, 500];
}

async function call(env, method, params) {
  const res = await fetch(`${API}/bot${env.BOT_TOKEN}/${method}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(params || {}),
  });
  const data = await res.json().catch(() => ({ ok: false, description: `HTTP ${res.status}` }));
  if (!data.ok) console.error(`Telegram ${method}: ${data.description}`);
  return data;
}

const send = (env, chat, text, keyboard) => call(env, 'sendMessage', {
  chat_id: chat, text, parse_mode: 'HTML', link_preview_options: { is_disabled: true },
  ...(keyboard ? { reply_markup: { inline_keyboard: keyboard } } : {}),
});

const openButton = (env) => [{ text: TEXT.open, web_app: { url: env.WEBAPP_URL } }];
const startKeyboard = (env) => [openButton(env),
  [{ text: TEXT.support, callback_data: 'donate' }, { text: TEXT.about, callback_data: 'help' }]];
const donateKeyboard = (env) => [amounts(env).map((n) => ({ text: `${n} ⭐`, callback_data: `pay:${n}` }))];

function invoice(env, amount) {
  return {
    title: TEXT.invoiceTitle, description: TEXT.invoiceText, payload: `donate:${amount}`,
    provider_token: '', currency: 'XTR', prices: [{ label: TEXT.invoiceLabel, amount }],
  };
}

const escapeHtml = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

async function onCommand(env, message) {
  const chat = message.chat.id;
  const [raw, ...args] = message.text.trim().split(/\s+/);
  const command = raw.split('@')[0].toLowerCase();
  if (message.chat.type !== 'private') {
    return ['/start', '/help', '/donate'].includes(command) ? send(env, chat, TEXT.groups) : null;
  }
  switch (command) {
    case '/start':
      if (args[0] === 'donate') return send(env, chat, TEXT.donate, donateKeyboard(env));
      return send(env, chat, TEXT.start(escapeHtml(message.from && message.from.first_name || '')), startKeyboard(env));
    case '/help': return send(env, chat, TEXT.help, [openButton(env)]);
    case '/donate': return send(env, chat, TEXT.donate, donateKeyboard(env));
    case '/paysupport': return send(env, chat, TEXT.paysupport(escapeHtml(env.SUPPORT_CONTACT || '')));
    case '/terms': return send(env, chat, TEXT.terms);
    case '/refund': return onRefund(env, message, args);
    default: return send(env, chat, TEXT.fallback, [openButton(env)]);
  }
}

// Возврат делает только владелец: id платежа приходит ему в сообщении о каждом поступлении.
async function onRefund(env, message, args) {
  if (!env.ADMIN_ID || String(message.from.id) !== String(env.ADMIN_ID)) return send(env, message.chat.id, TEXT.fallback, [openButton(env)]);
  const [user, charge] = args;
  if (!/^\d+$/.test(user || '') || !charge) return send(env, message.chat.id, escapeHtml(TEXT.refundUsage));
  const res = await call(env, 'refundStarPayment', { user_id: Number(user), telegram_payment_charge_id: charge });
  return send(env, message.chat.id, res.ok ? TEXT.refundDone : TEXT.refundFail(escapeHtml(res.description || 'ошибка')));
}

async function onPayment(env, message) {
  const pay = message.successful_payment;
  await send(env, message.chat.id, TEXT.thanks(pay.total_amount));
  if (env.ADMIN_ID) {
    const who = message.from || {};
    await send(env, env.ADMIN_ID, `Поддержка: ${pay.total_amount} ⭐ от ${escapeHtml(who.first_name || '')}`
      + `${who.username ? ' @' + escapeHtml(who.username) : ''}.\nВозврат: <code>/refund ${who.id} ${escapeHtml(pay.telegram_payment_charge_id)}</code>`);
  }
}

async function onCallback(env, query) {
  const chat = query.message && query.message.chat.id;
  const data = query.data || '';
  let notice;
  if (chat) {
    if (data === 'donate') await send(env, chat, TEXT.donate, donateKeyboard(env));
    else if (data === 'help') await send(env, chat, TEXT.help, [openButton(env)]);
    else if (data.startsWith('pay:')) {
      const amount = Number(data.slice(4));
      if (amounts(env).includes(amount)) await call(env, 'sendInvoice', { chat_id: chat, ...invoice(env, amount) });
      else notice = TEXT.badAmount;
    }
  }
  return call(env, 'answerCallbackQuery', { callback_query_id: query.id, ...(notice ? { text: notice, show_alert: true } : {}) });
}

// Telegram ждёт ответа на этот запрос не дольше 10 секунд, иначе платёж отменяется.
function onPreCheckout(env, query) {
  const amount = Number(String(query.invoice_payload || '').replace(/^donate:/, ''));
  const ok = query.currency === 'XTR' && String(query.invoice_payload).startsWith('donate:') && amount === query.total_amount;
  return call(env, 'answerPreCheckoutQuery', { pre_checkout_query_id: query.id, ok, ...(ok ? {} : { error_message: TEXT.badInvoice }) });
}

export async function handleUpdate(env, update) {
  if (update.pre_checkout_query) return onPreCheckout(env, update.pre_checkout_query);
  if (update.callback_query) return onCallback(env, update.callback_query);
  const message = update.message;
  if (!message) return null;
  if (message.successful_payment) return onPayment(env, message);
  if (typeof message.text === 'string' && message.text.startsWith('/')) return onCommand(env, message);
  if (message.chat.type === 'private') return send(env, message.chat.id, TEXT.fallback, [openButton(env)]);
  return null;
}

// ---------- Проверка данных приложения ----------

const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');

async function hmac(key, text) {
  const k = await crypto.subtle.importKey('raw', typeof key === 'string' ? new TextEncoder().encode(key) : key,
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return crypto.subtle.sign('HMAC', k, new TextEncoder().encode(text));
}

function sameText(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// Подпись initData по документации Telegram: приложение доказывает, что его открыл настоящий пользователь бота.
export async function verifyInitData(initData, token, now = Date.now() / 1000) {
  const params = new URLSearchParams(String(initData || ''));
  const hash = params.get('hash');
  if (!hash) return null;
  params.delete('hash');
  const check = [...params.entries()].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)).map(([k, v]) => `${k}=${v}`).join('\n');
  const expected = hex(await hmac(await hmac('WebAppData', token), check));
  if (!sameText(expected, hash.toLowerCase())) return null;
  const age = now - Number(params.get('auth_date'));
  if (!(age >= -300 && age <= DAY)) return null;
  try { return JSON.parse(params.get('user')); } catch { return null; }
}

// ---------- HTTP ----------

function cors(env) {
  let origin = '*';
  try { origin = new URL(env.WEBAPP_URL).origin; } catch {}
  return { 'Access-Control-Allow-Origin': origin, 'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Max-Age': '86400', Vary: 'Origin' };
}

const json = (data, status = 200, headers = {}) => new Response(JSON.stringify(data), {
  status, headers: { 'Content-Type': 'application/json; charset=utf-8', ...headers },
});

async function apiInvoice(request, env) {
  const headers = cors(env);
  let body;
  try { body = await request.json(); } catch { return json({ error: 'bad request' }, 400, headers); }
  const user = await verifyInitData(body.initData, env.BOT_TOKEN);
  if (!user) return json({ error: 'unauthorized' }, 401, headers);
  const amount = Number(body.amount);
  if (!Number.isInteger(amount) || amount < 1 || amount > STARS_MAX) return json({ error: 'bad amount' }, 400, headers);
  const res = await call(env, 'createInvoiceLink', invoice(env, amount));
  return res.ok ? json({ link: res.result }, 200, headers) : json({ error: 'telegram' }, 502, headers);
}

// Одноразовая настройка бота: вебхук, команды, описания и кнопка меню.
async function setup(request, env) {
  const origin = new URL(request.url).origin;
  const steps = {
    setWebhook: { url: `${origin}/webhook`, secret_token: env.WEBHOOK_SECRET,
      allowed_updates: ['message', 'callback_query', 'pre_checkout_query'], drop_pending_updates: true },
    setMyCommands: { commands: COMMANDS },
    setMyDescription: { description: DESCRIPTION },
    setMyShortDescription: { short_description: SHORT_DESCRIPTION },
    setChatMenuButton: { menu_button: { type: 'web_app', text: 'Клетка', web_app: { url: env.WEBAPP_URL } } },
  };
  const out = {};
  for (const [method, params] of Object.entries(steps)) {
    const res = await call(env, method, params);
    out[method] = res.ok ? 'ok' : res.description || 'error';
  }
  return json(out);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!env.BOT_TOKEN || !env.WEBHOOK_SECRET || !env.WEBAPP_URL) return json({ error: 'bot is not configured' }, 500);
    if (url.pathname === '/webhook' && request.method === 'POST') {
      if (!sameText(request.headers.get('X-Telegram-Bot-Api-Secret-Token') || '', env.WEBHOOK_SECRET)) return json({ error: 'forbidden' }, 403);
      // Telegram повторяет запрос при любой ошибке, поэтому сбой обработки не должен превращаться в ответ с ошибкой.
      try { await handleUpdate(env, await request.json()); } catch (err) { console.error('update failed:', err && err.message); }
      return json({ ok: true });
    }
    if (url.pathname === '/api/invoice') {
      if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors(env) });
      if (request.method === 'POST') return apiInvoice(request, env);
    }
    if (url.pathname === '/setup' && request.method === 'GET') {
      if (!sameText(url.searchParams.get('key') || '', env.WEBHOOK_SECRET)) return json({ error: 'forbidden' }, 403);
      return setup(request, env);
    }
    if (url.pathname === '/' && request.method === 'GET') return json({ ok: true, bot: 'kletka' });
    return json({ error: 'not found' }, 404);
  },
};
