/* Вход, регистрация, обязательная смена пароля и знакомство с Черепунделем. */
S.f = { mode: 'join', email: '', password: '', name: '', last: '', gender: '', code: '', org_name: '', departments: '', dept_id: '' };
S.authTab = 'intro'; S.err = null; S.org = null; S.busy = false;

const WT = 'Привет! Я Черепундель, ваш наставник. Ошибаться здесь нормально: мы для этого и тренируемся. Никто не увидит ваши промахи, зато вы заметите настоящие ловушки раньше, чем в них попадёте.';
const WM = { a: 'Верно! Домен .co вместо .ru: одна буква, и отправитель уже чужой.', b: 'Да! Спешка и угрозы нужны, чтобы вы не успели подумать.', c: 'Обращение по имени ничего не доказывает: имена легко узнать. Ищите дальше.' };

const fld = (label, key, type = 'text', extra = '') =>
  `<label class="fld"><span>${label}</span><input class="in" type="${type}" value="${esc(S.f[key])}" ${extra} oninput="S.f.${key}=this.value" onkeydown="event.key==='Enter'&&submitAuth()"></label>`;

function AuthV() {
  const tab = S.authTab, f = S.f;
  if (tab === 'intro') return `<div class="au"><div class="glass intro pop"><div class="bob" style="width:128px;margin:0 auto 6px">${img(1)}</div><h1>Северный Контур</h1><p class="mut" style="font-weight:600;margin-top:6px">Академия безопасности</p><p style="margin:18px 0 26px;font-size:17px">Привет, я Черепундель. Вместе мы за несколько минут в день учимся замечать фишинг, слабые пароли и опасные вложения. Ошибаться здесь можно: никто не увидит ваши промахи.</p><div class="g" style="gap:10px"><button class="btn pls" onclick="authTab('login')">Войти</button><button class="btn s" onclick="authTab('register')">Зарегистрироваться</button></div></div></div>`;
  const login = tab === 'login';
  let form;
  if (login) {
    form = `${fld('Почта', 'email', 'email', 'autocomplete="username"')}${fld('Пароль', 'password', 'password', 'autocomplete="current-password"')}`;
  } else {
    const modes = [['join', 'Я сотрудник'], ['individual', 'Учусь сам'], ['create_org', 'Новая компания']]
      .filter(([m]) => m === 'join' || (m === 'individual' ? S.signup.individual : S.signup.org));
    const seg = `<div class="seg" style="margin-top:14px">${modes.map(([m, l]) => `<button class="${f.mode === m ? 'on' : ''}" onclick="S.f.mode='${m}';S.err=null;R()">${l}</button>`).join('')}</div>`;
    let top = '';
    if (f.mode === 'join') {
      top = `<label class="fld"><span>Код компании (его выдаёт администратор)</span><div class="row" style="gap:8px;flex-wrap:nowrap"><input class="in" style="flex:1;text-transform:uppercase" value="${esc(f.code)}" maxlength="12" oninput="S.f.code=this.value;S.org=null" onkeydown="event.key==='Enter'&&lookupOrg()"><button class="btn s" style="width:auto" onclick="lookupOrg()">Найти</button></div></label>`;
      if (S.org) top += `<p class="ok" style="margin-top:8px;font-weight:700">Компания: ${esc(S.org.name)}</p>` +
        (S.org.departments.length ? `<label class="fld"><span>Подразделение</span><select class="in" onchange="S.f.dept_id=this.value"><option value="">Выберите…</option>${S.org.departments.map(d => `<option value="${d.id}" ${String(f.dept_id) === String(d.id) ? 'selected' : ''}>${esc(d.name)}</option>`).join('')}</select></label>` : '');
    } else if (f.mode === 'create_org') {
      top = fld('Название компании', 'org_name') + `<label class="fld"><span>Подразделения через запятую (можно изменить позже)</span><input class="in" placeholder="HR, Бухгалтерия, Склад" value="${esc(f.departments)}" oninput="S.f.departments=this.value"></label>`;
    }
    form = `${seg}${top}<div class="grid-in">${fld('Имя', 'name', 'text', 'maxlength="28" autocomplete="given-name"')}${fld('Фамилия', 'last', 'text', 'maxlength="31" autocomplete="family-name"')}</div><p class="sm mut" style="margin-top:6px">Черепундель будет обращаться к вам по имени.</p><div class="seg" style="margin-top:12px">${[['f', 'Женский'], ['m', 'Мужской']].map(([g, l]) => `<button class="${f.gender === g ? 'on' : ''}" onclick="S.f.gender='${g}';R()">${l}</button>`).join('')}</div><p class="sm mut" style="margin-top:6px">Пол нужен, чтобы подобрать иллюстрации в сюжетах.</p>${fld('Рабочая почта', 'email', 'email', 'autocomplete="username"')}${fld('Пароль', 'password', 'password', 'autocomplete="new-password"')}<p class="sm mut" style="margin-top:6px">Минимум 8 символов. Лучше длинная фраза из нескольких слов.</p>`;
  }
  const btn = login ? 'Войти' : f.mode === 'create_org' ? 'Создать компанию' : 'Зарегистрироваться';
  const sw = login ? `Нет аккаунта? <button class="link" onclick="authTab('register')">Зарегистрироваться</button>` : `Уже есть аккаунт? <button class="link" onclick="authTab('login')">Войти</button>`;
  return `<div class="au"><div class="glass"><button class="link back" onclick="authTab('intro')">‹ Назад</button><h2 style="margin-top:10px">${login ? 'С возвращением' : 'Создайте аккаунт'}</h2><p class="mut" style="margin-top:6px">${login ? 'Войдите, чтобы продолжить с того места, где остановились.' : 'Ваши звёзды и награды будут сохраняться.'}</p>${form}${S.err ? `<p class="err" role="alert">${esc(S.err)}</p>` : ''}<button class="btn pls" style="margin-top:18px" ${S.busy ? 'disabled' : ''} onclick="submitAuth()">${btn}</button><p class="sm mut" style="margin-top:14px;text-align:center">${sw}</p></div></div>`;
}

function authTab(t) { S.authTab = t; S.err = null; R(); }

async function lookupOrg() {
  S.err = null;
  try { S.org = await api('GET', '/orgs/lookup?code=' + encodeURIComponent(S.f.code.trim())); S.f.code = S.f.code.trim().toUpperCase(); }
  catch (e) { S.org = null; S.err = e.message; }
  R();
}

async function submitAuth() {
  if (S.busy) return;
  if (S.authTab !== 'login' && !S.f.gender) { S.err = 'Выберите пол: от него зависят иллюстрации в сюжетах'; R(); return; }
  S.busy = true; S.err = null; R();
  try {
    const f = S.f, tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    let r;
    if (S.authTab === 'login') r = await api('POST', '/auth/login', { email: f.email, password: f.password });
    else r = await api('POST', '/auth/register', {
      mode: f.mode, gender: f.gender, name: (f.name.trim() + ' ' + f.last.trim()).trim(), email: f.email, password: f.password, tz,
      invite_code: f.code, dept_id: f.dept_id || null, org_name: f.org_name, departments: f.departments,
    });
    S.f.password = ''; S.user = r.user;
    await boot(true);
  } catch (e) { S.err = e.message; }
  S.busy = false; R();
}

async function logout() { try { await api('POST', '/auth/logout'); } catch (e) { /* уже вышли */ } S.user = null; S.P = null; S.v = 'auth'; S.authTab = 'intro'; R(); }

// ---------- обязательная смена пароля после сброса администратором ----------
S.pw = { cur: '', nw: '' };
function PwV() {
  return `<div class="wg"><div class="bob">${img(3)}</div><div class="auth"><div class="bub" style="min-height:0;font-size:17px;cursor:default;text-align:left">Администратор выдал вам временный пароль. Придумайте свой: длинную фразу, которую знаете только вы.</div><div class="card" style="margin-top:16px"><label class="fld"><span>Временный пароль</span><input class="in" type="password" oninput="S.pw.cur=this.value"></label><label class="fld"><span>Новый пароль</span><input class="in" type="password" autocomplete="new-password" oninput="S.pw.nw=this.value" onkeydown="event.key==='Enter'&&savePw()"></label>${S.err ? `<p class="err">${esc(S.err)}</p>` : ''}<button class="btn" style="margin-top:16px;width:100%" onclick="savePw()">Сохранить пароль</button></div></div></div>`;
}
async function savePw(fromProfile) {
  S.err = null;
  try {
    await api('POST', '/me/password', { current: S.pw.cur, new: S.pw.nw });
    S.pw = { cur: '', nw: '' }; S.user.must_change_password = false;
    if (fromProfile) { toast('Пароль изменён'); R(); } else await boot(true);
  } catch (e) { if (fromProfile) toast(e.message); else { S.err = e.message; R(); } }
}

// ---------- знакомство ----------
S.ws = 0; S.wd = []; S.wl = null;
function TY() {
  const e = document.getElementById('tw'); if (!e) return;
  if (matchMedia('(prefers-reduced-motion:reduce)').matches) { e.textContent = WT; return; }
  let i = 0; clearInterval(S.ti);
  S.ti = setInterval(() => { const x = document.getElementById('tw'); if (!x) { clearInterval(S.ti); return; } x.textContent = WT.slice(0, ++i); if (i >= WT.length) clearInterval(S.ti); }, 22);
}
function wh(id) { if (S.wd.includes(id)) return; S.wd.push(id); S.wl = id; R(); }
async function finishWelcome() {
  clearInterval(S.ti);
  try { await api('POST', '/me/onboarded'); S.user.onboarded = true; } catch (e) { /* не критично */ }
  go('home');
}
function WelcomeV() {
  const name = esc(S.user.name.split(' ')[0]), n = S.wd.filter(x => x !== 'c').length;
  const cl = id => S.wd.includes(id) ? (id === 'c' ? 'no' : 'ok') : '', up = S.wl && S.wl !== 'c';
  const stp = `<div class="stp" aria-hidden="true">${[0, 1, 2].map(i => `<i class="${i <= S.ws ? 'on' : ''}"></i>`).join('')}</div>`;
  if (S.ws === 0) return `${stp}<div class="wg"><div class="bob">${img(1)}</div><div><div class="bub" title="Нажмите, чтобы показать весь текст" onclick="clearInterval(S.ti);tw.textContent=WT"><span id="tw"></span></div><div class="row" style="margin-top:20px"><button class="btn pls" onclick="S.ws=1;R()">Познакомиться</button></div><button class="btn s" style="margin-top:16px;padding:8px 14px" onclick="finishWelcome()">Пропустить знакомство</button></div></div>`;
  if (S.ws === 1) return `${stp}<div class="wg"><div class="${up ? 'jump' : 'bob'}">${img(up ? 6 : 5)}</div><div><div class="bub" aria-live="polite" style="min-height:0;font-size:17px">${S.wl ? WM[S.wl] : `Приятно познакомиться, ${name}! Вот так выглядят мои уроки. Это письмо пришло «от директора». Нажмите на то, что кажется подозрительным.`}</div><div class="mail" style="margin-top:16px"><div class="h sm">От: <button class="hot ${cl('a')}" onclick="wh('a')">Анатолий Рябов &lt;a.ryabov@severny-kontur.<b>co</b>&gt;</button></div><p><button class="hot ${cl('c')}" onclick="wh('c')">Добрый день, ${name}!</button></p><p style="margin-top:8px"><button class="hot ${cl('b')}" onclick="wh('b')">Срочно оплатите счёт до 15:00, иначе договор будет расторгнут.</button></p></div><div class="row" style="margin-top:16px"><b>Найдено ${n} из 2</b>${n === 2 ? `<span class="pp">${stars(1, 1)} звезда</span><button class="btn pls" onclick="S.ws=2;R()">Дальше</button>` : ''}</div></div></div>`;
  return `${stp}<div class="wg"><div class="jump">${img(6)}</div><div><h1>Вы справились, ${name}!</h1><p class="mut" style="margin:10px 0 18px;font-size:18px">Так всё и устроено. Каждая неделя это история из рабочего дня: вы выбираете действие, я объясняю, что получилось, а потом короткий тест. За успехи вы получаете звёзды. Они повышают уровень, открывают новые недели и новые образы Черепундельчика.</p><div class="row" style="gap:10px;margin-bottom:22px">${[1, 2, 3, 4, 5, 6, 7, 8].map(i => `<img src="${M(i)}" alt="" class="${i > 1 ? 'lk' : ''}" style="height:64px;width:auto">`).join('')}</div><button class="btn pls" onclick="finishWelcome()">Начать первую неделю</button></div></div>`;
}
