/**
 * One wind field, drawn as instanced WebGL2 flakes.
 * Canvas2D is the fallback when WebGL2 is missing.
 * The canvas stays pointer-events: none and is sized from the layout viewport.
 */

export type WeatherScene = {
  act: string;
  p: number;
  pointerX: number;
  pointerY: number;
  scroll: number;
  scarf: { x: number; y: number } | null;
};

export const viewSize = (): { w: number; h: number } => {
  const vv = window.visualViewport;
  const w = Math.round(vv?.width ?? document.documentElement.clientWidth);
  const h = Math.round(vv?.height ?? document.documentElement.clientHeight);
  return { w: Math.max(1, w), h: Math.max(1, h) };
};

type Ribbon = { x: number; y: number; px: number; py: number };

type Runtime = {
  resize: () => void;
  frame: (now: number, scene: WeatherScene) => void;
  gust: (x: number, y: number, vx: number, vy: number) => void;
  puff: (x: number, y: number) => void;
  impact: () => void;
  ribbon: () => Ribbon[];
  pressure: () => number;
};

let runtime: Runtime | null = null;
let heard = { strength: 0, ember: false };

export function weatherAudio(): { strength: number; ember: boolean } {
  return heard;
}
let tiltX = 0;
let tiltY = 0;
let tiltOn = false;
const cues: { crystal: () => void; crackle: () => void } = { crystal() {}, crackle() {} };

export function setWeatherCues(next: { crystal?: () => void; crackle?: () => void }): void {
  if (next.crystal) cues.crystal = next.crystal;
  if (next.crackle) cues.crackle = next.crackle;
}

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

export function enableTilt(): void {
  if (tiltOn) return;
  tiltOn = true;
  const Ori = window.DeviceOrientationEvent as typeof DeviceOrientationEvent & {
    requestPermission?: () => Promise<PermissionState>;
  };
  const listen = () => {
    window.addEventListener("deviceorientation", (event) => {
      tiltX = clamp((event.gamma ?? 0) / 50, -1, 1);
      tiltY = clamp(((event.beta ?? 45) - 45) / 50, -1, 1);
    });
  };
  if (typeof Ori?.requestPermission === "function") {
    void Ori.requestPermission().then((state) => {
      if (state === "granted") listen();
    }).catch(() => undefined);
  } else listen();
}

export function mountWeather(canvas: HTMLCanvasElement): void {
  runtime = createWeather(canvas);
}

export function weatherFrame(now: number, scene: WeatherScene): void {
  runtime?.frame(now, scene);
}

export function weatherGust(x: number, y: number, vx: number, vy: number): void {
  runtime?.gust(x, y, vx, vy);
}

export function weatherPuff(x: number, y: number): void {
  runtime?.puff(x, y);
}

export function weatherImpact(): void {
  runtime?.impact();
}

export function weatherRibbon(): Ribbon[] {
  return runtime?.ribbon() ?? [];
}

export function weatherPressure(): number {
  return runtime?.pressure() ?? 0;
}

export function weatherResize(): void {
  runtime?.resize();
}

export function paintStillSnow(canvas: HTMLCanvasElement): void {
  const { w, h } = viewSize();
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.clearRect(0, 0, w, h);
  for (let i = 0; i < 70; i++) {
    const x = hash(i + 1) * w;
    const y = hash(i + 9) * h;
    const r = 1 + hash(i + 3) * 3.2;
    ctx.fillStyle = `rgba(243,238,227,${0.25 + hash(i + 4) * 0.55})`;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
  }
  document.body.style.backgroundImage = `url(${canvas.toDataURL("image/png")})`;
  document.body.style.backgroundSize = "auto";
  canvas.style.display = "none";
}

const hash = (n: number) => {
  const x = Math.sin(n * 127.1) * 43758.5453;
  return x - Math.floor(x);
};

const VERT = `#version 300 es
precision highp float;
layout(location=0) in vec2 aCorner;
layout(location=1) in vec4 aSeed;
uniform vec2 uRes;
uniform float uTime;
uniform vec2 uWind;
uniform vec2 uGust;
uniform float uGustLife;
uniform float uShock;
uniform vec2 uShockAt;
uniform float uMode;
uniform vec3 uRing;
uniform vec2 uTilt;
out float vDepth;
out vec2 vUv;
out float vNear;

float hash2(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){
  vec2 i=floor(p); vec2 f=fract(p);
  float a=hash2(i), b=hash2(i+vec2(1.0,0.0)), c=hash2(i+vec2(0.0,1.0)), d=hash2(i+vec2(1.0,1.0));
  vec2 u=f*f*(3.0-2.0*f);
  return mix(mix(a,b,u.x),mix(c,d,u.x),u.y);
}
vec2 curl(vec2 p){
  float e=0.2;
  float dx=noise(p+vec2(e,0.0))-noise(p-vec2(e,0.0));
  float dy=noise(p+vec2(0.0,e))-noise(p-vec2(0.0,e));
  return vec2(dy,-dx);
}
void main(){
  float depth=aSeed.z;
  float grav=uMode>0.5 && uMode<1.5 ? -1.0 : 1.0;
  float speed=mix(18.0,78.0,depth)*(uMode>1.5?0.22:1.0);
  vec2 flow=curl(aSeed.xy*3.4+vec2(uTime*0.06,uTime*0.02));
  vec2 wind=uWind+uTilt;
  float amp=clamp(length(wind)/280.0,0.0,1.0);
  float x=fract(aSeed.x+flow.x*0.05*amp+wind.x*uTime/uRes.x)*uRes.x;
  float y=fract(aSeed.y+grav*speed*uTime/uRes.y+flow.y*0.03)*uRes.y;
  if(uRing.z>1.0 && distance(vec2(x,y),uRing.xy)<uRing.z){
    x=mix(aSeed.x*uRes.x,x,0.12);
    y=fract(aSeed.y+grav*speed*0.65*uTime/uRes.y)*uRes.y;
  }
  vec2 pos=vec2(x,y);
  vec2 from=pos-uGust;
  float gd=length(from);
  if(uGustLife>0.01 && gd<240.0){
    pos+=(from/max(gd,1.0))*(1.0-gd/240.0)*110.0*uGustLife;
  }
  if(uShock>1.0){
    vec2 s=pos-uShockAt;
    float sd=length(s);
    float band=smoothstep(uShock+30.0,uShock,sd)*smoothstep(uShock-90.0,uShock-20.0,sd);
    pos+=(s/max(sd,1.0))*band*64.0;
  }
  float hand=step(uRes.x,840.0);
  float size=depth<0.33?mix(20.0,12.0,depth/0.33)*mix(1.0,2.7,hand):mix(5.5,1.6,depth)*mix(1.0,1.25,hand);
  vec2 vel=wind+vec2(0.0,grav*speed);
  float stretch=1.0+clamp(length(vel)/320.0,0.0,2.6);
  vec2 dir=length(vel)>8.0?normalize(vel):vec2(0.0,grav);
  vec2 side=vec2(-dir.y,dir.x);
  vec2 offset=dir*aCorner.y*size*stretch+side*aCorner.x*size;
  vec2 px=pos+offset;
  vec2 clip=(px/uRes)*2.0-1.0;
  clip.y=-clip.y;
  gl_Position=vec4(clip,0.0,1.0);
  vDepth=depth;
  vUv=aCorner+0.5;
  vNear=depth<0.33?(hand>0.5?2.0:1.0):0.0;
}`;

const FRAG = `#version 300 es
precision mediump float;
in float vDepth;
in vec2 vUv;
in float vNear;
uniform float uMode;
out vec4 o;
void main(){
  float d=length((vUv-0.5)*2.0);
  if(d>1.0) discard;
  float near=step(0.5,vNear);
  float phone=step(1.5,vNear);
  float inner=mix(0.5,mix(0.28,0.02,phone),near);
  float alpha=(1.0-smoothstep(inner,1.0,d))*(near>0.5?mix(0.55,0.74,phone):0.9)*mix(0.72,1.0,vDepth);
  vec3 col=uMode>0.5 && uMode<1.5 ? vec3(1.0,0.46,0.1) : vec3(0.97,0.96,0.92);
  if(uMode>1.5) col=vec3(0.45, 0.43, 0.4);
  o=vec4(col,alpha);
}`;

const VVERT = `#version 300 es
precision highp float;
layout(location=0) in vec2 aPos;
void main(){ gl_Position=vec4(aPos,0.0,1.0); }`;

const VFRAG = `#version 300 es
precision mediump float;
uniform vec2 uRes;
uniform float uPressure;
out vec4 o;
void main(){
  vec2 uv=gl_FragCoord.xy/uRes;
  float v=smoothstep(0.26,1.0,length((uv-vec2(0.5,0.4))*vec2(1.08,1.22)));
  float fringe=smoothstep(0.55,1.0,v)*uPressure;
  vec3 col=vec3(0.02,0.0,0.015)*v*uPressure;
  col.r+=fringe*0.55;
  col.b+=fringe*0.12;
  o=vec4(col,v*uPressure*0.92);
}`;

const createWeather = (canvas: HTMLCanvasElement): Runtime => {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const gl = reduced ? null : canvas.getContext("webgl2", { alpha: true, antialias: false, premultipliedAlpha: false });
  const gpu = gl ? buildGpu(gl) : null;
  const ctx2d = gpu ? null : canvas.getContext("2d");
  const max = 7000;
  const narrow0 = viewSize().w <= 800;
  let count = narrow0 ? 1000 : 4200;
  let tuned = reduced;
  const samples: number[] = [];
  let last = performance.now();
  let started = performance.now();
  let sim = 0;
  let frozenSim = 0;
  let freezeUntil = 0;
  let shockStart = 0;
  let gustX = 0;
  let gustY = 0;
  let gustLife = 0;
  let mode = 0;
  let pressure = 0;
  let prevX = 0;
  let prevY = 0;
  let crystalAt = 0;
  const chain: Ribbon[] = Array.from({ length: 12 }, () => ({ x: 0, y: 0, px: 0, py: 0 }));
  let chainReady = false;
  const hidden = () => document.visibilityState === "hidden";

  const resize = () => {
    const { w, h } = viewSize();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    if (gl) gl.viewport(0, 0, canvas.width, canvas.height);
  };
  resize();

  const field = (scene: WeatherScene, w: number) => {
    const pull = (scene.pointerX - w * 0.5) / Math.max(1, w);
    let wx = tiltX * 36;
    let wy = tiltY * 12;
    mode = 0;
    pressure = 0;
    if (scene.act === "awaken") {
      wx *= 0.2;
    } else if (scene.act === "return") {
      if (scene.p >= 0.55) {
        mode = 2;
        wx = 0;
        wy = 0;
      } else wx *= 0.12;
      pressure = scene.p > 0.4 ? 0.18 : 0.04;
    } else if (scene.act === "intrusion") {
      wx += pull * (80 + scene.p * 220);
      pressure = 0.25 + scene.p * 0.45;
    } else if (scene.act === "clash") {
      wx += pull * 60;
      pressure = 0.62;
    } else if (scene.act === "observe") {
      wx *= 0.3 + scene.p * 0.35;
      pressure = 0.08 + scene.p * 0.22;
    } else if (scene.act === "neko" && scene.p < 0.42) {
      wx += 70 + scene.p * 80;
      pressure = 0.62 + scene.p * 0.5;
    } else if (scene.act === "neko" && scene.p >= 0.42) {
      mode = 1;
      wy -= 40;
      pressure = 0.2;
    } else if (scene.act === "kakoi") {
      wx += scene.p >= 0.26 ? 260 : 80;
      pressure = scene.p < 0.26 ? 0.72 : 0.05;
    } else if (scene.act === "still") {
      mode = 2;
      wx = 0;
      wy = 0;
    }
    wx += scene.scroll * 140;
    heard = { strength: clamp(Math.hypot(wx, wy) / 300, 0, 1), ember: mode === 1 };
    const wake = Math.hypot(scene.pointerX - prevX, scene.pointerY - prevY);
    if (wake > 0.5 && wake < 80) {
      wx += (scene.pointerX - prevX) * 0.8;
      wy += (scene.pointerY - prevY) * 0.8;
    }
    prevX = scene.pointerX;
    prevY = scene.pointerY;
    return { wx, wy };
  };

  const stepRibbon = (anchor: { x: number; y: number } | null, wx: number, wy: number) => {
    if (!anchor) {
      chainReady = false;
      return;
    }
    if (!chainReady) {
      for (let i = 0; i < chain.length; i++) {
        chain[i].x = chain[i].px = anchor.x - i * 10;
        chain[i].y = chain[i].py = anchor.y + i * 6;
      }
      chainReady = true;
    }
    chain[0].x = chain[0].px = anchor.x;
    chain[0].y = chain[0].py = anchor.y;
    for (let i = 1; i < chain.length; i++) {
      const n = chain[i];
      const vx = (n.x - n.px) * 0.92 + wx * 0.012;
      const vy = (n.y - n.py) * 0.92 + 0.35 + wy * 0.004;
      n.px = n.x;
      n.py = n.y;
      n.x += vx;
      n.y += vy;
    }
    for (let pass = 0; pass < 3; pass++) {
      for (let i = 1; i < chain.length; i++) {
        const a = chain[i - 1];
        const b = chain[i];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.hypot(dx, dy) || 1;
        const diff = (dist - 12) / dist;
        const ox = dx * diff * 0.5;
        const oy = dy * diff * 0.5;
        if (i > 1) {
          a.x += ox;
          a.y += oy;
        }
        b.x -= ox;
        b.y -= oy;
      }
    }
  };

  const frame = (now: number, scene: WeatherScene) => {
    if (hidden()) return;
    const { w, h } = viewSize();
    const dt = Math.min(40, now - last);
    last = now;
    if (!tuned) {
      samples.push(dt);
      if (now - started > 2000 && samples.length > 20) {
        tuned = true;
        const avg = samples.reduce((s, n) => s + n, 0) / samples.length;
        if (avg > 28) count = Math.max(480, Math.floor(count * 0.55));
        else if (avg < 18 && w > 900) count = Math.min(max, Math.floor(count * 1.45));
      }
    }
    const { wx, wy } = field(scene, w);
    if (now >= freezeUntil) sim += dt / 1000;
    else frozenSim = sim;
    gustLife = Math.max(0, gustLife - dt / 700);
    const showTime = now < freezeUntil ? frozenSim : sim;
    const shock = shockStart > 0 && now > shockStart && now < shockStart + 520
      ? ((now - shockStart) / 520) * Math.max(w, h)
      : 0;
    const ringR = scene.act === "kakoi" && scene.p > 0.08 ? Math.min(w, h) * 0.34 : -1;
    stepRibbon(scene.scarf, wx, wy);
    document.documentElement.style.setProperty("--pressure", pressure.toFixed(3));
    document.documentElement.classList.toggle("is-pressure", pressure > 0.18);
    if (scene.act === "observe") lightText(showTime, w, h, wx);
    if (pressure < 0.12 && mode === 0 && now - crystalAt > 700 && Math.random() < 0.04) {
      crystalAt = now;
      cues.crystal();
    }
    if (mode === 1 && Math.random() < 0.08) cues.crackle();
    if (gpu && gl) {
      gpu.draw(gl, canvas, count, w, h, showTime, wx, wy, gustX, gustY, gustLife, shock, mode, ringR, pressure);
      return;
    }
    paint2d(ctx2d, count, w, h, showTime, wx, wy, mode, shock);
  };

  return {
    resize,
    frame,
    gust(x, y, vx, vy) {
      const len = Math.hypot(vx, vy) || 1;
      gustX = x - (vx / len) * 36;
      gustY = y - (vy / len) * 36;
      gustLife = 1;
    },
    puff(x, y) {
      gustX = x;
      gustY = y;
      gustLife = 0.7;
    },
    impact() {
      freezeUntil = performance.now() + 250;
      frozenSim = sim;
      shockStart = freezeUntil;
    },
    ribbon: () => (chainReady ? chain : []),
    pressure: () => pressure,
  };
};

const lightText = (time: number, w: number, h: number, wx: number) => {
  const heads = document.querySelectorAll<HTMLElement>("h1, h2");
  heads.forEach((el) => el.classList.remove("is-lit"));
  for (let i = 0; i < 8; i++) {
    const x = (hash(i + 2) * w + wx * time * 0.15) % w;
    const y = (hash(i + 5) * h + time * 24) % h;
    const stack = document.elementsFromPoint((x + w) % w, (y + h) % h);
    const head = stack.find((node) => node instanceof HTMLElement && (node.tagName === "H1" || node.tagName === "H2"));
    if (head instanceof HTMLElement) head.classList.add("is-lit");
  }
};

const paint2d = (
  ctx: CanvasRenderingContext2D | null,
  count: number,
  w: number,
  h: number,
  time: number,
  wx: number,
  wy: number,
  mode: number,
  shock: number,
) => {
  if (!ctx) return;
  ctx.clearRect(0, 0, w, h);
  const n = Math.min(count, 420);
  for (let i = 0; i < n; i++) {
    const depth = hash(i + 3);
    const grav = mode === 1 ? -1 : 1;
    const speed = (18 + depth * 50) * (mode === 2 ? 0.25 : 1);
    let x = (hash(i + 1) * w + wx * time) % w;
    let y = (hash(i + 2) * h + grav * speed * time) % h;
    if (x < 0) x += w;
    if (y < 0) y += h;
    if (shock > 1) {
      const dx = x - w * 0.5;
      const dy = y - h * 0.46;
      const sd = Math.hypot(dx, dy) || 1;
      if (Math.abs(sd - shock) < 50) {
        x += (dx / sd) * 18;
        y += (dy / sd) * 18;
      }
    }
    const hand = w <= 840;
    const r = depth < 0.33 ? (hand ? 18 : 6) : depth < 0.66 ? (hand ? 3.4 : 2.6) : 1.3;
    const ash = depth < 0.33 ? 0.55 : 0.8;
    ctx.fillStyle = mode === 1 ? "rgba(255,120,40,0.8)" : mode === 2 ? `rgba(90,84,76,${ash})` : `rgba(243,238,227,${depth < 0.33 ? 0.45 : 0.85})`;
    ctx.beginPath();
    ctx.ellipse(x, y, r, r * (1 + Math.min(2, Math.abs(wx) / 200)), 0, 0, Math.PI * 2);
    ctx.fill();
  }
  void wy;
};

const buildGpu = (gl: WebGL2RenderingContext) => {
  const prog = program(gl, VERT, FRAG);
  const fog = program(gl, VVERT, VFRAG);
  if (!prog || !fog) return null;
  const quad = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, quad);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
    -0.5, -0.5, 0.5, -0.5, -0.5, 0.5,
    -0.5, 0.5, 0.5, -0.5, 0.5, 0.5,
  ]), gl.STATIC_DRAW);
  const seeds = new Float32Array(7000 * 4);
  for (let i = 0; i < 7000; i++) {
    seeds[i * 4] = hash(i + 1.3);
    seeds[i * 4 + 1] = hash(i + 8.2);
    seeds[i * 4 + 2] = hash(i + 4.7);
    seeds[i * 4 + 3] = hash(i + 9.1);
  }
  const seedBuf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, seedBuf);
  gl.bufferData(gl.ARRAY_BUFFER, seeds, gl.STATIC_DRAW);
  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);
  gl.bindBuffer(gl.ARRAY_BUFFER, quad);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
  gl.bindBuffer(gl.ARRAY_BUFFER, seedBuf);
  gl.enableVertexAttribArray(1);
  gl.vertexAttribPointer(1, 4, gl.FLOAT, false, 0, 0);
  gl.vertexAttribDivisor(1, 1);
  const fogBuf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, fogBuf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const fogVao = gl.createVertexArray();
  gl.bindVertexArray(fogVao);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
  gl.bindVertexArray(null);
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
  const loc = (name: string) => gl.getUniformLocation(prog, name);
  const u = {
    res: loc("uRes"),
    time: loc("uTime"),
    wind: loc("uWind"),
    gust: loc("uGust"),
    gustLife: loc("uGustLife"),
    shock: loc("uShock"),
    shockAt: loc("uShockAt"),
    mode: loc("uMode"),
    ring: loc("uRing"),
    tilt: loc("uTilt"),
    fmode: gl.getUniformLocation(prog, "uMode"),
  };
  const fogPressure = gl.getUniformLocation(fog, "uPressure");
  const fogRes = gl.getUniformLocation(fog, "uRes");
  return {
    draw(
      gl: WebGL2RenderingContext,
      canvas: HTMLCanvasElement,
      count: number,
      w: number,
      h: number,
      time: number,
      wx: number,
      wy: number,
      gx: number,
      gy: number,
      glife: number,
      shock: number,
      mode: number,
      ringR: number,
      pressure: number,
    ) {
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.useProgram(prog);
      gl.bindVertexArray(vao);
      const dpr = canvas.width / Math.max(1, w);
      gl.uniform2f(u.res, w, h);
      gl.uniform1f(u.time, time);
      gl.uniform2f(u.wind, wx, wy);
      gl.uniform2f(u.gust, gx, gy);
      gl.uniform1f(u.gustLife, glife);
      gl.uniform1f(u.shock, shock);
      gl.uniform2f(u.shockAt, w * 0.5, h * 0.46);
      gl.uniform1f(u.mode, mode);
      gl.uniform3f(u.ring, w * 0.5, h * 0.48, ringR);
      gl.uniform2f(u.tilt, tiltX * 30, tiltY * 10);
      gl.uniform1f(u.fmode, mode);
      gl.drawArraysInstanced(gl.TRIANGLES, 0, 6, count);
      if (pressure > 0.04) {
        gl.useProgram(fog);
        gl.bindVertexArray(fogVao);
        gl.uniform2f(fogRes, canvas.width, canvas.height);
        gl.uniform1f(fogPressure, pressure);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      }
      gl.bindVertexArray(null);
      void dpr;
    },
  };
};

const program = (gl: WebGL2RenderingContext, vs: string, fs: string) => {
  const v = shader(gl, gl.VERTEX_SHADER, vs);
  const f = shader(gl, gl.FRAGMENT_SHADER, fs);
  if (!v || !f) return null;
  const p = gl.createProgram();
  if (!p) return null;
  gl.attachShader(p, v);
  gl.attachShader(p, f);
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) {
    console.warn(gl.getProgramInfoLog(p));
    return null;
  }
  return p;
};

const shader = (gl: WebGL2RenderingContext, type: number, src: string) => {
  const s = gl.createShader(type);
  if (!s) return null;
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    console.warn(gl.getShaderInfoLog(s));
    gl.deleteShader(s);
    return null;
  }
  return s;
};
