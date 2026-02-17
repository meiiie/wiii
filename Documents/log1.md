Failed to load resource: the server responded with a status of 403 ()Understand this error
installHook.js:1 Server Error: 403 - Http failure response for http://localhost:8088/api/v1/auth/login: 403 
overrideMethod @ installHook.js:1Understand this error
installHook.js:1 API Error: _HttpErrorResponse
overrideMethod @ installHook.js:1Understand this error
auth.interceptor.ts:86 🔗 AuthInterceptor: Error response status: N/A (Network/CORS error)
installHook.js:1 ❌ Login failed: Error: Server Error: 403 - Http failure response for http://localhost:8088/api/v1/auth/login: 403 
    at error.interceptor.ts:64:31
    at Observable.init [as _subscribe] (throwError.js:5:64)
    at Observable2._trySubscribe (Observable.js:38:25)
    at Observable.js:32:31
    at errorContext (errorContext.js:19:9)
    at Observable2.subscribe (Observable.js:23:9)
    at catchError.js:14:31
    at OperatorSubscriber2._this._error (OperatorSubscriber.js:25:21)
    at Subscriber2.error (Subscriber.js:43:18)
    at FetchBackend.doRequest (module.mjs:1910:16)
overrideMethod @ installHook.js:1Understand this error
installHook.js:1 ❌ Error status: undefined
overrideMethod @ installHook.js:1Understand this error
installHook.js:1 ❌ Error message: Server Error: 403 - Http failure response for http://localhost:8088/api/v1/auth/login: 403 
overrideMethod @ installHook.js:1Understand this error
installHook.js:1 ❌ Login failed in component: Error: Server Error: 403 - Http failure response for http://localhost:8088/api/v1/auth/login: 403 
    at error.interceptor.ts:64:31
    at Observable.init [as _subscribe] (throwError.js:5:64)
    at Observable2._trySubscribe (Observable.js:38:25)
    at Observable.js:32:31
    at errorContext (errorContext.js:19:9)
    at Observable2.subscribe (Observable.js:23:9)
    at catchError.js:14:31
    at OperatorSubscriber2._this._error (OperatorSubscriber.js:25:21)
    at Subscriber2.error (Subscriber.js:43:18)
    at FetchBackend.doRequest (module.mjs:1910:16)