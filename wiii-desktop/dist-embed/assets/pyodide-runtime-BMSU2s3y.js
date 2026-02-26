var y=Object.defineProperty;var g=(r,e,t)=>e in r?y(r,e,{enumerable:!0,configurable:!0,writable:!0,value:t}):r[e]=t;var n=(r,e,t)=>g(r,typeof e!="symbol"?e+"":e,t);const u="https://cdn.jsdelivr.net/pyodide/v0.27.0/full";class h{constructor(){n(this,"worker",null);n(this,"ready",!1);n(this,"initializing",!1);n(this,"pendingResolve",null);n(this,"pendingReject",null);n(this,"onStatus")}async initialize(e){if(!this.ready){if(this.initializing)return new Promise(t=>{const i=setInterval(()=>{this.ready&&(clearInterval(i),t())},100)});if(typeof navigator<"u"&&!navigator.onLine)throw new Error("Không có kết nối mạng. Pyodide cần tải từ CDN.");return this.initializing=!0,this.onStatus=e,new Promise((t,i)=>{const o=setTimeout(()=>{this.initializing=!1,this.worker?.terminate(),this.worker=null,i(new Error("Tải Pyodide quá lâu (>30s). Kiểm tra kết nối mạng."))},3e4);try{const l=`
          let pyodide = null;

          async function initPyodide() {
            importScripts("${u}/pyodide.js");
            pyodide = await loadPyodide({
              indexURL: "${u}/",
            });
            // Pre-install common packages
            await pyodide.loadPackagesFromImports("import micropip");
            const micropip = pyodide.pyimport("micropip");
            await micropip.install(["numpy", "pandas"]);
            // Note: matplotlib installed on-demand in execute
            postMessage({ type: "ready" });
          }

          async function execute(code) {
            const start = performance.now();
            const stdout = [];
            const stderr = [];
            const images = [];

            // Redirect stdout/stderr
            pyodide.runPython(\`
import sys
from io import StringIO
_stdout = StringIO()
_stderr = StringIO()
sys.stdout = _stdout
sys.stderr = _stderr
\`);

            let exitCode = 0;
            try {
              // Check if matplotlib is needed
              if (code.includes("matplotlib") || code.includes("plt.")) {
                try {
                  await pyodide.loadPackagesFromImports("import matplotlib");
                  pyodide.runPython(\`
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
\`);
                } catch(e) {
                  // matplotlib load error — continue without it
                }
              }

              await pyodide.runPythonAsync(code);

              // Capture matplotlib figures
              try {
                const figCount = pyodide.runPython(\`
import matplotlib.pyplot as plt
len(plt.get_fignums())
\`);
                if (figCount > 0) {
                  const b64 = pyodide.runPython(\`
import io, base64
buf = io.BytesIO()
plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
plt.close('all')
buf.seek(0)
base64.b64encode(buf.read()).decode('utf-8')
\`);
                  images.push(b64);
                }
              } catch(e) {
                // No matplotlib — skip
              }
            } catch(err) {
              exitCode = 1;
              stderr.push(String(err));
            }

            // Capture stdout/stderr
            const out = pyodide.runPython("_stdout.getvalue()");
            const err = pyodide.runPython("_stderr.getvalue()");
            if (out) stdout.push(out);
            if (err) stderr.push(err);

            // Restore streams
            pyodide.runPython(\`
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__
\`);

            const executionTime = Math.round(performance.now() - start);

            return {
              stdout: stdout.join("\\n"),
              stderr: stderr.join("\\n"),
              exitCode,
              images,
              tables: [],
              executionTime,
            };
          }

          self.onmessage = async function(e) {
            const { type, payload } = e.data;
            if (type === "init") {
              try {
                postMessage({ type: "status", payload: "Đang tải Pyodide..." });
                await initPyodide();
              } catch(err) {
                postMessage({ type: "error", payload: String(err) });
              }
            } else if (type === "execute") {
              try {
                postMessage({ type: "status", payload: "Đang chạy Python..." });
                const result = await execute(payload);
                postMessage({ type: "result", payload: result });
              } catch(err) {
                postMessage({ type: "error", payload: String(err) });
              }
            }
          };
        `,d=new Blob([l],{type:"application/javascript"}),a=URL.createObjectURL(d);this.worker=new Worker(a),URL.revokeObjectURL(a),this.worker.onmessage=p=>{const s=p.data;s.type==="ready"?(clearTimeout(o),this.ready=!0,this.initializing=!1,t()):s.type==="result"?(this.pendingResolve?.(s.payload),this.pendingResolve=null,this.pendingReject=null):s.type==="error"?(this.initializing&&(clearTimeout(o),this.initializing=!1,i(new Error(s.payload))),this.pendingReject?.(new Error(s.payload)),this.pendingResolve=null,this.pendingReject=null):s.type==="status"&&this.onStatus?.(s.payload)},this.worker.onerror=p=>{clearTimeout(o),this.initializing=!1,i(new Error(`Worker error: ${p.message}`))},this.worker.postMessage({type:"init"})}catch(l){clearTimeout(o),this.initializing=!1,i(l)}})}}async execute(e){return(!this.ready||!this.worker)&&await this.initialize(),this.pendingReject&&(this.pendingReject(new Error("Cancelled: new execution started")),this.pendingResolve=null,this.pendingReject=null),new Promise((t,i)=>{this.pendingResolve=t,this.pendingReject=i;const o=setTimeout(()=>{this.pendingReject?.(new Error("Execution timeout (60s)")),this.pendingResolve=null,this.pendingReject=null},6e4),l=this.pendingResolve;this.pendingResolve=a=>{clearTimeout(o),l(a)};const d=this.pendingReject;this.pendingReject=a=>{clearTimeout(o),d(a)},this.worker.postMessage({type:"execute",payload:e})})}destroy(){this.worker?.terminate(),this.worker=null,this.ready=!1,this.initializing=!1}}let c=null;function f(){return c||(c=new h),c}export{h as PyodideRuntime,f as getPyodideRuntime};
