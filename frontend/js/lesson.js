/* Прохождение урока, чтение материала, повторение ошибок, итоговый экзамен.
   Правильные ответы приходят только с сервера и только после ответа. */

// ---------- движок вопроса (один и тот же для урока, повторения и экзамена) ----------
const QE = { q: null, sel: [], res: null, rm: [], busy: false, submit: null, hint: null, after: null };
function qSet(q, o = {}) { Object.assign(QE, { q, sel: [], res: null, rm: [], busy: false, submit: null, hint: null, after: null }, o); }

function qOptions() {
  const q = QE.q, r = QE.res, known = r && r.correct;
  if (q.type === 'sort') return q.options.map((t, i) => `<div class="opt ${known ? (QE.sel[i] === r.correct[i] ? 'ok' : 'no') : ''}" style="cursor:default"><div>${esc(t)}</div><div class="row" style="gap:8px;margin-top:8px">${['Нельзя', 'Можно'].map((l, v) => `<button class="btn ${QE.sel[i] === v ? '' : 's'}" style="padding:6px 14px" ${r ? 'disabled' : ''} onclick="qsr(${i},${v})">${l}</button>`).join('')}</div></div>`).join('');
  return q.options.map((t, i) => QE.rm.includes(i) ? '' : `<button class="opt ${known ? (r.correct.includes(i) ? 'ok' : QE.sel.includes(i) ? 'no' : '') : (QE.sel.includes(i) ? 'ok' : '')}" ${r ? 'disabled' : ''} onclick="qpk(${i})">${esc(t)}</button>`).join('');
}
function qCtl() {
  if (QE.res) return '';
  const q = QE.q, all = q.type === 'sort' ? q.options.every((_, i) => QE.sel[i] !== undefined) : QE.sel.length > 0;
  return `<div class="row" style="margin-top:16px">${q.type === 'multi' || q.type === 'sort' ? `<button class="btn" ${all && !QE.busy ? '' : 'disabled'} onclick="qchk()">Проверить</button>` : ''}${QE.hint && (q.type === 'one' || q.type === 'multi') && S.hints > 0 ? `<button class="btn s" onclick="qhint()">Подсказка</button>` : ''}</div>`;
}
function qpk(i) {
  if (QE.res || QE.busy) return;
  if (QE.q.type === 'multi') { QE.sel = QE.sel.includes(i) ? QE.sel.filter(x => x !== i) : [...QE.sel, i]; R(); }
  else { QE.sel = [i]; qchk(); }
}
function qsr(i, v) { if (QE.res || QE.busy) return; QE.sel[i] = v; R(); }
async function qchk() {
  if (QE.busy || QE.res) return;
  const q = QE.q, sel = q.type === 'sort' ? Array.from({ length: q.options.length }, (_, i) => QE.sel[i]) : QE.sel.slice();
  QE.busy = true;
  try { QE.res = await QE.submit(sel); } catch (e) { QE.busy = false; toast(e.message); R(); return; }
  QE.busy = false; R();
  if (QE.after) QE.after();
}
async function qhint() {
  try { const r = await QE.hint(); QE.rm.push(r.remove); S.hints = r.hints; R(); } catch (e) { toast(e.message); }
}

// ---------- материал ----------
const MT = m => [['Что это', m.what], ['Зачем это нужно', m.why]].map(([h, t]) => `<h2 style="margin:24px 0 8px;font-size:26px">${h}</h2><p>${esc(t)}</p>`).join('') +
  `<h2 style="margin:24px 0 8px;font-size:26px">Как это работает</h2><ol style="padding-left:26px;margin:0">${m.steps.map(s => `<li style="margin-bottom:8px">${esc(s)}</li>`).join('')}</ol><div class="say" style="padding:18px 22px;margin-top:22px"><b>Пример из жизни.</b> ${esc(m.example)}</div>`;
const MC2 = c => c.cards ? `<h2 style="margin:30px 0 16px;font-size:28px">Главное</h2><div class="g g3">${c.cards.map(x => `<div class="card" style="padding:26px"><b style="font-size:20px">${esc(x[0])}</b><p style="margin-top:10px;font-size:17px">${esc(x[1])}</p></div>`).join('')}</div>` : '';

async function readMat(key) {
  try { S.mat = await api('GET', '/lessons/' + key); S.v = 'mat'; R(); scrollTo(0, 0); } catch (e) { toast(e.message); }
}
V.mat = () => {
  const l = S.mat, chs = l.chapters || [{ title: l.title, material: l.material }];
  return `<button class="btn s" style="padding:6px 14px" onclick="openMod(${l.module})">К урокам недели</button><h1 style="margin:22px 0 6px;font-size:40px">Материал: ${esc(l.title)}</h1><p class="mut">${esc(l.kind)} · ${l.minutes} мин</p>` +
    chs.map(c => `<div class="row pop" style="align-items:flex-start;gap:40px;margin-top:10px"><div style="flex:1;min-width:280px;max-width:820px;font-size:20px;line-height:1.6">${chs.length > 1 ? `<h1 style="margin:26px 0 0;font-size:30px">${esc(c.title)}</h1>` : ''}${MT(c.material)}</div>${chs.length === 1 ? `<div class="bob" style="width:min(280px,100%);flex:none;position:sticky;top:24px">${img(c.mascot || MOD(l.module).mascot, 280)}</div>` : ''}</div>${MC2(c)}`).join('') +
    `<button class="btn" style="margin-top:28px;font-size:19px;padding:16px 30px" onclick="startLesson('${l.key}')">Пройти урок</button>`;
};

// ---------- урок ----------
async function startLesson(key) {
  try {
    const les = await api('GET', '/lessons/' + key), run = await api('POST', `/lessons/${key}/start`);
    Object.assign(S, { les, run: run.run, hints: run.hints, ch: 0, qi: -1, hp: 100, combo: 0, gain: 0, sp: null, hfound: [], hok: {}, hn: 0, hlast: null, result: null });
    S.v = les.type === 'hotspot' ? 'lesson' : 'story'; R(); scrollTo(0, 0);
  } catch (e) { toast(e.message); }
}

function setQ() {
  const key = S.les.key, ch = S.ch, qi = S.qi;
  qSet(S.les.chapters[ch].questions[qi], {
    submit: async sel => { const r = await api('POST', `/runs/${S.run}/answer`, { ch, qi, sel }); S.hp = r.hp; S.combo = r.combo; S.gain = r.gain; return r; },
    hint: () => api('POST', `/runs/${S.run}/hint`, { ch, qi }),
  });
}
function toQuestions() { S.qi = 0; setQ(); R(); scrollTo(0, 0); }
function afterMat() { const c = S.les.chapters[S.ch]; if (c.story) { S.sp = null; S.qi = -3; R(); } else toQuestions(); scrollTo(0, 0); }

async function nx() {
  const les = S.les, c = les.chapters[S.ch];
  if (S.qi < c.questions.length - 1) { S.qi++; setQ(); R(); return; }
  if (S.ch < les.chapters.length - 1) { S.ch++; S.qi = -1; R(); scrollTo(0, 0); return; }
  await finishRun();
}
async function finishRun() {
  try {
    const r = await api('POST', `/runs/${S.run}/finish`);
    S.result = r; S.P = r.progress; S.v = 'res'; R(); scrollTo(0, 0);
  } catch (e) { toast(e.message); }
}

const MAT = (c, hd) => `${hd}<h1 style="margin:26px 0 18px;font-size:40px">Материал: ${esc(c.title)}</h1><div class="row pop" style="align-items:flex-start;gap:40px"><div style="flex:1;min-width:280px;max-width:820px;font-size:20px;line-height:1.6">${MT(c.material)}</div><div class="bob" style="width:min(280px,100%);flex:none;position:sticky;top:24px">${img(c.mascot, 280)}</div></div>${MC2(c)}<button class="btn" style="margin-top:28px;font-size:19px;padding:16px 30px" onclick="afterMat()">${c.story ? 'К истории' : 'К заданиям'}</button>`;

const SC = c => c.scene ? `<img class="scene pop" src="${c.scene[S.user.gender === 'f' ? 'f' : 'm']}" alt="Иллюстрация к сюжету">` : '';

const STY = (c, hd) => {
  const y = c.story, p = S.sp;
  return `${hd}<div class="hero pop" style="margin-top:22px"><div><h2>История: что бы вы сделали?</h2><p style="margin:14px 0;font-size:22px;line-height:1.55">${esc(y.text)}</p></div>${img(c.mascot)}</div>${SC(c)}<div class="og">${y.options.map((v, i) => `<button class="opt ${p == null ? '' : i === y.best ? 'ok' : i === p ? 'no' : ''}" ${p == null ? '' : 'disabled'} onclick="S.sp=${i};R()">${esc(v.t)}</button>`).join('')}</div>${p == null ? '' : `<div class="card pop" style="margin-top:16px"><b>${p === y.best ? 'Хороший выбор' : 'Посмотрим, что получилось'}</b><p class="sm" style="margin-top:6px">${esc(y.options[p].r)}</p>${p === y.best ? '' : `<p class="sm" style="margin-top:6px">Лучше было так: ${esc(y.options[y.best].r)}</p>`}</div><button class="btn" style="margin-top:16px" onclick="toQuestions()">К заданиям</button>`}`;
};

V.story = () => {
  const les = S.les, c = les.chapters[S.ch], n = les.chapters.length;
  const hd = `<div class="row" style="justify-content:space-between"><b>${n > 1 ? `Глава ${S.ch + 1} из ${n}` : 'Урок'}</b><span class="sm mut">Подсказки: ${S.hints} · Верных подряд: ${S.combo}</span></div><div class="sm" style="margin:8px 0 4px">Доверие отдела: ${S.hp}%</div>${bar(S.hp)}`;
  if (S.qi === -2) return MAT(c, hd);
  if (S.qi === -3) return STY(c, hd);
  if (S.qi < 0) return `${hd}<div class="hero pop" style="margin-top:24px"><div><h1>${esc(c.title)}</h1><p style="margin:12px 0 18px;font-size:18px">${esc(c.intro)}</p></div>${img(c.mascot)}</div>${SC(c)}${c.mail ? `<div class="mail" style="margin-top:16px">${c.mail}</div>` : ''}<button class="btn" style="margin-top:22px" onclick="S.qi=-2;R();scrollTo(0,0)">Читать материал</button>`;
  const q = c.questions[S.qi], r = QE.res;
  return `${hd}<p class="mut" style="margin-top:20px">${esc(c.title)} · вопрос ${S.qi + 1} из ${c.questions.length}${q.type === 'multi' ? ' · несколько ответов' : ''}</p>${c.mail ? `<div class="mail" style="margin-top:12px">${c.mail}</div>` : ''}<div style="margin-top:12px"><h2>${esc(q.q)}</h2><div class="og">${qOptions()}</div>${qCtl()}</div><div style="margin-top:20px">${r ? `<div class="card pop fb">${img(r.ok ? 6 : 4, 96)}<div><b style="font-size:20px">${r.ok ? 'Верно' : 'Не совсем, и это полезно знать'}</b><p style="margin-top:6px;font-size:17px">${esc(r.text)}</p></div></div><button class="btn" style="margin-top:14px" onclick="nx()">Дальше</button>` : `<div class="say">Выбирайте не быстро, а внимательно. Серия из трёх верных ответов подряд даёт бонусные очки.</div>`}</div>`;
};

// ---------- «Найди ошибку в письме» ----------
async function hit(id) {
  if (S.hfound.includes(id)) return;
  try {
    const r = await api('POST', `/runs/${S.run}/hit`, { id });
    S.hok[id] = r.ok; S.hfound.push(id); S.hn = r.found; S.hlast = { ...r, id }; S.hp = r.hp; R();
  } catch (e) { toast(e.message); }
}
V.lesson = () => {
  const l = S.les, h = l.hotspot, it = id => h.items.find(x => x.id === id), need = h.need;
  const b = id => `<button class="hot ${S.hfound.includes(id) ? (S.hok[id] ? 'ok' : 'no') : ''}" onclick="hit('${id}')">${it(id).text}</button>`;
  const last = S.hlast;
  return `<h2>${esc(l.title)}</h2><details open class="card" style="margin:12px 0"><summary><b>Материал урока</b></summary>${MT(l.material)}</details><p class="mut" style="margin:6px 0 16px">Нажимайте на то, что кажется подозрительным. Нужно найти ${need} признака.</p>
<div class="g"><div class="mail pop"><div class="h"><div class="sm" style="color:#666">От: ${b('a')}<br>Тема: Счёт № 4471</div></div><p>${b('d')}</p><p style="margin:10px 0">${b('b')}</p><p>Счёт по ссылке: ${b('c')}</p><p style="margin-top:14px">${b('e')}</p></div>
<div><div style="display:flex;gap:12px;align-items:flex-end">${img(5, 90)}<div style="flex:1"><b>Найдено ${S.hn} из ${need}</b>${bar(S.hn / need * 100)}</div></div>
<div class="say" style="${last && !last.ok ? 'background:var(--erl)' : ''}" aria-live="polite">${last ? esc(last.msg) : esc(h.hint)}</div>
${S.hn >= need ? `<button class="btn" style="margin-top:16px" onclick="finishRun()">Завершить урок</button>` : ''}</div></div>`;
};
// ---------- результат ----------
V.res = () => {
  const r = S.result;
  return `<div class="hero pop"><div><h1>${r.passed ? 'Урок пройден' : 'Почти получилось'}</h1><p class="mut" style="margin:8px 0 18px">Доверие отдела: ${r.hp}%. Верных ответов: ${r.sc} из ${r.total}. +${r.xp} очков опыта.</p><div class="row" style="margin:-6px 0 16px;gap:10px"><span aria-hidden="true">${stars(r.stars_earned, 2)}</span><span class="sm mut">${r.stars_earned ? 'Звёзд за урок: ' + r.stars_earned : r.passed ? 'Новых звёзд нет: вы уже получили их раньше' : 'Звёзд нет'}</span></div>${r.level_up ? RWC(r.level_up) : ''}${r.passed ? (r.badge ? `<div class="badge"><i>${esc(r.badge.code)}</i><b>Неделя пройдена! Бейдж: ${esc(r.badge.title)}</b></div>` : '<p>Отлично! Следующий урок недели ждёт вас.</p>') : '<p>Нужно набрать хотя бы 60% доверия и ответить верно не меньше чем на половину вопросов. Попробуйте ещё раз: теперь вы знаете, на что смотреть.</p>'}<div class="card" style="margin:20px 0"><h3>Что запомнить</h3><ol class="rules">${r.rules.map(x => `<li>${esc(x)}</li>`).join('')}</ol></div><button class="btn" onclick="${r.passed ? `openMod(${r.module})` : `startLesson('${S.les.key}')`}">${r.passed ? 'К урокам недели' : 'Пройти ещё раз'}</button></div>${img(r.passed ? 6 : 4)}</div>`;
};

// ---------- повторение ошибок ----------
async function loadReview() { const d = await api('GET', '/review'); S.rv = { due: d.due, qs: d.questions, i: 0, ok: 0, xp: 0, done: false }; rvSet(); }
function rvSet() {
  const x = S.rv.qs[S.rv.i]; if (!x) return;
  qSet(x, { submit: async sel => { const r = await api('POST', '/review/answer', { qid: x.qid, sel }); if (r.ok) { S.rv.ok++; S.rv.xp += r.xp; } return r; } });
}
async function rvNext() {
  S.rv.i++;
  if (S.rv.i >= S.rv.qs.length) { S.rv.done = true; try { await refreshP(); } catch (e) { /* ок */ } } else rvSet();
  R(); scrollTo(0, 0);
}
V.review = () => {
  const rv = S.rv, r = QE.res;
  if (!rv.qs.length) return `<div class="hero pop"><div><h1>Повторять пока нечего</h1><p class="mut" style="margin:10px 0 18px">Вопросы, в которых вы ошиблись, вернутся через два дня. А пока можно пройти новый урок.</p><button class="btn" onclick="go('home')">На главную</button></div>${img(6)}</div>`;
  if (rv.done) return `<div class="hero pop"><div><h1>Повторение завершено</h1><p class="mut" style="margin:10px 0 18px">Верных ответов: ${rv.ok} из ${rv.qs.length}. +${rv.xp} очков опыта.${rv.ok < rv.qs.length ? ' Вопросы с ошибками вернутся ещё раз через два дня.' : ''}</p><button class="btn" onclick="go('home')">На главную</button></div>${img(rv.ok === rv.qs.length ? 6 : 5)}</div>`;
  const q = QE.q;
  return `<p class="mut">Повторение ошибок · вопрос ${rv.i + 1} из ${rv.qs.length}${q.type === 'multi' ? ' · несколько ответов' : ''}</p>${bar((rv.i + (r ? 1 : 0)) / rv.qs.length * 100)}<span class="tag" style="margin-top:14px;display:inline-block">${esc(q.topic)}</span><div style="margin-top:12px"><h2>${esc(q.q)}</h2><div class="og">${qOptions()}</div>${qCtl()}</div><div style="margin-top:20px">${r ? `<div class="card pop fb">${img(r.ok ? 6 : 4, 96)}<div><b style="font-size:20px">${r.ok ? 'Верно' : 'Пока не получилось'}</b><p style="margin-top:6px;font-size:17px">${esc(r.text)}</p></div></div><button class="btn" style="margin-top:14px" onclick="rvNext()">${rv.i + 1 < rv.qs.length ? 'Дальше' : 'Закончить'}</button>` : `<div class="say">Вспомните, в чём была ловушка в прошлый раз.</div>`}</div>`;
};

// ---------- итоговый экзамен ----------
async function loadExam() { const [info] = await Promise.all([api('GET', '/exam'), refreshP()]); S.ex = { st: 'info', info }; }
async function exStart() {
  try { const r = await api('POST', '/exam/start'); S.ex = { ...S.ex, st: 'run', run: r.run, qs: r.questions, i: 0 }; exSet(); R(); scrollTo(0, 0); } catch (e) { toast(e.message); }
}
function exSet() {
  const i = S.ex.i;
  qSet(S.ex.qs[i], { submit: sel => api('POST', `/runs/${S.ex.run}/answer`, { qi: i, sel }), after: () => setTimeout(exNext, 350) });
}
async function exNext() {
  S.ex.i++;
  if (S.ex.i < S.ex.qs.length) { exSet(); R(); scrollTo(0, 0); return; }
  try { const r = await api('POST', `/runs/${S.ex.run}/finish`); S.ex.result = r; S.ex.st = 'result'; await refreshP(); } catch (e) { toast(e.message); S.ex.i--; exSet(); }
  R(); scrollTo(0, 0);
}
V.exam = () => {
  const ex = S.ex, P = S.P;
  if (ex.st === 'run') {
    const q = QE.q;
    return `<p class="mut">Итоговый экзамен · вопрос ${ex.i + 1} из ${ex.qs.length}${q.type === 'multi' ? ' · несколько ответов' : ''}</p>${bar(ex.i / ex.qs.length * 100)}<div style="margin-top:22px"><h2>${esc(q.q)}</h2><div class="og">${qOptions()}</div>${qCtl()}</div><div class="say" style="margin-top:20px">На экзамене подсказок и объяснений нет: разбор вы увидите в конце.</div>`;
  }
  if (ex.st === 'result') {
    const r = ex.result;
    return `<div class="hero pop"><div><h1>${r.passed ? 'Экзамен сдан!' : 'Пока не хватило'}</h1><p class="mut" style="margin:10px 0 18px">Верных ответов: ${r.score} из ${r.total}. Нужно не меньше ${Math.round(ex.info.pass_share * 100)}%.</p>${r.passed ? `<a class="btn" style="text-decoration:none;display:inline-block" href="/certificate/${esc(r.certificate)}" target="_blank" rel="noopener">Открыть сертификат</a>` : `<button class="btn" onclick="exStart()">Попробовать снова</button>`}</div>${img(r.passed ? 6 : 4)}</div>${r.review.length ? `<h2 style="margin:26px 0 12px">Разбор ошибок</h2><div class="g">${r.review.map(x => `<div class="card"><span class="tag">${esc(x.topic)}</span><p style="margin:10px 0 6px"><b>${esc(x.q)}</b></p><p class="sm">Верно: ${x.type === 'sort' ? x.options.map((o, i) => `${esc(o)} (${x.correct[i] ? 'можно' : 'нельзя'})`).join('; ') : x.correct.map(i => esc(x.options[i])).join('; ')}</p><p class="sm mut" style="margin-top:6px">${esc(x.text)}</p></div>`).join('')}</div>` : ''}<button class="btn s" style="margin-top:20px" onclick="go('home')">На главную</button>`;
  }
  const i = ex.info, open = i.open;
  return `<div class="hero pop"><div><h1>Итоговый экзамен</h1><p class="mut" style="margin:10px 0 14px">${i.total} вопросов по всем неделям, по два из каждой. Нужно ответить верно не меньше чем на ${Math.round(i.pass_share * 100)}%. Подсказок нет, а разбор ошибок появится в конце. За успех: ${stars(2, 2)}, сертификат и образ «Аналитик».</p>${P.certificate ? `<p style="margin-bottom:14px"><b>Вы уже сдали экзамен.</b> Номер сертификата: ${esc(P.certificate.code)}</p><a class="btn" style="text-decoration:none;display:inline-block" href="/certificate/${esc(P.certificate.code)}" target="_blank" rel="noopener">Открыть сертификат</a>` : open ? `<button class="btn pls" onclick="exStart()">Начать экзамен</button>` : `<div class="say">${i.gating === 'sequential' ? 'Экзамен откроется, когда будут пройдены все семь недель.' : `Экзамен откроется на уровне 8. Сейчас уровень ${P.level}, не хватает звёзд: ${P.stars_to_next}.`}</div>`}</div>${img(8)}</div>${i.last && !P.certificate ? `<p class="sm mut" style="margin-top:16px">Последняя попытка: ${i.last.score} из ${i.last.total}.</p>` : ''}`;
};
