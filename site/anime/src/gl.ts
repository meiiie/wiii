const VERT = `
attribute vec2 aPos;
void main() { gl_Position = vec4(aPos, 0.0, 1.0); }
`;

const FRAG = `
precision highp float;
uniform vec2 uRes;
uniform float uTime;
uniform float uScroll;
uniform float uVel;
uniform float uImpact;
uniform vec2 uSpark;
uniform float uStill;

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 345.45));
  p += dot(p, p + 34.345);
  return fract(p.x * p.y);
}
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  float a = hash(i);
  float b = hash(i + vec2(1.0, 0.0));
  float c = hash(i + vec2(0.0, 1.0));
  float d = hash(i + vec2(1.0, 1.0));
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p *= 2.03;
    a *= 0.5;
  }
  return v;
}

void main() {
  vec2 uv = gl_FragCoord.xy / uRes.xy;
  vec2 p = uv * vec2(uRes.x / uRes.y, 1.0) * 1.6;
  float t = uTime * (0.035 + uVel * 0.08);
  p += vec2(uScroll * 0.8, uScroll * -0.35);
  vec2 q = vec2(fbm(p + t), fbm(p + vec2(5.2, 1.3) - t));
  vec2 r = vec2(
    fbm(p + 1.8 * q + vec2(1.7, 9.2) + uScroll),
    fbm(p + 1.8 * q + vec2(8.3, 2.8) - uVel)
  );
  float f = fbm(p + 2.2 * r);
  vec3 ink = vec3(0.028, 0.032, 0.045);
  vec3 smoke = vec3(0.09, 0.105, 0.135);
  vec3 sky = vec3(0.733, 0.867, 0.949);
  vec3 col = mix(ink, smoke, smoothstep(0.25, 0.85, f));
  col = mix(col, sky, smoothstep(0.62, 1.0, f) * 0.28);
  float d = distance(uv, uSpark);
  col += vec3(0.97, 0.94, 0.89) * exp(-d * d * 220.0);
  col += sky * exp(-d * d * 48.0) * 0.55;
  col = mix(col, vec3(0.42, 0.02, 0.015), uImpact * 0.55 * (0.35 + 0.65 * f));
  float vig = smoothstep(1.15, 0.35, length((uv - 0.5) * vec2(1.15, 1.0)));
  col *= vig;
  col = mix(col, vec3(dot(col, vec3(0.3, 0.5, 0.2))), uStill * 0.65);
  gl_FragColor = vec4(col, 1.0);
}
`;

export type InkUniforms = {
  time: number;
  scroll: number;
  vel: number;
  impact: number;
  sparkX: number;
  sparkY: number;
  still: number;
};

export class InkField {
  private gl: WebGLRenderingContext | null = null;
  private program: WebGLProgram | null = null;
  private loc: Record<string, WebGLUniformLocation | null> = {};
  private dpr = 1;

  constructor(private canvas: HTMLCanvasElement) {}

  mount(): boolean {
    const gl = this.canvas.getContext("webgl", {
      alpha: false,
      antialias: false,
      depth: false,
      stencil: false,
      powerPreference: "low-power",
    });
    if (!gl) return false;
    this.gl = gl;
    const vs = this.shader(gl.VERTEX_SHADER, VERT);
    const fs = this.shader(gl.FRAGMENT_SHADER, FRAG);
    if (!vs || !fs) return false;
    const program = gl.createProgram();
    if (!program) return false;
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.bindAttribLocation(program, 0, "aPos");
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return false;
    this.program = program;
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    for (const name of ["uRes", "uTime", "uScroll", "uVel", "uImpact", "uSpark", "uStill"]) {
      this.loc[name] = gl.getUniformLocation(program, name);
    }
    this.resize();
    return true;
  }

  resize(): void {
    const gl = this.gl;
    if (!gl) return;
    const mobile = window.innerWidth < 800;
    this.dpr = Math.min(window.devicePixelRatio || 1, mobile ? 1 : 1.15);
    const w = Math.max(2, Math.floor(window.innerWidth * this.dpr));
    const h = Math.max(2, Math.floor(window.innerHeight * this.dpr));
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
    }
    gl.viewport(0, 0, w, h);
  }

  draw(u: InkUniforms): void {
    const gl = this.gl;
    const program = this.program;
    if (!gl || !program) return;
    gl.useProgram(program);
    gl.uniform2f(this.loc.uRes, this.canvas.width, this.canvas.height);
    gl.uniform1f(this.loc.uTime, u.time);
    gl.uniform1f(this.loc.uScroll, u.scroll);
    gl.uniform1f(this.loc.uVel, u.vel);
    gl.uniform1f(this.loc.uImpact, u.impact);
    gl.uniform2f(this.loc.uSpark, u.sparkX, 1 - u.sparkY);
    gl.uniform1f(this.loc.uStill, u.still);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  private shader(type: number, source: string): WebGLShader | null {
    const gl = this.gl;
    if (!gl) return null;
    const shader = gl.createShader(type);
    if (!shader) return null;
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      gl.deleteShader(shader);
      return null;
    }
    return shader;
  }
}
