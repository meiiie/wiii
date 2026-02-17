# React 18 Development Skill

## Description
React 18 patterns for building modern UI components with TypeScript, hooks, and best practices.

## Project Structure
```
src/
├── components/
│   ├── layout/          # App shell, sidebar, header
│   ├── chat/            # Chat-related components
│   ├── search/          # Search UI
│   ├── common/          # Shared components
│   └── index.ts         # Barrel exports
├── hooks/               # Custom React hooks
├── services/            # API clients
├── stores/              # Zustand stores
├── types/               # TypeScript types
├── utils/               # Helper functions
├── App.tsx
└── main.tsx
```

## Component Patterns

### Functional Component
```tsx
interface ChatMessageProps {
  message: Message;
  isUser: boolean;
  onRetry?: () => void;
}

export function ChatMessage({ message, isUser, onRetry }: ChatMessageProps) {
  const formattedTime = useFormattedTime(message.timestamp);

  return (
    <div className={cn(
      "p-4 rounded-lg",
      isUser ? "bg-blue-50 ml-auto" : "bg-gray-50"
    )}>
      <p>{message.content}</p>
      <span className="text-xs text-gray-500">{formattedTime}</span>
    </div>
  );
}
```

### Custom Hook
```tsx
import { useState, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);

  const mutation = useMutation({
    mutationFn: sendChatMessage,
    onSuccess: (data) => {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
      }]);
    },
  });

  const sendMessage = useCallback((content: string) => {
    setMessages(prev => [...prev, { role: 'user', content }]);
    mutation.mutate(content);
  }, [mutation]);

  return {
    messages,
    sendMessage,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}
```

### State Management (Zustand)
```tsx
import { create } from 'zustand';

interface AppState {
  sidebarOpen: boolean;
  currentView: 'chat' | 'search' | 'documents';
  toggleSidebar: () => void;
  setView: (view: AppState['currentView']) => void;
}

export const useAppStore = create<AppState>((set) => ({
  sidebarOpen: true,
  currentView: 'chat',
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setView: (view) => set({ currentView: view }),
}));
```

### Data Fetching (React Query)
```tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export function useDocuments() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['documents'],
    queryFn: fetchDocuments,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  const syncMutation = useMutation({
    mutationFn: triggerSync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });

  return {
    documents: query.data ?? [],
    isLoading: query.isLoading,
    triggerSync: syncMutation.mutate,
  };
}
```

### Error Boundary
```tsx
import { Component, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? <div>Something went wrong</div>;
    }
    return this.props.children;
  }
}
```

### Streaming Text Component
```tsx
import { useState, useEffect } from 'react';

interface StreamingTextProps {
  stream: AsyncIterable<string>;
}

export function StreamingText({ stream }: StreamingTextProps) {
  const [text, setText] = useState('');

  useEffect(() => {
    const consume = async () => {
      for await (const chunk of stream) {
        setText(prev => prev + chunk);
      }
    };
    consume();
  }, [stream]);

  return <p className="whitespace-pre-wrap">{text}</p>;
}
```

## Best Practices

1. **Co-locate** - Keep related code together (component + hook + types)
2. **Composition over inheritance** - Use compound components
3. **Memoization** - Use `useMemo`/`useCallback` for expensive operations
4. **Keys** - Always use stable, unique keys for lists
5. **Accessibility** - Include ARIA attributes, keyboard navigation
6. **Loading states** - Always handle loading, error, and empty states

## File Naming
- Components: `PascalCase.tsx` (e.g., `ChatWindow.tsx`)
- Hooks: `useCamelCase.ts` (e.g., `useChat.ts`)
- Utils: `camelCase.ts` (e.g., `formatDate.ts`)
- Types: `camelCase.ts` or `index.ts`
