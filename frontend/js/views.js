/* Главная, курс, неделя, награды, профиль. Разметка и классы взяты из прототипа. */
const V = {};
const NAVOF = { story: 'mod', lesson: 'mod', res: 'mod', mat: 'mod', review: 'home', exam: 'rw' };

function N() {
  const nv = document.getElementById('nv');
  if (!S.user || ['boot', 'auth', 'welcome', 'pw'].includes(S.v)) { nv.innerHTML = ''; return; }
  const cur = NAVOF[S.v] || S.v;
  nv.innerHTML = `<b>Северный Контур<small>Академия безопасности</small></b>` +
    [['home', 'Главная'], ['mod', 'Курс'], ['rw', 'Награды'], ['prof', 'Профиль']]
      .map(([k, l]) => `<button class="${cur === k ? 'on' : ''}" onclick="go('${k}')">${l}</button>`).join('') +
    `<span class="sp"></span>` +
    (S.user.role === 'admin' ? `<button class="${S.v === 'adm' ? 'on' : ''}" onclick="go('adm')">Для администратора</button>` : '') +
    `<button class="out" onclick="logout()">Выйти</button>`;
}

function R() {
  N();
  const mn = document.getElementById('mn');
  mn.className = ['story', 'lesson', 'mat', 'review', 'exam'].includes(S.v) ? 'wide' : ['welcome', 'auth', 'pw'].includes(S.v) ? 'wc' : '';
  document.body.classList.toggle('au-on', S.v === 'auth'); if (window.fxSet) fxSet(S.v === 'auth');
  mn.innerHTML = (V[S.v] || V.home)();
  if (S.v === 'welcome' && S.ws === 0) TY();
}

async function refreshP() { S.P = await api('GET', '/progress'); }

async function go(v) {
  clearInterval(S.ti);
  S.v = v;
  if (v === 'mod') S.wk = null;
  try {
    if (['home', 'mod', 'rw', 'prof'].includes(v)) await refreshP();
    if (v === 'home') { const [d, t] = await Promise.all([api('GET', '/daily'), api('GET', '/team')]); S.daily = d; S.team = t; }
    if (v === 'adm') await loadAdmin();
    if (v === 'exam') await loadExam();
    if (v === 'review') await loadReview();
  } catch (e) { toast(e.message); if (['review', 'exam', 'adm'].includes(v)) S.v = 'home'; }
  R(); scrollTo(0, 0);
}

async function openMod(k) { S.wk = k; S.v = 'mod'; try { await refreshP(); } catch (e) { toast(e.message); } R(); scrollTo(0, 0); }
const lockMsg = k => toast(S.P.modules[k].need);

// ---------- главная ----------
V.welcome = WelcomeV; V.auth = AuthV; V.pw = PwV;
V.boot = () => '<div class="load">Загрузка…</div>';

V.home = () => {
  const P = S.P, u = S.user, name = esc(u.name.split(' ')[0]), h = new Date().getHours();
  const hello = h < 6 ? 'Доброй ночи' : h < 12 ? 'Доброе утро' : h < 18 ? 'Добрый день' : 'Добрый вечер';
  const cur = P.current, mod = cur ? MOD(cur) : null;
  const nextL = mod && mod.lessons.find(l => !(P.lessons[l.key] && P.lessons[l.key].done));
  const sk = P.streak.current, nb = P.next_badge;
  const sub = (sk ? `Серия: ${sk} ${plural(sk, 'день', 'дня', 'дней')} подряд.` : 'Сегодня хороший день, чтобы начать серию.') +
    (nb ? ` Осталось ${nb.left} ${plural(nb.left, 'урок', 'урока', 'уроков')} до бейджа «${esc(nb.badge.title)}».` : '');
  const T = S.course.modules.map(m => m.short);
  const pts = T.map((_, i) => [70 + i * 127, i % 2 ? 200 : 90]);
  const d = pts.slice(1).map((p, i) => { const a = pts[i]; return `C${a[0] + 64},${a[1]} ${p[0] - 64},${p[1]} ${p[0]},${p[1]}`; });
  const lockTxt = k => P.gating === 'sequential' ? 'после недели ' + (k - 1) : 'с уровня ' + MOD(k).unlock_level;
  const nd = pts.map((p, i) => {
    const z = MS(i + 1), s = z === 'done' ? 'd' : z === 'cur' ? 'c' : z === 'open' ? 'o' : 'l';
    return `<g style="cursor:pointer" onclick="openMod(${i + 1})"><circle cx="${p[0]}" cy="${p[1]}" r="${s === 'c' ? 30 : 24}" style="fill:${s === 'd' ? '#6FAE2E' : s === 'c' ? '#1B2A5C' : 'var(--card)'};stroke:${s === 'l' ? 'var(--ln)' : s === 'o' ? '#6FAE2E' : 'none'};stroke-width:3"/><text x="${p[0]}" y="${p[1] + 6}" text-anchor="middle" style="fill:${s === 'l' ? 'var(--mut)' : s === 'o' ? 'var(--ink)' : '#fff'};font-size:17px;font-weight:800">${s === 'd' ? '✓' : i + 1}</text><text x="${p[0]}" y="${p[1] + 56}" text-anchor="middle">${esc(T[i])}</text>${s === 'o' || s === 'l' ? `<text x="${p[0]}" y="${p[1] + 74}" text-anchor="middle" style="font-size:12px;font-weight:400;fill:${s === 'o' ? 'var(--acd)' : 'var(--mut)'}">${s === 'o' ? 'открыта' : lockTxt(i + 1)}</text>` : ''}</g>`;
  }).join('');
  const dq = S.daily, a = dq && dq.answered;
  const lv = P.level, r = RD()[lv - 1];
  const hero = `<div class="hh pop"><div style="padding-bottom:28px"><h1>${hello}, ${name}!</h1><p style="margin:10px 0 18px;font-size:18px">${sub}</p><div class="row">${cur ? `<button class="btn" onclick="openMod(${cur})">Продолжить неделю ${cur}</button><span class="sm" style="color:#C9D2F0">${nextL ? `${esc(nextL.kind)} · около ${nextL.minutes} мин` : ''}</span>` : `<button class="btn" onclick="go('exam')">${P.certificate ? 'Мой сертификат' : 'Итоговый экзамен'}</button><span class="sm" style="color:#C9D2F0">Все недели пройдены</span>`}</div></div>${img(2)}</div>`;
  const cards = `<div class="g g3" style="margin-top:16px"><div class="card"><h3>Серия: ${sk} ${plural(sk, 'день', 'дня', 'дней')}</h3><div class="dys">${P.streak.week.map(x => `<div class="dy ${x.active ? 'f' : ''} ${x.today ? 't' : ''}"><i></i>${x.d}</div>`).join('')}</div></div>
<div class="card" style="cursor:pointer" onclick="go('rw')"><h3>Уровень ${lv}: ${esc(r.title)}</h3><p class="sm" style="margin:6px 0 10px">${stars(1, 1)} ${P.stars}${lv < RD().length ? ` · ещё ${P.stars_to_next} до уровня ${lv + 1}` : ' · максимум'}</p>${bar(P.level_pct)}<p class="sm mut" style="margin-top:8px">${P.xp} очков опыта</p></div>
<div class="card"><h3>${nb ? 'Следующий бейдж' : 'Все бейджи получены'}</h3>${nb ? `<div class="badge" style="margin-top:10px"><i>${esc(nb.badge.code)}</i><span>${esc(nb.badge.title)}<br><span class="sm mut">осталось ${nb.left} ${plural(nb.left, 'урок', 'урока', 'уроков')}</span></span></div>` : `<p class="sm mut" style="margin-top:10px">Остался итоговый экзамен и сертификат.</p>`}</div></div>`;
  const path = `<div class="card" style="margin-top:16px"><h2>Ваш путь по курсу</h2><p class="sm mut" style="margin:4px 0 8px">Семь недель, у каждой своя история. Нажмите на текущую, чтобы продолжить.</p><div class="tr"><svg viewBox="0 -40 900 330" role="img" aria-label="Путь курса из семи недель"><path d="M${pts[0]} ${d.join(' ')}" fill="none" style="stroke:var(--ln);stroke-width:6;stroke-dasharray:1 13;stroke-linecap:round"/><path d="M${pts[0]} ${d.slice(0, Math.min((cur || 8) - 1, 6)).join(' ')}" fill="none" style="stroke:#6FAE2E;stroke-width:6;stroke-linecap:round"/>${nd}${(() => { const c = (cur || 1) - 1; return `<image href="${M(1)}" x="${pts[c][0] - 36}" y="${pts[c][1] - 106}" width="72" height="72"/>`; })()}</svg></div></div>`;
  const daily = dq ? `<div class="card"><h3>Вопрос дня · звезда и 20 очков</h3><p style="margin:8px 0 4px">${esc(dq.q)}</p>${dq.options.map((t, i) => `<button class="opt ${a ? (i === a.correct ? 'ok' : i === a.pick ? 'no' : '') : ''}" ${a ? 'disabled' : ''} onclick="dca(${i})">${esc(t)}</button>`).join('')}${a ? `<div class="say pop">${esc(a.text)}</div>` : ''}</div>` : '';
  const T2 = S.team && S.team.enabled ? `<div class="card"><h3>Командный зачёт недели</h3><p class="sm mut" style="margin:4px 0 6px">Считаются очки подразделений, а не отдельных людей.</p><table class="tb">${S.team.departments.map((x, i) => `<tr><td style="width:22px;font-weight:800">${i + 1}</td><td>${esc(x.name)}${x.id === S.team.my_dept ? ' <span class="tag">ваш отдел</span>' : ''}</td><td style="width:80px">${bar(x.points / Math.max(1, S.team.departments[0].points) * 100)}</td><td style="width:46px;text-align:right">${x.points}</td></tr>`).join('')}</table></div>` : '';
  const rv = P.review, due = rv.due;
  const review = `<div class="card"><h3>Повторение ошибок</h3><p class="sm mut" style="margin:6px 0 10px">${!rv.open ? 'Тренажёр откроется на уровне 2.' : due ? `Готово к повторению: ${due} ${plural(due, 'вопрос', 'вопроса', 'вопросов')}. Верный ответ даёт очки опыта.` : 'Пока повторять нечего. Вопросы, в которых вы ошиблись, вернутся через два дня.'}</p>${rv.open && due ? `<button class="btn" onclick="go('review')">Повторить</button>` : ''}</div>`;
  const memo = `<div class="card" style="display:flex;gap:14px;align-items:flex-end">${img(3, 76)}<div><h3>Памятка от ИБ-отдела</h3><p class="sm" style="margin-top:6px">Приходят письма «о доставке посылки». Сверяйте номер заказа в личном кабинете, а подозрительное письмо просто перешлите в ИБ.</p></div></div>`;
  return takeFlash() + hero + cards + path + `<div class="g g2" style="margin-top:16px;align-items:start">${daily}<div class="g">${T2}${review}${memo}</div></div>`;
};

async function dca(i) {
  try {
    const r = await api('POST', '/daily/answer', { pick: i });
    if (r.level_up) S.flash = r.level_up;
    const [d] = await Promise.all([api('GET', '/daily'), refreshP()]); S.daily = d;
  } catch (e) { toast(e.message); }
  R();
}

// ---------- курс ----------
const MC = k => {
  const m = MOD(k), z = MS(k), l = z === 'lock', pm = S.P.modules[k], mins = m.lessons.reduce((a, x) => a + x.minutes, 0);
  const lbl = { done: 'Пройдено', cur: 'Сейчас', open: 'Открыта', lock: S.P.gating === 'sequential' ? 'После недели ' + (k - 1) : 'С уровня ' + m.unlock_level }[z];
  return `<button class="card mc ${z}" onclick="openMod(${k})"><span class="row" style="justify-content:space-between;gap:8px"><span class="tag">Неделя ${k}</span><span class="tag" style="${z === 'cur' ? 'background:var(--ink);color:var(--bg)' : l ? 'background:var(--ln);color:var(--mut)' : ''}">${lbl}</span></span><span class="row" style="gap:12px;flex-wrap:nowrap;margin-top:12px"><span style="flex:1"><b style="font-size:18px;display:block">${esc(m.title)}</b><span class="sm mut">${esc(m.desc)}</span></span><img src="${M(m.mascot)}" alt="" class="${l ? 'lk' : ''}" width="76"></span><span class="sm mut" style="display:block;margin-top:10px">${m.lessons.length} урока · ${mins} мин · пройдено ${pm.lessons_done} из ${pm.lessons_total}</span></button>`;
};

V.mod = () => S.wk ? MV() : CV();

function CV() {
  const dn = S.P.badges.length, tot = S.course.modules.length, P = S.P;
  const exam = P.certificate ? 'Сертификат получен. Его можно открыть и распечатать.' : P.exam.open ? 'Экзамен открыт. Пройдите его и получите сертификат и последний образ Черепундельчика.' : P.gating === 'sequential' ? 'Откроется, когда будут пройдены все семь недель. Сертификат о прохождении курса и последний образ Черепундельчика.' : 'Откроется на уровне 8. Сертификат о прохождении курса и последний образ Черепундельчика.';
  return takeFlash() + `<div class="hero pop"><div><h1>${esc(S.course.title)}</h1><p class="mut" style="margin:10px 0 14px">${tot} недель в трёх разделах. В каждой сюжет, задания и тест. ${P.gating === 'sequential' ? 'Недели открываются по порядку.' : 'Новые недели открываются с уровнем.'}</p><b>Пройдено ${dn} из ${tot}</b>${bar(dn / tot * 100)}</div>${img(4)}</div>` +
    S.course.sections.map(s => `<h2 style="margin:30px 0 4px">${esc(s.title)}</h2><p class="mut" style="margin-bottom:14px">${esc(s.desc)}</p><div class="g g11">${s.modules.map(MC).join('')}</div>`).join('') +
    `<button class="card mc" style="margin-top:30px;display:flex;gap:16px;align-items:center" onclick="go('exam')"><img src="${M(8)}" alt="" class="${P.exam.open || P.certificate ? '' : 'lk'}" width="80"><span><h3>Итоговый экзамен</h3><span class="sm mut" style="display:block;margin-top:4px">${exam}</span></span></button>`;
}

function MV() {
  const k = S.wk, m = MOD(k), P = S.P, pm = P.modules[k], l = pm.state === 'lock', done = pm.state === 'done';
  const rows = m.lessons.map((x, i) => {
    const lp = P.lessons[x.key], dn = lp && lp.done, cls = !l ? (dn ? 'done' : 'cur') : 'lock';
    return `<div class="lr"><button class="wk ${cls}" onclick="${l ? `lockMsg(${k})` : `startLesson('${x.key}')`}"><span class="dot">${dn ? '✓' : i + 1}</span><span style="flex:1"><b>${esc(x.title)}</b><br><span class="sm mut">${x.minutes} мин${dn ? ` · пройдено, доверие ${lp.best_trust}%` : ''}</span></span><span class="tag">${esc(x.kind)}</span></button><button class="btn s" onclick="${l ? `lockMsg(${k})` : `readMat('${x.key}')`}">Материал</button></div>`;
  }).join('');
  return `<button class="btn s" style="padding:6px 14px;margin-bottom:16px" onclick="go('mod')">Все модули</button>${takeFlash()}<div class="hero pop"><div><span class="tag">Неделя ${k}</span><h1 style="margin-top:10px">${esc(m.title)}</h1><p class="mut" style="margin-top:10px">${esc(m.desc)}</p></div>${img(m.mascot)}</div>${l ? `<div class="say" style="margin-top:20px">${esc(pm.need)}. Звёзды дают за пройденные уроки и вопрос дня.</div>` : ''}<div class="g" style="margin-top:24px">${rows}</div>${done ? `<div class="card" style="margin-top:20px"><div class="badge"><i>${esc(m.badge.code)}</i><b>Бейдж недели: ${esc(m.badge.title)}</b></div></div>` : ''}${l ? '' : `<div class="card" style="margin-top:20px"><h3>Что запомнить за неделю</h3><ol class="rules">${m.rules.map(r => `<li>${esc(r)}</li>`).join('')}</ol></div>`}`;
}

// ---------- награды ----------
V.rw = () => {
  const P = S.P, l = P.level, R8 = RD(), th = TH();
  return takeFlash() + `<div class="hero pop"><div><h1>Награды и уровни</h1><p class="mut" style="margin:8px 0 16px">Звёзды открывают новые недели, образы Черепундельчика и сертификат в конце курса.</p><div class="card"><h3>Уровень ${l}: ${esc(R8[l - 1].title)}</h3><p class="sm" style="margin:6px 0 10px">${stars(1, 1)} ${P.stars}${l < R8.length ? ` · до уровня ${l + 1} осталось ${P.stars_to_next}` : ''}</p>${bar(P.level_pct)}</div></div>${img(6)}</div>
<div class="card" style="margin-top:16px"><h3>Как получить звёзды</h3><p class="sm" style="margin-top:8px">За урок: ${stars(1, 1)} за прохождение (доверие от 60%) и ещё ${stars(1, 1)} при доверии от 90%. Если вы прошли урок хуже, повторите его: недостающая звезда начислится.<br>Вопрос дня на главной: ${stars(1, 1)} за верный ответ.<br>Итоговый экзамен: ${stars(2, 2)} и сертификат.</p></div>
<h2 style="margin:26px 0 14px">Коллекция образов</h2><div class="g g3">${R8.map((r, i) => { const o = l >= i + 1; return `<div class="card" style="${i === l ? 'border:2px solid var(--ac)' : ''}"><div style="height:150px;display:grid;place-items:center"><img src="${M(r.mascot)}" alt="${o ? esc(r.reward) : 'Закрытая награда'}" class="${o ? '' : 'lk'}" style="max-height:150px;max-width:100%"></div><h3 style="margin-top:10px">${esc(r.reward)}</h3><p class="sm mut">Уровень ${i + 1}: ${esc(r.title)} · от ${th[i]} ${stars(1, 1)}</p><p class="sm" style="margin-top:6px">${o ? 'Открыто' : 'Откроется'}: ${esc(r.unlocks)}</p></div>`; }).join('')}</div>`;
};

// ---------- профиль ----------
const ic = (p, bg, f) => `<span class="ic" style="background:${bg}"><svg width="22" height="22" viewBox="0 0 24 24"><path d="${p}" style="fill:${f}"/></svg></span>`;

V.prof = () => {
  const P = S.P, u = S.user, l = P.level, n = l < RD().length ? P.stars_to_next : 0, r = RD()[l - 1], sk = P.streak;
  const where = u.org ? `${u.dept ? esc(u.dept.name) + ' · ' : ''}${esc(u.org.name)}` : 'Самостоятельное обучение';
  const T = [
    [ic('M12 4l7 8h-4v8H9v-8H5z', 'var(--acl)', 'var(--acd)'), l, 'уровень', esc(r.title)],
    [ic('M12 2l3 6.5 7 .8-5.2 4.8 1.5 7-6.3-3.6L5.7 21l1.5-7L2 9.3l7-.8z', 'rgba(242,177,52,.25)', 'var(--st)'), P.stars, 'звёзд', l < RD().length ? `ещё ${n} до уровня ${l + 1}` : 'максимум'],
    [ic('M13 2L4 14h7l-1 8 9-12h-7z', 'var(--acl)', 'var(--acd)'), P.xp, 'очков опыта', 'за всё обучение'],
    [ic('M12 2c1 4 5 6 5 11a5 5 0 0 1-10 0c0-2 1-3 2-4 0 2 1 3 2 3 0-4-1-6 1-10z', 'var(--erl)', 'var(--er)'), sk.current, plural(sk.current, 'день', 'дня', 'дней') + ' подряд', `рекорд: ${sk.best} ${plural(sk.best, 'день', 'дня', 'дней')}`]];
  const mods = S.course.modules, bd = P.badges.length;
  const gSel = `<label class="fld"><span>Пол (для иллюстраций в сюжетах)</span><select class="in" onchange="saveGender(this.value)"><option value="">Не указан</option><option value="f" ${u.gender === 'f' ? 'selected' : ''}>Женский</option><option value="m" ${u.gender === 'm' ? 'selected' : ''}>Мужской</option></select></label>`;
  const depSel = u.org && u.departments.length ? `<label class="fld"><span>Подразделение</span><select class="in" onchange="saveDept(this.value)"><option value="">Не выбрано</option>${u.departments.map(d => `<option value="${d.id}" ${u.dept && u.dept.id === d.id ? 'selected' : ''}>${esc(d.name)}</option>`).join('')}</select></label>` : '';
  return `<div class="hh pop" style="grid-template-columns:1fr 150px"><div style="padding-bottom:24px"><h1>${esc(u.name)}</h1><p style="margin:6px 0 16px">${where}</p><div class="row" style="gap:10px"><span class="tag" style="background:var(--ac);color:#10230A">Уровень ${l}: ${esc(r.title)}</span><span class="sm" style="color:#C9D2F0">${esc(r.reward)}</span></div><div class="sm" style="margin:14px 0 6px;color:#C9D2F0">${l < RD().length ? `До уровня ${l + 1} осталось звёзд: ${n}` : 'Максимальный уровень'}</div><div class="bar" style="background:rgba(255,255,255,.2)"><i style="width:${P.level_pct}%"></i></div></div>${img(r.mascot)}</div>
<div class="g g4" style="margin-top:16px">${T.map(t => `<div class="card tile">${t[0]}<div><div class="num">${t[1]}</div><b>${t[2]}</b><div class="sm mut">${t[3]}</div></div></div>`).join('')}</div>
${P.certificate ? `<div class="card" style="margin-top:16px;display:flex;gap:16px;align-items:center;flex-wrap:wrap"><img src="${M(8)}" width="70" alt=""><div style="flex:1"><h3>Сертификат о прохождении курса</h3><p class="sm mut">Номер ${esc(P.certificate.code)} · ${fmtDate(P.certificate.issued_at)}</p></div><a class="btn" style="text-decoration:none" href="/certificate/${esc(P.certificate.code)}" target="_blank" rel="noopener">Открыть</a></div>` : ''}
<div class="g g2" style="margin-top:16px;align-items:start"><div class="g"><div class="card"><h3>Прогресс по курсу · ${bd} из ${mods.length}</h3><div class="g" style="gap:8px;margin-top:12px">${mods.map(m => { const z = MS(m.id); return `<button class="wk ${z === 'done' ? 'done' : z === 'cur' ? 'cur' : z === 'lock' ? 'lock' : ''}" style="padding:10px 14px" onclick="openMod(${m.id})"><span class="dot">${z === 'done' ? '✓' : m.id}</span><b style="flex:1">${esc(m.title)}</b><span class="tag">${{ done: 'Пройдено', cur: 'Сейчас', open: 'Открыта', lock: 'Закрыта' }[z]}</span></button>`; }).join('')}</div></div>
<div class="card"><h3>Бейджи · ${bd} из ${mods.length}</h3><div class="g" style="grid-template-columns:1fr 1fr;gap:14px;margin-top:14px">${mods.map(m => { const e = P.badges.includes(m.id); return `<div class="badge ${e ? '' : 'off'}"><i>${esc(m.badge.code)}</i><span>${esc(m.badge.title)}<br><span class="sm mut">${e ? 'Получен' : 'Неделя ' + m.id}</span></span></div>`; }).join('')}</div></div></div>
<div class="g"><div class="card"><h3>Серия: ${sk.current} ${plural(sk.current, 'день', 'дня', 'дней')}</h3><div class="dys">${sk.week.map(x => `<div class="dy ${x.active ? 'f' : ''} ${x.today ? 't' : ''}"><i></i>${x.d}</div>`).join('')}</div><p class="sm mut" style="margin-top:10px">Загляните завтра, чтобы серия продолжилась.</p></div>
<div class="card"><h3>Точность ответов по темам</h3><div class="g" style="gap:12px;margin-top:12px">${P.accuracy.map(a => `<div><div class="row" style="justify-content:space-between;gap:8px"><span>${esc(a.topic)}</span><span class="sm mut">${a.pct == null ? 'пока нет данных' : a.pct + '%'}</span></div>${bar(a.pct || 0)}</div>`).join('')}</div><p class="sm mut" style="margin-top:12px">Эти данные видите только вы.</p></div>
<div class="card"><h3>Коллекция образов</h3><div class="row" style="gap:6px;margin:12px 0">${RD().map((x, i) => `<img src="${M(x.mascot)}" alt="" class="${l >= i + 1 ? '' : 'lk'}" style="height:54px;width:auto">`).join('')}</div><button class="btn s" onclick="go('rw')">Все награды</button></div></div></div>
<div class="card" style="margin-top:16px"><h3>Аккаунт</h3><p class="sm mut" style="margin:4px 0 0">${esc(u.email)}</p><div class="grid-in"><div><label class="fld"><span>Имя и фамилия</span><input id="nm" class="in" value="${esc(u.name)}" maxlength="60"></label><p class="sm mut" style="margin-top:6px">Первое слово — ваше имя, так к вам обращается Черепундель. Например: Анна Попова.</p>${gSel}${depSel}<button class="btn s" style="margin-top:12px" onclick="saveName()">Сохранить</button></div><div><label class="fld"><span>Текущий пароль</span><input class="in" type="password" autocomplete="current-password" oninput="S.pw.cur=this.value"></label><label class="fld"><span>Новый пароль</span><input class="in" type="password" autocomplete="new-password" oninput="S.pw.nw=this.value"></label><button class="btn s" style="margin-top:12px" onclick="savePw(true)">Сменить пароль</button></div></div><button class="btn s" style="margin-top:18px" onclick="logout()">Выйти из аккаунта</button></div>`;
};

async function saveName() {
  try { const r = await api('PATCH', '/me', { name: document.getElementById('nm').value }); S.user = r.user; toast('Сохранено'); R(); } catch (e) { toast(e.message); }
}
async function saveGender(v) {
  try { const r = await api('PATCH', '/me', { gender: v || null }); S.user = r.user; toast('Сохранено'); R(); } catch (e) { toast(e.message); }
}

async function saveDept(v) {
  try { const r = await api('PATCH', '/me', { dept_id: v || null }); S.user = r.user; toast('Подразделение обновлено'); R(); } catch (e) { toast(e.message); }
}
