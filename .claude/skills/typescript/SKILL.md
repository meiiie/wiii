# TypeScript Strict Mode Skill

## Description
TypeScript best practices with strict mode enabled for type-safe development.

## Configuration
```json
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noImplicitReturns": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  }
}
```

## Type Patterns

### Interface vs Type
```typescript
// Use interface for objects that can be extended
interface User {
  id: string;
  name: string;
}

interface AdminUser extends User {
  permissions: string[];
}

// Use type for unions, intersections, primitives
type Status = 'pending' | 'completed' | 'failed';
type Nullable<T> = T | null;
type APIResponse<T> = { data: T; error: null } | { data: null; error: string };
```

### Generic Types
```typescript
// Generic function
function getFirst<T>(arr: T[]): T | undefined {
  return arr[0];
}

// Generic interface
interface Repository<T> {
  findById(id: string): Promise<T | null>;
  save(item: T): Promise<T>;
  delete(id: string): Promise<void>;
}

// Constrained generic
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key];
}
```

### Utility Types
```typescript
// Partial - all properties optional
type PartialUser = Partial<User>;

// Required - all properties required
type RequiredConfig = Required<Config>;

// Pick - select specific properties
type UserPreview = Pick<User, 'id' | 'name'>;

// Omit - exclude properties
type UserWithoutId = Omit<User, 'id'>;

// Record - object with specific key/value types
type UserMap = Record<string, User>;

// ReturnType - extract function return type
type ChatResult = ReturnType<typeof sendChatMessage>;

// Parameters - extract function parameters
type ChatParams = Parameters<typeof sendChatMessage>;
```

### Discriminated Unions
```typescript
type Message =
  | { type: 'text'; content: string }
  | { type: 'image'; url: string; alt: string }
  | { type: 'file'; filename: string; size: number };

function renderMessage(msg: Message) {
  switch (msg.type) {
    case 'text':
      return <p>{msg.content}</p>;
    case 'image':
      return <img src={msg.url} alt={msg.alt} />;
    case 'file':
      return <a download>{msg.filename}</a>;
  }
}
```

### Type Guards
```typescript
// Type predicate
function isError(result: unknown): result is Error {
  return result instanceof Error;
}

// in operator narrowing
function processResponse(res: SuccessResponse | ErrorResponse) {
  if ('error' in res) {
    console.error(res.error);
    return;
  }
  console.log(res.data);
}

// Assertion function
function assertNonNull<T>(value: T | null | undefined): asserts value is T {
  if (value == null) {
    throw new Error('Value is null or undefined');
  }
}
```

### API Types
```typescript
// Request/Response types
interface ChatRequest {
  message: string;
  history?: ChatMessage[];
}

interface ChatResponse {
  answer: string;
  sources: Source[];
}

interface Source {
  document_number: string;
  title: string;
  article?: string;
  url: string;
}

// API function with proper types
async function sendChat(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }

  return response.json() as Promise<ChatResponse>;
}
```

## Anti-Patterns to Avoid

```typescript
// ❌ Don't use any
const data: any = fetchData();

// ✅ Use unknown and narrow
const data: unknown = fetchData();
if (isValidData(data)) {
  // data is now typed
}

// ❌ Don't use non-null assertion carelessly
const name = user!.name;

// ✅ Use optional chaining or guard
const name = user?.name ?? 'Anonymous';

// ❌ Don't use type assertion to lie
const user = {} as User;

// ✅ Properly construct objects
const user: User = { id: '1', name: 'John' };
```

## Naming Conventions
- Interfaces/Types: `PascalCase`
- Type parameters: Single uppercase (`T`, `K`, `V`) or descriptive (`TData`, `TError`)
- Constants: `SCREAMING_SNAKE_CASE` or `camelCase`
- Functions/variables: `camelCase`
