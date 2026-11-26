/* Кабинет администратора компании. По людям виден только прогресс, ответы конкретных сотрудников не показываются. */
S.ad = { tab: 'ov', q: '', temp: null };

async function loadAdmin() {
  const [ov, us, dp, org] = await Promise.all([api('GET', '/admin/overview'), api('GET', '/admin/users'), api('GET', '/admin/departments'), api('GET', '/admin/org')]);
  Object.assign(S.ad, { ov, users: us.users, depts: dp.departments, org });
}
async function adReload() { try { await loadAdmin(); } catch (e) { toast(e.message); } R(); }
async function adDo(fn, ok) { try { const r = await fn(); if (ok) toast(ok); await loadAdmin(); R(); return r; } catch (e) { toast(e.message); } }

const adTab = t => { S.ad.tab = t; S.ad.temp = null; R(); scrollTo(0, 0); };

V.adm = () => {
  const a = S.ad, tabs = [['ov', 'Обзор'], ['users', 'Сотрудники'], ['depts', 'Подразделения'], ['set', 'Настройки компании']];
  return `<div class="hero pop"><div><h1>${a.tab === 'ov' ? 'Обзор обучения' : 'Кабинет администратора'}</h1><p class="mut" style="margin-top:8px">${esc(a.ov.org)}: курс «Основы ИБ», ${a.ov.employees} ${plural(a.ov.employees, 'сотрудник', 'сотрудника', 'сотрудников')}. В обзоре данные показаны по подразделениям, без имён и без ответов отдельных людей.</p></div>${img(8)}</div><div class="tabs">${tabs.map(([k, l]) => `<button class="${a.tab === k ? 'on' : ''}" onclick="adTab('${k}')">${l}</button>`).join('')}</div>${{ ov: adOverview, users: adUsers, depts: adDepts, set: adSettings }[a.tab]()}`;
};

function adOverview() {
  const o = S.ad.ov, tile = (n, t, s) => `<div class="card tile"><div><div class="num">${n}</div><b>${t}</b><div class="sm mut">${s}</div></div></div>`;
  const max = Math.max(1, ...o.activity.map(x => x.users));
  return `<div class="g g4" style="margin-top:12px">${tile(o.employees, 'сотрудников', 'в компании')}${tile(o.started, 'начали', 'прошли хотя бы урок')}${tile(o.active7, 'активны', 'за последние 7 дней')}${tile(o.certified, 'с сертификатом', `курс пройден: ${o.completed}`)}</div>
<div class="g g2" style="margin-top:16px;align-items:start"><div class="card"><h3>Прогресс по подразделениям</h3><p class="sm mut" style="margin-top:4px">Средний процент пройденных уроков. Общий: ${o.progress}%.</p><table class="tb">${o.departments.map(d => `<tr><td style="width:130px">${esc(d.name)}<div class="sm mut">${d.members} ${plural(d.members, 'человек', 'человека', 'человек')}</div></td><td>${bar(d.progress)}</td><td style="width:44px;text-align:right">${d.progress}%</td></tr>`).join('')}</table></div>
<div class="card"><h3>Где чаще ошибаются</h3>${o.errors.hidden ? `<p class="sm mut" style="margin-top:10px">Сводка появится, когда ответят хотя бы ${o.errors.min_group} сотрудника: так по ней нельзя узнать, как ответил конкретный человек.</p>` : `<p class="sm mut" style="margin:4px 0 8px">Доля неверных ответов по темам.</p><table class="tb">${o.errors.topics.map(t => `<tr><td style="width:150px">${esc(t.topic)}</td><td>${bar(t.error_rate)}</td><td style="width:44px;text-align:right">${t.error_rate}%</td></tr>`).join('')}</table>`}</div></div>
<div class="g g2" style="margin-top:16px;align-items:start"><div class="card"><h3>Сколько человек прошли неделю</h3><table class="tb">${o.modules.map(m => `<tr><td style="width:130px">${m.id}. ${esc(m.short)}</td><td>${bar(m.share)}</td><td style="width:44px;text-align:right">${m.share}%</td></tr>`).join('')}</table></div>
<div class="card"><h3>Активность за 14 дней</h3><p class="sm mut" style="margin-top:4px">Сколько сотрудников занимались в каждый день.</p><div class="chart" role="img" aria-label="Активность по дням">${o.activity.map(x => `<i title="${fmtDate(x.day)}: ${x.users}" style="height:${Math.round(x.users / max * 100)}%"></i>`).join('')}</div></div></div>`;
}

function adRows() {
  const q = S.ad.q.trim().toLowerCase(), me = S.user.id;
  const rows = S.ad.users.filter(u => !q || u.name.toLowerCase().includes(q) || u.email.includes(q));
  const el = document.getElementById('adrows'); if (!el) return;
  el.innerHTML = rows.map(u => `<tr style="${u.active ? '' : 'opacity:.5'}"><td><b>${esc(u.name)}</b>${u.role === 'admin' ? ' <span class="tag">админ</span>' : ''}${u.id === me ? ' <span class="tag">вы</span>' : ''}<div class="sm mut">${esc(u.email)}</div></td>
<td><select class="sel" onchange="adDo(()=>api('PATCH','/admin/users/${u.id}',{dept_id:this.value?+this.value:null}))"><option value="">Не указано</option>${S.ad.depts.map(d => `<option value="${d.id}" ${u.dept_id === d.id ? 'selected' : ''}>${esc(d.name)}</option>`).join('')}</select></td>
<td style="min-width:110px">${bar(u.progress)}<div class="sm mut">${u.progress}% · недель ${u.weeks}/7${u.certified ? ' · сертификат' : ''}</div></td><td>${u.stars}</td><td>${fmtDate(u.last_active)}</td>
<td style="white-space:nowrap"><button class="link" onclick="adReset(${u.id})">Сбросить пароль</button><br><button class="link" onclick="adToggle(${u.id},'active',${u.active ? 'false' : 'true'})">${u.active ? 'Отключить' : 'Включить'}</button> · <button class="link" onclick="adToggle(${u.id},'role','${u.role === 'admin' ? 'learner' : 'admin'}')">${u.role === 'admin' ? 'Снять админа' : 'Сделать админом'}</button></td></tr>`).join('') || `<tr><td colspan="6" class="mut">Никого не найдено</td></tr>`;
}
function adUsers() {
  setTimeout(adRows, 0);
  const t = S.ad.temp;
  return `${t ? `<div class="card pop" style="margin-top:12px;border:2px solid var(--st)"><h3>Временный пароль для ${esc(t.name)}</h3><p style="margin:8px 0"><span class="codebox" style="font-size:20px">${esc(t.pw)}</span></p><p class="sm mut">Передайте его сотруднику лично. При входе система попросит придумать свой. Это окно больше не покажет пароль.</p><button class="btn s" style="margin-top:10px" onclick="copyText('${esc(t.pw)}')">Скопировать</button></div>` : ''}<div class="card" style="margin-top:12px"><div class="row" style="justify-content:space-between"><input class="in" style="flex:1;max-width:320px" placeholder="Поиск по имени или почте" value="${esc(S.ad.q)}" oninput="S.ad.q=this.value;adRows()"><a class="btn s" style="text-decoration:none" href="/api/admin/export.csv">Скачать CSV</a></div><p class="sm mut" style="margin:10px 0">Здесь виден только прогресс. Ответы и ошибки конкретных людей администратору не показываются.</p><div class="tblw"><table class="tbl"><thead><tr><th>Сотрудник</th><th>Подразделение</th><th>Прогресс</th><th>Звёзд</th><th>Активность</th><th></th></tr></thead><tbody id="adrows"></tbody></table></div></div>`;
}
const adToggle = (id, k, v) => adDo(() => api('PATCH', '/admin/users/' + id, { [k]: v }), 'Сохранено');
async function adReset(id) {
  const u = S.ad.users.find(x => x.id === id);
  if (!confirm(`Сбросить пароль для «${u.name}»? Текущие входы будут закрыты.`)) return;
  const r = await adDo(() => api('POST', `/admin/users/${id}/reset-password`));
  if (r) { S.ad.temp = { name: u.name, pw: r.temp_password }; R(); scrollTo(0, 0); }
}

function adDepts() {
  return `<div class="card" style="margin-top:12px"><h3>Подразделения</h3><p class="sm mut" style="margin:4px 0 12px">Сотрудники выбирают подразделение при регистрации. По ним считаются прогресс и командный зачёт.</p><table class="tb">${S.ad.depts.map(d => `<tr><td>${esc(d.name)}</td><td class="sm mut">${d.members} ${plural(d.members, 'человек', 'человека', 'человек')}</td><td style="text-align:right;white-space:nowrap"><button class="link" onclick="adRename(${d.id})">Переименовать</button> · <button class="link" onclick="adDelDept(${d.id})">Удалить</button></td></tr>`).join('')}</table><div class="row" style="margin-top:16px"><input id="nd" class="in" placeholder="Новое подразделение" maxlength="60" onkeydown="event.key==='Enter'&&adAddDept()"><button class="btn" onclick="adAddDept()">Добавить</button></div></div>`;
}
const adAddDept = () => { const el = document.getElementById('nd'); if (el.value.trim()) adDo(() => api('POST', '/admin/departments', { name: el.value }), 'Добавлено'); };
function adRename(id) { const d = S.ad.depts.find(x => x.id === id), n = prompt('Новое название', d.name); if (n && n.trim()) adDo(() => api('PATCH', '/admin/departments/' + id, { name: n }), 'Сохранено'); }
function adDelDept(id) { const d = S.ad.depts.find(x => x.id === id); if (confirm(`Удалить «${d.name}»? Сотрудники останутся без подразделения.`)) adDo(() => api('DELETE', '/admin/departments/' + id), 'Удалено'); }

function adSettings() {
  const o = S.ad.org, url = location.origin;
  return `<div class="g g2" style="margin-top:12px;align-items:start"><div class="card"><h3>Как пригласить сотрудников</h3><p class="sm mut" style="margin:6px 0 12px">Сотрудник открывает ${esc(url)}, выбирает «Регистрация» → «Я сотрудник» и вводит код.</p><span class="codebox" id="code">${esc(o.invite_code)}</span><div class="row" style="margin-top:14px"><button class="btn s" onclick="copyText('${esc(o.invite_code)}')">Скопировать код</button><button class="btn s" onclick="adNewCode()">Выпустить новый код</button></div><p class="sm mut" style="margin-top:10px">Новый код делает старый недействительным. Уже зарегистрированных это не затрагивает.</p></div>
<div class="card"><h3>Параметры компании</h3><label class="fld"><span>Название</span><input id="on" class="in" value="${esc(o.name)}" maxlength="60"></label><label class="fld"><span>Разрешённый домен почты (необязательно)</span><input id="od" class="in" placeholder="company.ru" value="${esc(o.allowed_domain || '')}"></label><label class="fld"><span>Как открываются недели</span><select id="og" class="in"><option value="level" ${o.gating === 'level' ? 'selected' : ''}>По уровням: звёзды открывают недели</option><option value="sequential" ${o.gating === 'sequential' ? 'selected' : ''}>По порядку: следующая после предыдущей</option></select></label><p class="sm mut" style="margin-top:8px">«По порядку» подходит для обязательного обучения со сроком: никто не застрянет из-за нехватки звёзд.</p><button class="btn" style="margin-top:14px" onclick="adSaveOrg()">Сохранить</button></div></div>`;
}
const adNewCode = () => { if (confirm('Выпустить новый код? Старый перестанет работать.')) adDo(() => api('POST', '/admin/org/regenerate-code'), 'Новый код готов'); };
const adSaveOrg = () => adDo(() => api('PATCH', '/admin/org', { name: on.value, allowed_domain: od.value, gating: og.value }), 'Сохранено');
