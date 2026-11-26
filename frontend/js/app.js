/* Запуск приложения. */
async function boot() {
  try {
    const sess = await api('GET', '/session');
    S.signup = sess.signup;
    if (!sess.user) { S.user = null; S.v = 'auth'; R(); return; }
    const b = await api('GET', '/bootstrap');
    S.user = b.user; S.course = b.course; S.P = b.progress;
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (tz && tz !== S.user.tz) api('PATCH', '/me', { tz }).then(r => { S.user = r.user; }).catch(() => {});
    if (S.user.must_change_password) { S.v = 'pw'; R(); }
    else if (!S.user.onboarded) { S.v = 'welcome'; S.ws = 0; S.wd = []; S.wl = null; R(); }
    else await go('home');
  } catch (e) {
    document.getElementById('mn').innerHTML = `<div class="load"><div class="card" style="max-width:420px;text-align:center"><h3>Не удалось загрузить</h3><p class="sm mut" style="margin:8px 0 14px">${esc(e.message)}</p><button class="btn" onclick="boot()">Повторить</button></div></div>`;
  }
}
boot();
