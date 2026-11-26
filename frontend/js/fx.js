/* Переливающийся фон экрана входа: WebGL-шейдер, реагирует на движение мыши. */
(function () {
  const c = document.getElementById('fx'); if (!c) return;
  const still = matchMedia('(prefers-reduced-motion:reduce)').matches;
  let gl, U, raf = 0, on = false, mx = .5, my = .5, tx = .5, ty = .5, t0 = performance.now();
  const VS = 'attribute vec2 a;void main(){gl_Position=vec4(a,0.,1.);}';
  const FS = `precision highp float;uniform vec2 r;uniform float t;uniform vec2 m;uniform float dk;
float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x),f.y);}
float fbm(vec2 p){float a=.5,s=0.;for(int i=0;i<4;i++){s+=a*n(p);p=p*2.03+17.;a*=.5;}return s;}
void main(){
  vec2 p=(gl_FragCoord.xy-.5*r)/min(r.x,r.y);
  vec2 mm=(m-.5)*vec2(r.x/r.y,1.);
  float tt=t*.08;
  vec2 q=vec2(fbm(p*1.2+tt),fbm(p*1.2+5.2-tt));
  vec2 w=p+(q-.5)*1.2;
  vec2 dm=p-mm; w+=dm*.55*exp(-dot(dm,dm)*4.);
  float f=fbm(w*1.5+vec2(tt,-tt));
  float g=fbm(w*2.2-tt+9.);
  float d0=dot(w,vec2(.707,.707))+(f-.5)*.9;
  float fld=1.-abs(d0)/.62-g*.35;
  float mask=smoothstep(.0,.3,fld);
  float k=clamp(fld,0.,1.);
  vec3 mint=vec3(.37,.92,.75),cyan=vec3(.16,.78,.93),blue=vec3(.30,.54,.88),pale=vec3(.76,.97,.98);
  vec3 col=mix(mint,cyan,smoothstep(.0,.22,k));
  col=mix(col,blue,smoothstep(.18,.45,k));
  float rid=.5+.5*sin(k*10.+f*7.+tt*3.);
  col=mix(col,pale,smoothstep(.35,.95,k)*rid);
  vec3 base=mix(vec3(.957,.961,.965),vec3(.071,.102,.2),dk);
  vec3 o=mix(base,col,mask*(1.-.25*dk));
  o+=(h(gl_FragCoord.xy+fract(t))-.5)*.07;
  gl_FragColor=vec4(o,1.);
}`;
  function sh(type, src) { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); return s; }
  function init() {
    gl = c.getContext('webgl', { antialias: false, alpha: false });
    if (!gl) return false;
    const pr = gl.createProgram(); gl.attachShader(pr, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, FS));
    gl.linkProgram(pr); if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) return false;
    gl.useProgram(pr);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const a = gl.getAttribLocation(pr, 'a'); gl.enableVertexAttribArray(a); gl.vertexAttribPointer(a, 2, gl.FLOAT, false, 0, 0);
    U = {}; ['r', 't', 'm', 'dk'].forEach(k => { U[k] = gl.getUniformLocation(pr, k); });
    return true;
  }
  function size() { const k = .75; c.width = Math.round(innerWidth * k); c.height = Math.round(innerHeight * k); gl.viewport(0, 0, c.width, c.height); }
  function draw() {
    mx += (tx - mx) * .06; my += (ty - my) * .06;
    gl.uniform2f(U.r, c.width, c.height); gl.uniform1f(U.t, still ? 4 : (performance.now() - t0) / 1000);
    gl.uniform2f(U.m, mx, my); gl.uniform1f(U.dk, matchMedia('(prefers-color-scheme:dark)').matches ? 1 : 0);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
  function loop() { draw(); raf = on && !still && !document.hidden ? requestAnimationFrame(loop) : 0; }
  function kick() { if (on && !raf) loop(); }
  addEventListener('pointermove', e => { tx = e.clientX / innerWidth; ty = 1 - e.clientY / innerHeight; });
  addEventListener('resize', () => { if (gl && on) { size(); draw(); } });
  document.addEventListener('visibilitychange', kick);
  window.fxSet = function (v) {
    if (v === on) return; on = v;
    if (!v) { cancelAnimationFrame(raf); raf = 0; return; }
    if (!gl && !init()) { document.body.classList.add('nogl'); return; }
    size(); kick();
  };
})();
