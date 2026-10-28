"use client";

import { QueryClient, QueryClientProvider, QueryCache, MutationCache } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { toast, Toaster } from "sonner";

interface QueryProviderProps {
  children: ReactNode;
}

export function QueryProvider({ children }: QueryProviderProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 1000 * 60, // 1 minute
            retry: (failureCount, error: any) => {
              if (error?.status === 401 || error?.status === 403 || error?.status === 404) {
                return false;
              }
              return failureCount < 2;
            },
          },
        },
        queryCache: new QueryCache({
          onError: (error: any) => {
            const message = error?.message || "An unexpected error occurred.";
            toast.error(message);
          },
        }),
        mutationCache: new MutationCache({
          onError: (error: any) => {
            const message = error?.message || "Action failed.";
            toast.error(message);
          },
        }),
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster
        theme="dark"
        position="bottom-right"
        toastOptions={{
          className:
            "bg-[#14161C] border border-[#262A35] text-[#E8EAF0] shadow-card",
        }}
      />
    </QueryClientProvider>
  );
}
