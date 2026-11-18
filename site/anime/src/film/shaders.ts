export const FULLSCREEN_VS = `#version 300 es
layout(location=0) in vec2 aPos;
out vec2 vUv;
void main() {
  vUv = aPos * 0.5 + 0.5;
  gl_Position = vec4(aPos, 0.0, 1.0);
}`;

export const PLATE_FS = `#version 300 es
precision highp float;
in vec2 vUv;
layout(location=0) out vec4 frag;
layout(location=1) out vec4 depthOut;
uniform sampler2D uPlate;
uniform sampler2D uDepth;
uniform vec2 uOrigin;
uniform vec2 uWindow;
uniform vec2 uCenter;
uniform float uZoom;
uniform float uDolly;
uniform vec2 uTruck;
uniform float uRoll;
uniform float uFocus;
uniform vec2 uShake;
uniform vec2 uRig;
uniform float uDofOn;
uniform float uFogAmt;
uniform vec3 uFog;

vec2 mirror(vec2 p) {
  vec2 q = abs(p);
  vec2 ip = floor(q);
  vec2 f = fract(q);
  vec2 odd = mod(ip, 2.0);
  return mix(f, 1.0 - f, step(0.5, odd));
}
vec2 toTex(vec2 imageUv) { return vec2(imageUv.x, 1.0 - imageUv.y); }
float depthAt(vec2 imageUv) { return texture(uDepth, toTex(mirror(imageUv))).r; }
vec2 cam(vec2 screenUv) {
  vec2 base = uOrigin + screenUv * uWindow;
  float cs = cos(uRoll), sn = sin(uRoll);
  vec2 rel = base - uCenter;
  rel = vec2(cs * rel.x - sn * rel.y, sn * rel.x + cs * rel.y);
  base = uCenter + rel + uRig + uShake;
  vec2 guess = base;
  for (int i = 0; i < 3; i++) {
    float d = depthAt(guess);
    float s = max(0.42, uZoom * (1.0 + uDolly * (d - uFocus)));
    guess = uCenter + (base - uCenter) / s - uTruck * (d - uFocus);
  }
  return guess;
}
void main() {
  vec2 screenUv = vec2(vUv.x, 1.0 - vUv.y);
  vec2 guess = cam(screenUv);
  vec2 st = toTex(mirror(guess));
  float d0 = texture(uDepth, st).r;
  vec3 col = texture(uPlate, st).rgb;
  float coc = abs(d0 - uFocus);
  if (uDofOn > 0.5 && coc > 0.04) {
    vec3 acc = col;
    float w = 1.0;
    for (int i = 0; i < 8; i++) {
      float a = float(i) * 6.2831853 / 8.0;
      vec2 o = vec2(cos(a), sin(a)) * coc * 0.018;
      acc += texture(uPlate, toTex(mirror(guess + o))).rgb;
      w += 1.0;
    }
    if (coc > 0.18) {
      for (int i = 0; i < 4; i++) {
        float a = float(i) * 6.2831853 / 4.0 + 0.4;
        vec2 o = vec2(cos(a), sin(a)) * coc * 0.032;
        acc += texture(uPlate, toTex(mirror(guess + o))).rgb;
        w += 1.0;
      }
    }
    col = acc / w;
  }
  col = mix(col, uFog, smoothstep(0.2, 0.9, 1.0 - d0) * uFogAmt);
  frag = vec4(col, 1.0);
  depthOut = vec4(d0, d0, d0, 1.0);
  gl_FragDepth = clamp(1.0 - d0, 0.02, 0.98);
}`;

export const SPRITE_VS = `#version 300 es
layout(location=0) in vec2 aCorner;
uniform vec2 uPos;
uniform vec2 uSize;
uniform vec2 uParallax;
out vec2 vUv;
void main() {
  vec2 screen = uPos + (aCorner - 0.5) * uSize + uParallax;
  vec2 clip = vec2(screen.x * 2.0 - 1.0, 1.0 - screen.y * 2.0);
  vUv = vec2(aCorner.x, 1.0 - aCorner.y);
  gl_Position = vec4(clip, 0.0, 1.0);
}`;

export const SPRITE_FS = `#version 300 es
precision highp float;
in vec2 vUv;
layout(location=0) out vec4 frag;
layout(location=1) out vec4 depthOut;
uniform sampler2D uSprite;
uniform float uCard;
uniform float uAlpha;
void main() {
  vec4 s = texture(uSprite, vUv);
  if (s.a < 0.04 || uAlpha < 0.01) discard;
  frag = vec4(s.rgb, s.a * uAlpha);
  depthOut = vec4(uCard);
  gl_FragDepth = clamp(1.0 - uCard, 0.02, 0.98);
}`;

export const SNOW_VS = `#version 300 es
uniform float uTime;
uniform float uCount;
uniform vec2 uWind;
uniform float uMode;
uniform float uFall;
uniform float uRing;
out float vBand;
out float vSeed;
out float vCalm;
void main() {
  float id = float(gl_VertexID);
  float band = mod(id, 3.0);
  float seed = fract(sin(id * 12.9898) * 43758.5453);
  float speed = (0.07 + band * 0.08 + seed * 0.05) * max(uFall, 0.05);
  float grav = (uMode > 0.5 && uMode < 1.5) ? -1.0 : 1.0;
  float y = fract(seed * 3.1 + uTime * speed * grav + uWind.y * uTime * 0.03);
  float x = fract(seed * 1.7 + sin(uTime * 0.35 + id) * 0.012 + uWind.x * uTime * (0.04 + band * 0.03));
  float calm = 0.0;
  if (uRing > 0.5) {
    float bowl = fract(seed * 2.3);
    if (bowl < 0.42) {
      float ang = seed * 6.2831853;
      float rad = 0.04 + fract(seed * 5.1) * 0.13;
      x = 0.5 + cos(ang) * rad * 0.62;
      y = fract(0.5 + sin(ang) * rad * 0.4 + uTime * speed * 0.2);
      calm = 1.0;
    } else {
      float dir = uWind.x >= 0.0 ? 1.0 : -1.0;
      x = fract(seed * 1.7 + uTime * (0.16 + band * 0.07) * dir);
      y = fract(seed * 3.1 + uTime * speed * 1.35);
    }
  }
  vCalm = calm;
  if (id > uCount) {
    gl_Position = vec4(2.0, 2.0, 0.0, 1.0);
    gl_PointSize = 1.0;
    vBand = band;
    vSeed = seed;
    return;
  }
  gl_Position = vec4(x * 2.0 - 1.0, 1.0 - y * 2.0, 0.0, 1.0);
  gl_PointSize = (calm > 0.5 ? 1.5 : (uMode > 1.5 ? 1.7 : 2.2)) + band * 1.4 + seed;
  vBand = band;
  vSeed = seed;
}`;

export const SNOW_FS = `#version 300 es
precision highp float;
in float vBand;
in float vSeed;
in float vCalm;
layout(location=0) out vec4 frag;
layout(location=1) out vec4 depthOut;
uniform float uMode;
uniform float uPressure;
void main() {
  vec2 p = gl_PointCoord - 0.5;
  if (dot(p, p) > 0.22) discard;
  float card = vBand < 0.5 ? 0.28 : (vBand < 1.5 ? 0.7 : 0.96);
  vec3 col = uMode > 0.5 && uMode < 1.5
    ? mix(vec3(0.78, 0.06, 0.04), vec3(0.92, 0.14, 0.08), vSeed)
    : vec3(0.9, 0.9, 0.9);
  float alpha = (0.35 + uPressure * 0.4) * (0.45 + vSeed * 0.55);
  if (uMode > 1.5) alpha *= 0.55;
  if (vCalm > 0.5) alpha *= 0.45;
  frag = vec4(col, alpha);
  depthOut = vec4(card);
  gl_FragDepth = clamp(1.0 - card, 0.02, 0.98);
}`;

export const DEPTH_BAKE_FS = `#version 300 es
precision highp float;
uniform sampler2D uRaw;
uniform vec2 uTexel;
uniform vec2 uDir;
uniform float uMode;
in vec2 vUv;
out vec4 frag;
void main() {
  if (uMode < 0.5) {
    float d = texture(uRaw, vUv).r;
    for (int i = 1; i <= 4; i++) {
      vec2 o = uDir * uTexel * float(i);
      d = max(d, texture(uRaw, vUv + o).r);
      d = max(d, texture(uRaw, vUv - o).r);
    }
    frag = vec4(d, d, d, 1.0);
  } else {
    float d = texture(uRaw, vUv).r * 0.227027;
    d += (texture(uRaw, vUv + uDir * uTexel).r + texture(uRaw, vUv - uDir * uTexel).r) * 0.1945946;
    d += (texture(uRaw, vUv + uDir * uTexel * 2.0).r + texture(uRaw, vUv - uDir * uTexel * 2.0).r) * 0.1216216;
    frag = vec4(d, d, d, 1.0);
  }
}`;

export const POST_FS = `#version 300 es
precision highp float;
in vec2 vUv;
out vec4 frag;
uniform sampler2D uA;
uniform sampler2D uB;
uniform sampler2D uDepthA;
uniform float uGate;
uniform float uKind;
uniform float uInvert;
uniform float uSmear;
uniform float uCA;
uniform float uTime;
uniform float uSat;
uniform vec3 uLift;
uniform vec3 uGain;
uniform float uGamma;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float a = hash(i);
  float b = hash(i + vec2(1.0, 0.0));
  float c = hash(i + vec2(0.0, 1.0));
  float d = hash(i + vec2(1.0, 1.0));
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 4; i++) {
    v += a * noise(p);
    p *= 2.02;
    a *= 0.5;
  }
  return v;
}
vec3 sampleCA(sampler2D tex, vec2 uv, float ca) {
  vec2 dir = normalize(uv - 0.5 + vec2(0.0001)) * ca;
  return vec3(texture(tex, uv + dir).r, texture(tex, uv).g, texture(tex, uv - dir).b);
}
vec3 smear(sampler2D tex, vec2 uv, float amt) {
  vec2 dir = normalize(uv - 0.5 + vec2(0.0001));
  vec3 acc = vec3(0.0);
  for (int i = 0; i < 8; i++) {
    acc += texture(tex, uv + dir * (float(i) / 7.0) * amt * 0.09).rgb;
  }
  return acc / 8.0;
}
vec3 shattered(vec2 uv, float t) {
  vec2 g = uv * vec2(7.0, 5.0);
  vec2 cell = floor(g);
  vec2 f = fract(g);
  float md = 8.0;
  vec2 delta = vec2(0.0);
  for (int y = -1; y <= 1; y++) {
    for (int x = -1; x <= 1; x++) {
      vec2 nb = cell + vec2(float(x), float(y));
      vec2 rnd = vec2(hash(nb), hash(nb + 3.1));
      vec2 c = vec2(float(x), float(y)) + rnd;
      float d = length(c - f);
      if (d < md) { md = d; delta = rnd - 0.5; }
    }
  }
  float far = 1.0 - texture(uDepthA, uv).r;
  vec2 uv2 = clamp(uv + delta * t * (0.08 + far * 0.14), 0.0, 1.0);
  vec3 shard = texture(uA, uv2).rgb;
  float crack = smoothstep(0.07, 0.0, md);
  vec3 next = texture(uB, uv).rgb;
  vec3 col = mix(shard, next, smoothstep(0.45, 1.0, t));
  return col + crack * t * vec3(0.92, 0.9, 0.84) * 0.4;
}
void main() {
  vec2 uv = vUv;
  vec3 a = sampleCA(uA, uv, uCA);
  vec3 b = texture(uB, uv).rgb;
  vec3 col = a;
  if (uSmear > 0.001) col = mix(a, smear(uA, uv, uSmear), clamp(uSmear, 0.0, 1.0));
  if (uKind > 0.5 && uKind < 1.5) {
    float n = fbm(uv * 3.4 + uTime * 0.04);
    float far = 1.0 - texture(uDepthA, uv).r;
    float edge = uGate * 1.35 - mix(n, far, 0.5);
    float m = smoothstep(0.0, 0.08, edge);
    float rim = exp(-pow(edge / 0.035, 2.0));
    vec3 ember = mix(vec3(0.04, 0.015, 0.02), vec3(0.92, 0.24, 0.1), rim);
    col = mix(col, b, m) + ember * rim * 0.9;
  } else if (uKind > 1.5 && uKind < 2.5) {
    vec3 lines = smear(uA, uv, max(uSmear, uGate));
    col = mix(lines, b, smoothstep(0.35, 1.0, uGate));
  } else if (uKind > 2.5) {
    col = shattered(uv, uGate);
  }
  if (uInvert > 0.5) col = vec3(1.0) - col;
  float l = dot(col, vec3(0.299, 0.587, 0.114));
  col = mix(vec3(l), col, uSat);
  col = pow(max(col, vec3(0.0)), vec3(max(0.2, uGamma))) * uGain + uLift;
  float vig = smoothstep(0.55, 0.98, length(uv - 0.5));
  col *= mix(1.0, 0.9, vig);
  float grain = hash(uv * (80.0 + fract(uTime * 13.0) * 40.0) + uTime);
  col += (grain - 0.5) * 0.018;
  frag = vec4(clamp(col, 0.0, 1.0), 1.0);
}`;
