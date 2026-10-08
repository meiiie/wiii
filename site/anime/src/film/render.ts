import { DEPTH_BAKE_FS, FULLSCREEN_VS, PLATE_FS, POST_FS, SNOW_FS, SNOW_VS, SPRITE_FS, SPRITE_VS } from "./shaders";
import type { Cam } from "./plates";

export type Grade = { lift: [number, number, number]; gain: [number, number, number]; gamma: number; sat: number };

export type SceneDraw = {
  plate: WebGLTexture;
  depth: WebGLTexture;
  cam: Cam;
  crop: { origin: [number, number]; window: [number, number] };
  rig: [number, number];
  shake: [number, number];
  fog: [number, number, number];
  fogAmt: number;
  dof: boolean;
  wiii: { tex: WebGLTexture | null; alpha: number; pos: [number, number]; size: [number, number]; depth: number };
  drift: { tex: WebGLTexture | null; alpha: number; pos: [number, number]; size: [number, number]; depth: number };
  snow: { count: number; mode: number; wind: [number, number]; pressure: number; fall: number; ring: number };
};

type Target = { fbo: WebGLFramebuffer; color: WebGLTexture; depth: WebGLTexture; w: number; h: number };

const compile = (gl: WebGL2RenderingContext, type: number, source: string) => {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("shader");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(shader) || "compile";
    gl.deleteShader(shader);
    throw new Error(log);
  }
  return shader;
};

const program = (gl: WebGL2RenderingContext, vs: string, fs: string) => {
  const p = gl.createProgram();
  if (!p) throw new Error("program");
  gl.attachShader(p, compile(gl, gl.VERTEX_SHADER, vs));
  gl.attachShader(p, compile(gl, gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p) || "link");
  return p;
};

const loc = (gl: WebGL2RenderingContext, p: WebGLProgram, name: string) => gl.getUniformLocation(p, name);

export class FilmRenderer {
  readonly gl: WebGL2RenderingContext;
  private plateProg: WebGLProgram;
  private spriteProg: WebGLProgram;
  private snowProg: WebGLProgram;
  private postProg: WebGLProgram;
  private bakeProg: WebGLProgram;
  private quad: WebGLVertexArrayObject;
  private spriteVao: WebGLVertexArrayObject;
  private snowVao: WebGLVertexArrayObject;
  private targets: Target[] = [];
  private cache = new Map<string, WebGLTexture>();
  private pending = new Set<string>();
  private alias = new Map<string, string>();
  private held = new Map<string, { plate: WebGLTexture; depth: WebGLTexture; aspect: number }>();
  private bakeFbo: WebGLFramebuffer | null = null;
  fboOk = false;
  dof = true;
  frameMs: number[] = [];
  readonly black: WebGLTexture;
  readonly grey: WebGLTexture;

  constructor(readonly canvas: HTMLCanvasElement) {
    const gl = canvas.getContext("webgl2", { alpha: false, antialias: false, depth: true, premultipliedAlpha: false });
    if (!gl) throw new Error("webgl2");
    this.gl = gl;
    this.plateProg = program(gl, FULLSCREEN_VS, PLATE_FS);
    this.spriteProg = program(gl, SPRITE_VS, SPRITE_FS);
    this.snowProg = program(gl, SNOW_VS, SNOW_FS);
    this.postProg = program(gl, FULLSCREEN_VS, POST_FS);
    this.bakeProg = program(gl, FULLSCREEN_VS, DEPTH_BAKE_FS);
    this.bakeFbo = gl.createFramebuffer();
    this.quad = this.buffer(new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]));
    this.spriteVao = this.buffer(new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]));
    const snow = gl.createVertexArray();
    if (!snow) throw new Error("vao");
    this.snowVao = snow;
    this.black = this.solid(11, 11, 13, 255);
    this.grey = this.solid(128, 128, 128, 255);
    this.resize(1);
  }

  private solid(r: number, g: number, b: number, a: number): WebGLTexture {
    const tex = this.blankTex();
    const gl = this.gl;
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([r, g, b, a]));
    return tex;
  }

  private buffer(data: Float32Array): WebGLVertexArrayObject {
    const gl = this.gl;
    const vao = gl.createVertexArray();
    const buf = gl.createBuffer();
    if (!vao || !buf) throw new Error("buffer");
    gl.bindVertexArray(vao);
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    gl.bindVertexArray(null);
    return vao;
  }

  resize(dpr: number): void {
    const w = Math.max(2, Math.floor(window.innerWidth * dpr));
    const h = Math.max(2, Math.floor(window.innerHeight * dpr));
    this.canvas.width = w;
    this.canvas.height = h;
    this.canvas.style.width = "100%";
    this.canvas.style.height = "100%";
    this.targets = [this.makeTarget(w, h), this.makeTarget(w, h)];
    this.gl.viewport(0, 0, w, h);
  }

  private makeTarget(w: number, h: number): Target {
    const gl = this.gl;
    const color = this.blankTex();
    const depth = this.blankTex();
    gl.bindTexture(gl.TEXTURE_2D, color);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.bindTexture(gl.TEXTURE_2D, depth);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    const rb = gl.createRenderbuffer();
    gl.bindRenderbuffer(gl.RENDERBUFFER, rb);
    gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH_COMPONENT16, w, h);
    const fbo = gl.createFramebuffer();
    if (!fbo || !rb) throw new Error("fbo");
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, color, 0);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT1, gl.TEXTURE_2D, depth, 0);
    gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.RENDERBUFFER, rb);
    gl.drawBuffers([gl.COLOR_ATTACHMENT0, gl.COLOR_ATTACHMENT1]);
    this.fboOk = gl.checkFramebufferStatus(gl.FRAMEBUFFER) === gl.FRAMEBUFFER_COMPLETE;
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    return { fbo, color, depth, w, h };
  }

  private blankTex(): WebGLTexture {
    const gl = this.gl;
    const tex = gl.createTexture();
    if (!tex) throw new Error("tex");
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return tex;
  }

  /** Decode `url`, then `fallback` if the first file is missing or not an image. Depth maps are dilated once. */
  requestImage(url: string, fallback: string, depth: boolean): void {
    const chosen = this.alias.get(url) ?? url;
    if (!chosen || this.cache.has(chosen) || this.pending.has(chosen)) return;
    this.pending.add(chosen);
    const img = new Image();
    img.decoding = "async";
    const fail = () => {
      this.pending.delete(chosen);
      if (fallback && chosen !== fallback && !this.alias.has(url)) {
        this.alias.set(url, fallback);
        this.requestImage(url, "", depth);
      }
    };
    img.onload = () => {
      this.pending.delete(chosen);
      if (!img.naturalWidth) {
        fail();
        return;
      }
      const tex = this.upload(img, depth);
      if (!tex) {
        fail();
        return;
      }
      this.cache.set(chosen, tex);
    };
    img.onerror = fail;
    img.src = chosen;
  }

  /**
   * Keep the last decoded pair for `slot` until the new plate and depth are both ready.
   * A resize or orientation change therefore does not flash empty.
   */
  retain(slot: string, plate: string, fallback: string, depth: string, aspect: number): { plate: WebGLTexture; depth: WebGLTexture; aspect: number } {
    this.requestImage(plate, fallback, false);
    this.requestImage(depth, "", true);
    const plateTex = this.cache.get(this.alias.get(plate) ?? plate);
    const depthTex = this.cache.get(depth);
    if (plateTex && depthTex) this.held.set(slot, { plate: plateTex, depth: depthTex, aspect });
    return this.held.get(slot) ?? { plate: this.black, depth: this.grey, aspect };
  }

  urls(): string[] {
    return [...this.cache.keys()];
  }

  image(url: string): WebGLTexture | null {
    this.requestImage(url, "", false);
    return this.cache.get(this.alias.get(url) ?? url) ?? null;
  }

  private upload(img: HTMLImageElement, depth: boolean): WebGLTexture | null {
    const gl = this.gl;
    const tex = this.blankTex();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, 1);
    while (gl.getError() !== gl.NO_ERROR) { /* drain */ }
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, 0);
    if (gl.getError() !== gl.NO_ERROR) {
      gl.deleteTexture(tex);
      return null;
    }
    if (!depth) return tex;
    const baked = this.bakeDepth(tex, img.naturalWidth, img.naturalHeight);
    if (baked && baked !== tex) gl.deleteTexture(tex);
    return baked ?? tex;
  }

  private alloc(w: number, h: number): WebGLTexture {
    const gl = this.gl;
    const tex = this.blankTex();
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    return tex;
  }

  private depthPass(source: WebGLTexture, dest: WebGLTexture, w: number, h: number, dir: [number, number], mode: number): void {
    const gl = this.gl;
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.bakeFbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, dest, 0);
    gl.drawBuffers([gl.COLOR_ATTACHMENT0]);
    gl.viewport(0, 0, w, h);
    gl.disable(gl.DEPTH_TEST);
    gl.disable(gl.BLEND);
    gl.useProgram(this.bakeProg);
    gl.bindVertexArray(this.quad);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, source);
    gl.uniform1i(loc(gl, this.bakeProg, "uRaw"), 0);
    gl.uniform2f(loc(gl, this.bakeProg, "uTexel"), 1 / w, 1 / h);
    gl.uniform2f(loc(gl, this.bakeProg, "uDir"), dir[0], dir[1]);
    gl.uniform1f(loc(gl, this.bakeProg, "uMode"), mode);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  private bakeDepth(source: WebGLTexture, w: number, h: number): WebGLTexture | null {
    if (!this.bakeFbo || w < 2 || h < 2) return source;
    const a = this.alloc(w, h);
    const b = this.alloc(w, h);
    this.depthPass(source, a, w, h, [1, 0], 0);
    this.depthPass(a, b, w, h, [0, 1], 0);
    this.depthPass(b, a, w, h, [1, 0], 1);
    this.depthPass(a, b, w, h, [0, 1], 1);
    const gl = this.gl;
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.deleteTexture(a);
    if (gl.getError() !== gl.NO_ERROR) {
      gl.deleteTexture(b);
      return source;
    }
    return b;
  }

  private bindScene(index: number): void {
    const gl = this.gl;
    const target = this.targets[index];
    gl.bindFramebuffer(gl.FRAMEBUFFER, target.fbo);
    gl.viewport(0, 0, target.w, target.h);
    gl.drawBuffers([gl.COLOR_ATTACHMENT0, gl.COLOR_ATTACHMENT1]);
    gl.enable(gl.DEPTH_TEST);
    gl.clearColor(0.04, 0.04, 0.05, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  }

  private drawPlate(scene: SceneDraw): void {
    const gl = this.gl;
    const p = this.plateProg;
    gl.useProgram(p);
    gl.disable(gl.BLEND);
    gl.bindVertexArray(this.quad);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, scene.plate);
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, scene.depth);
    gl.uniform1i(loc(gl, p, "uPlate"), 0);
    gl.uniform1i(loc(gl, p, "uDepth"), 1);
    gl.uniform2f(loc(gl, p, "uOrigin"), scene.crop.origin[0], scene.crop.origin[1]);
    gl.uniform2f(loc(gl, p, "uWindow"), scene.crop.window[0], scene.crop.window[1]);
    gl.uniform2f(loc(gl, p, "uCenter"), scene.cam.center[0], scene.cam.center[1]);
    gl.uniform1f(loc(gl, p, "uZoom"), scene.cam.zoom);
    gl.uniform1f(loc(gl, p, "uDolly"), scene.cam.dolly);
    gl.uniform2f(loc(gl, p, "uTruck"), scene.cam.truck[0], scene.cam.truck[1]);
    gl.uniform1f(loc(gl, p, "uRoll"), scene.cam.roll);
    gl.uniform1f(loc(gl, p, "uFocus"), scene.cam.focus);
    gl.uniform2f(loc(gl, p, "uShake"), scene.shake[0], scene.shake[1]);
    gl.uniform2f(loc(gl, p, "uRig"), scene.rig[0], scene.rig[1]);
    gl.uniform1f(loc(gl, p, "uDofOn"), scene.dof && this.dof ? 1 : 0);
    gl.uniform1f(loc(gl, p, "uFogAmt"), scene.fogAmt);
    gl.uniform3f(loc(gl, p, "uFog"), scene.fog[0], scene.fog[1], scene.fog[2]);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  private drawSprite(card: SceneDraw["wiii"], truck: [number, number], focus: number): void {
    if (!card.tex || card.alpha <= 0) return;
    const gl = this.gl;
    const p = this.spriteProg;
    gl.useProgram(p);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.bindVertexArray(this.spriteVao);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, card.tex);
    const parallaxX = truck[0] * (card.depth - focus) * 0.85;
    const parallaxY = truck[1] * (card.depth - focus) * 0.85;
    gl.uniform1i(loc(gl, p, "uSprite"), 0);
    gl.uniform2f(loc(gl, p, "uPos"), card.pos[0], card.pos[1]);
    gl.uniform2f(loc(gl, p, "uSize"), card.size[0], card.size[1]);
    gl.uniform2f(loc(gl, p, "uParallax"), parallaxX, parallaxY);
    gl.uniform1f(loc(gl, p, "uCard"), card.depth);
    gl.uniform1f(loc(gl, p, "uAlpha"), card.alpha);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  private drawSnow(scene: SceneDraw, now: number): void {
    const gl = this.gl;
    const p = this.snowProg;
    gl.useProgram(p);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.bindVertexArray(this.snowVao);
    gl.uniform1f(loc(gl, p, "uTime"), now);
    gl.uniform1f(loc(gl, p, "uCount"), scene.snow.count);
    gl.uniform2f(loc(gl, p, "uWind"), scene.snow.wind[0], scene.snow.wind[1]);
    gl.uniform1f(loc(gl, p, "uMode"), scene.snow.mode);
    gl.uniform1f(loc(gl, p, "uFall"), scene.snow.fall);
    gl.uniform1f(loc(gl, p, "uRing"), scene.snow.ring);
    gl.uniform1f(loc(gl, p, "uPressure"), scene.snow.pressure);
    gl.drawArrays(gl.POINTS, 0, Math.min(540, Math.ceil(scene.snow.count)));
  }

  paintScene(index: number, scene: SceneDraw, now: number): void {
    this.bindScene(index);
    this.drawPlate(scene);
    this.drawSnow(scene, now);
    this.drawSprite(scene.drift, scene.cam.truck, scene.cam.focus);
    this.drawSprite(scene.wiii, scene.cam.truck, scene.cam.focus);
  }

  present(grade: Grade, gate: number, kind: number, invert: number, smear: number, ca: number, now: number): void {
    const gl = this.gl;
    const [a, b] = this.targets;
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.disable(gl.DEPTH_TEST);
    gl.disable(gl.BLEND);
    const p = this.postProg;
    gl.useProgram(p);
    gl.bindVertexArray(this.quad);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, a.color);
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, b.color);
    gl.activeTexture(gl.TEXTURE2);
    gl.bindTexture(gl.TEXTURE_2D, a.depth);
    gl.uniform1i(loc(gl, p, "uA"), 0);
    gl.uniform1i(loc(gl, p, "uB"), 1);
    gl.uniform1i(loc(gl, p, "uDepthA"), 2);
    gl.uniform1f(loc(gl, p, "uGate"), gate);
    gl.uniform1f(loc(gl, p, "uKind"), kind);
    gl.uniform1f(loc(gl, p, "uInvert"), invert);
    gl.uniform1f(loc(gl, p, "uSmear"), smear);
    gl.uniform1f(loc(gl, p, "uCA"), ca);
    gl.uniform1f(loc(gl, p, "uTime"), now);
    gl.uniform1f(loc(gl, p, "uSat"), grade.sat);
    gl.uniform3f(loc(gl, p, "uLift"), grade.lift[0], grade.lift[1], grade.lift[2]);
    gl.uniform3f(loc(gl, p, "uGain"), grade.gain[0], grade.gain[1], grade.gain[2]);
    gl.uniform1f(loc(gl, p, "uGamma"), grade.gamma);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }
}
