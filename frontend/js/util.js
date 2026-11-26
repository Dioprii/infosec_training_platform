/* Общие помощники: состояние, запросы к API, мелкие компоненты интерфейса. */
const S = {
  v: 'boot', user: null, course: null, P: null, team: null, daily: null,
  wk: null, flash: 0, signup: { individual: true, org: true },
};

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const M = n => `/assets/mascot/turtle-${n}.webp`;
const img = (n, w) => `<img src="${M(n)}" alt="Черепундель" ${w ? `width="${w}"` : ''}>`;
const bar = p => `<div class="bar"><i style="width:${Math.max(0, Math.min(100, p))}%"></i></div>`;
const stars = (n, t = 3) => Array.from({ length: t }, (_, i) =>
  `<svg width="18" height="18" viewBox="0 0 24 24" style="vertical-align:-3px"><path d="M12 2l3 6.5 7 .8-5.2 4.8 1.5 7-6.3-3.6L5.7 21l1.5-7L2 9.3l7-.8z" style="fill:${i < n ? 'var(--st)' : 'var(--ln)'}"/></svg>`).join('');

async function api(method, url, data) {
  const opt = { method, credentials: 'same-origin', headers: {} };
  if (method !== 'GET') { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(data ?? {}); }
  let r;
  try { r = await fetch('/api' + url, opt); }
  catch (e) { throw Object.assign(new Error('Нет связи с сервером. Проверьте интернет и попробуйте ещё раз'), { status: 0 }); }
  let j = null;
  try { j = await r.json(); } catch (e) { /* пустой ответ */ }
  if (!r.ok) {
    if (r.status === 401 && S.user && !url.startsWith('/auth/')) { S.user = null; S.v = 'auth'; R(); }
    throw Object.assign(new Error((j && j.error) || 'Что-то пошло не так'), { status: r.status, field: j && j.field });
  }
  return j;
}

let toastTimer;
function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 4200);
}

// ---------- уровни и модули (данные приходят с сервера) ----------
const TH = () => S.course.thresholds;
const RD = () => S.course.levels;
const MOD = k => S.course.modules.find(m => m.id === k);
const MS = k => S.P.modules[k].state;
const LESSON = key => { for (const m of S.course.modules) for (const l of m.lessons) if (l.key === key) return l; };

const RWC = l => { const r = RD()[l - 1]; return `<div class="card pop" style="margin-bottom:18px;display:flex;gap:16px;align-items:center;border:2px solid var(--st)"><img src="${M(r.mascot)}" width="96" alt=""><div><h3>Новый уровень ${l}: ${esc(r.title)}</h3><p class="sm" style="margin:4px 0">Награда: ${esc(r.reward)}</p><p class="sm mut">Открыто: ${esc(r.unlocks)}</p></div></div>`; };
const takeFlash = () => { const l = S.flash; S.flash = 0; return l ? RWC(l) : ''; };

const fmtDate = s => { if (!s) return '—'; const [y, m, d] = s.slice(0, 10).split('-'); return `${d}.${m}.${y}`; };
const plural = (n, a, b, c) => { const m = Math.abs(n) % 100, k = m % 10; return m > 10 && m < 20 ? c : k > 1 && k < 5 ? b : k === 1 ? a : c; };
const copyText = async t => { try { await navigator.clipboard.writeText(t); toast('Скопировано'); } catch (e) { toast('Не удалось скопировать. Выделите текст вручную'); } };
