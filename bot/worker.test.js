// Проверки бота без сети: запросы к Telegram перехватываются. Запуск: `npm test` в папке bot/.
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import worker, { amounts, handleUpdate, verifyInitData } from './worker.js';

const env = { BOT_TOKEN: '123456:TEST-TOKEN', WEBHOOK_SECRET: 'hook-secret', WEBAPP_URL: 'https://example.github.io/Cell/',
  DONATE_AMOUNTS: '50,150,500', ADMIN_ID: '777', SUPPORT_CONTACT: '@owner' };

let calls, replies;
beforeEach(() => {
  calls = [];
  replies = {};
  globalThis.fetch = async (url, init) => {
    const method = String(url).split('/').pop();
    assert.ok(String(url).startsWith(`https://api.telegram.org/bot${env.BOT_TOKEN}/`), 'only Telegram is called');
    calls.push({ method, params: JSON.parse(init.body) });
    return new Response(JSON.stringify(replies[method] || { ok: true, result: true }), { status: 200 });
  };
});

const message = (text, extra = {}) => ({ message: { message_id: 1, chat: { id: 42, type: 'private' }, from: { id: 42, first_name: 'Аня' }, text, ...extra } });
const only = (method) => { const found = calls.filter((c) => c.method === method); assert.equal(found.length, 1, `${method} called once`); return found[0].params; };

function signedInitData(fields, token = env.BOT_TOKEN) {
  const check = Object.keys(fields).sort().map((k) => `${k}=${fields[k]}`).join('\n');
  const secret = createHmac('sha256', 'WebAppData').update(token).digest();
  const hash = createHmac('sha256', secret).update(check).digest('hex');
  return new URLSearchParams({ ...fields, hash }).toString();
}
const now = () => Math.floor(Date.now() / 1000);
const validInitData = () => signedInitData({ auth_date: String(now()), query_id: 'AAE', user: JSON.stringify({ id: 42, first_name: 'Аня' }) });

test('/start greets by name and offers the app, support and help', async () => {
  await handleUpdate(env, message('/start'));
  const p = only('sendMessage');
  assert.equal(p.chat_id, 42);
  assert.match(p.text, /Привет, Аня/);
  assert.equal(p.parse_mode, 'HTML');
  assert.deepEqual(p.reply_markup.inline_keyboard[0][0].web_app, { url: env.WEBAPP_URL });
  assert.deepEqual(p.reply_markup.inline_keyboard[1].map((b) => b.callback_data), ['donate', 'help']);
});

test('names with markup are escaped', async () => {
  await handleUpdate(env, message('/start', { from: { id: 42, first_name: '<b>x</b>&' } }));
  assert.match(only('sendMessage').text, /&lt;b&gt;x&lt;\/b&gt;&amp;/);
});

test('/start donate and /donate show the configured amounts', async () => {
  for (const text of ['/start donate', '/donate', '/donate@kletka_bot']) {
    calls = [];
    await handleUpdate(env, message(text));
    assert.deepEqual(only('sendMessage').reply_markup.inline_keyboard[0].map((b) => b.callback_data), ['pay:50', 'pay:150', 'pay:500']);
  }
});

test('/help, /terms and /paysupport answer with text', async () => {
  await handleUpdate(env, message('/help'));
  assert.match(only('sendMessage').text, /Как пользоваться/);
  calls = [];
  await handleUpdate(env, message('/terms'));
  assert.match(only('sendMessage').text, /добровольная поддержка/);
  calls = [];
  await handleUpdate(env, message('/paysupport'));
  assert.match(only('sendMessage').text, /@owner/);
});

test('plain text and unknown commands point to the app', async () => {
  for (const text of ['реши x^2', '/unknown']) {
    calls = [];
    await handleUpdate(env, message(text));
    assert.ok(only('sendMessage').reply_markup.inline_keyboard[0][0].web_app);
  }
});

test('in groups the bot never sends a web_app button and ignores chatter', async () => {
  const group = { chat: { id: -100, type: 'supergroup' } };
  await handleUpdate(env, message('/start', group));
  assert.equal(only('sendMessage').reply_markup, undefined);
  calls = [];
  await handleUpdate(env, message('привет', group));
  await handleUpdate(env, message('/terms', group));
  assert.equal(calls.length, 0);
});

test('choosing an amount sends a Stars invoice', async () => {
  await handleUpdate(env, { callback_query: { id: 'cb1', data: 'pay:150', message: { chat: { id: 42 } } } });
  const p = only('sendInvoice');
  assert.equal(p.currency, 'XTR');
  assert.equal(p.provider_token, '');
  assert.equal(p.payload, 'donate:150');
  assert.deepEqual(p.prices.map((x) => x.amount), [150]);
  assert.equal(only('answerCallbackQuery').callback_query_id, 'cb1');
});

test('an amount that is not offered is refused', async () => {
  await handleUpdate(env, { callback_query: { id: 'cb2', data: 'pay:999999', message: { chat: { id: 42 } } } });
  assert.equal(calls.filter((c) => c.method === 'sendInvoice').length, 0);
  assert.equal(only('answerCallbackQuery').show_alert, true);
});

test('donate and help buttons work, every callback is answered', async () => {
  await handleUpdate(env, { callback_query: { id: 'a', data: 'donate', message: { chat: { id: 42 } } } });
  await handleUpdate(env, { callback_query: { id: 'b', data: 'help', message: { chat: { id: 42 } } } });
  await handleUpdate(env, { callback_query: { id: 'c', data: 'whatever' } });
  assert.equal(calls.filter((c) => c.method === 'sendMessage').length, 2);
  assert.equal(calls.filter((c) => c.method === 'answerCallbackQuery').length, 3);
});

test('pre-checkout is approved only for a matching Stars donation', async () => {
  const q = (over) => ({ pre_checkout_query: { id: 'pq', currency: 'XTR', total_amount: 150, invoice_payload: 'donate:150', ...over } });
  await handleUpdate(env, q());
  assert.equal(only('answerPreCheckoutQuery').ok, true);
  for (const over of [{ currency: 'USD' }, { total_amount: 1 }, { invoice_payload: 'other:150' }, { invoice_payload: '' }]) {
    calls = [];
    await handleUpdate(env, q(over));
    const p = only('answerPreCheckoutQuery');
    assert.equal(p.ok, false);
    assert.ok(p.error_message);
  }
});

test('a payment is thanked and reported to the owner with the refund command', async () => {
  await handleUpdate(env, message(undefined, { from: { id: 42, first_name: 'Аня', username: 'anya' },
    successful_payment: { currency: 'XTR', total_amount: 150, invoice_payload: 'donate:150', telegram_payment_charge_id: 'ch_1' } }));
  const sent = calls.filter((c) => c.method === 'sendMessage').map((c) => c.params);
  assert.equal(sent.length, 2);
  assert.equal(sent[0].chat_id, 42);
  assert.match(sent[0].text, /150 ⭐/);
  assert.equal(sent[1].chat_id, '777');
  assert.match(sent[1].text, /\/refund 42 ch_1/);
});

test('/refund works for the owner only', async () => {
  await handleUpdate(env, message('/refund 42 ch_1'));
  assert.equal(calls.filter((c) => c.method === 'refundStarPayment').length, 0);
  calls = [];
  await handleUpdate(env, message('/refund 42 ch_1', { from: { id: 777 }, chat: { id: 777, type: 'private' } }));
  assert.deepEqual(only('refundStarPayment'), { user_id: 42, telegram_payment_charge_id: 'ch_1' });
  assert.match(only('sendMessage').text, /возвращены/);
  calls = [];
  replies.refundStarPayment = { ok: false, description: 'CHARGE_ALREADY_REFUNDED' };
  await handleUpdate(env, message('/refund 42 ch_1', { from: { id: 777 }, chat: { id: 777, type: 'private' } }));
  assert.match(only('sendMessage').text, /CHARGE_ALREADY_REFUNDED/);
  calls = [];
  await handleUpdate(env, message('/refund abc', { from: { id: 777 }, chat: { id: 777, type: 'private' } }));
  assert.equal(calls.filter((c) => c.method === 'refundStarPayment').length, 0);
});

test('donation amounts fall back to defaults when the setting is broken', () => {
  assert.deepEqual(amounts({ DONATE_AMOUNTS: '10, 20,x,-5,0,99999' }), [10, 20]);
  assert.deepEqual(amounts({ DONATE_AMOUNTS: 'abc' }), [50, 150, 500]);
  assert.deepEqual(amounts({}), [50, 150, 500]);
});

test('initData signature is verified', async () => {
  assert.deepEqual(await verifyInitData(validInitData(), env.BOT_TOKEN), { id: 42, first_name: 'Аня' });
  assert.equal(await verifyInitData(validInitData(), 'other:token'), null);
  assert.equal(await verifyInitData(validInitData().replace('query_id=AAE', 'query_id=AAF'), env.BOT_TOKEN), null);
  assert.equal(await verifyInitData(signedInitData({ auth_date: String(now() - 2 * 86400), user: '{"id":42}' }), env.BOT_TOKEN), null);
  assert.equal(await verifyInitData('', env.BOT_TOKEN), null);
  assert.equal(await verifyInitData('user=%7B%7D&auth_date=1', env.BOT_TOKEN), null);
});

const post = (path, body, headers = {}) => worker.fetch(new Request('https://bot.example.workers.dev' + path, {
  method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) }), env);

test('webhook requires the secret header', async () => {
  assert.equal((await post('/webhook', message('/start'))).status, 403);
  assert.equal((await post('/webhook', message('/start'), { 'X-Telegram-Bot-Api-Secret-Token': 'wrong' })).status, 403);
  assert.equal(calls.length, 0);
  const res = await post('/webhook', message('/start'), { 'X-Telegram-Bot-Api-Secret-Token': env.WEBHOOK_SECRET });
  assert.equal(res.status, 200);
  only('sendMessage');
});

test('webhook answers 200 even when handling fails, so Telegram does not retry forever', async () => {
  globalThis.fetch = async () => { throw new Error('network down'); };
  const res = await post('/webhook', message('/start'), { 'X-Telegram-Bot-Api-Secret-Token': env.WEBHOOK_SECRET });
  assert.equal(res.status, 200);
});

test('/api/invoice creates a link only for a real app user', async () => {
  replies.createInvoiceLink = { ok: true, result: 'https://t.me/$invoice' };
  let res = await post('/api/invoice', { initData: validInitData(), amount: 150 });
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { link: 'https://t.me/$invoice' });
  assert.equal(res.headers.get('Access-Control-Allow-Origin'), 'https://example.github.io');
  assert.equal(only('createInvoiceLink').payload, 'donate:150');
  calls = [];
  assert.equal((await post('/api/invoice', { initData: 'user=%7B%7D&hash=00', amount: 150 })).status, 401);
  for (const amount of [0, -5, 1.5, 100000, 'abc']) assert.equal((await post('/api/invoice', { initData: validInitData(), amount })).status, 400);
  assert.equal(calls.length, 0);
  replies.createInvoiceLink = { ok: false, description: 'boom' };
  assert.equal((await post('/api/invoice', { initData: validInitData(), amount: 50 })).status, 502);
});

test('CORS preflight is answered', async () => {
  const res = await worker.fetch(new Request('https://bot.example.workers.dev/api/invoice', { method: 'OPTIONS' }), env);
  assert.equal(res.status, 204);
  assert.equal(res.headers.get('Access-Control-Allow-Origin'), 'https://example.github.io');
});

test('/setup is protected and configures webhook, commands, texts and menu button', async () => {
  const get = (q) => worker.fetch(new Request('https://bot.example.workers.dev/setup' + q), env);
  assert.equal((await get('')).status, 403);
  assert.equal((await get('?key=nope')).status, 403);
  assert.equal(calls.length, 0);
  const res = await get('?key=' + env.WEBHOOK_SECRET);
  assert.deepEqual(await res.json(), { setWebhook: 'ok', setMyCommands: 'ok', setMyDescription: 'ok', setMyShortDescription: 'ok', setChatMenuButton: 'ok' });
  const hook = only('setWebhook');
  assert.equal(hook.url, 'https://bot.example.workers.dev/webhook');
  assert.equal(hook.secret_token, env.WEBHOOK_SECRET);
  assert.ok(hook.allowed_updates.includes('pre_checkout_query'));
  assert.equal(only('setChatMenuButton').menu_button.web_app.url, env.WEBAPP_URL);
  assert.ok(only('setMyDescription').description.length <= 512);
  assert.ok(only('setMyShortDescription').short_description.length <= 120);
  assert.ok(only('setMyCommands').commands.every((c) => /^[a-z0-9_]{1,32}$/.test(c.command)));
});

test('an unconfigured bot and unknown paths fail clearly', async () => {
  assert.equal((await worker.fetch(new Request('https://bot.example.workers.dev/'), { ...env, BOT_TOKEN: '' })).status, 500);
  assert.equal((await worker.fetch(new Request('https://bot.example.workers.dev/nope'), env)).status, 404);
  assert.equal((await worker.fetch(new Request('https://bot.example.workers.dev/'), env)).status, 200);
});
