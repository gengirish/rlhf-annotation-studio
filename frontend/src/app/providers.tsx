"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PropsWithChildren, useState } from "react";
import { Toaster } from "sonner";

import { ClerkSessionBridge } from "@/lib/clerk-session-bridge";

export function Providers({ children }: PropsWithChildren) {
  const [queryClient] = useState(() => new QueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      <ClerkSessionBridge />
      {children}
      <Toaster position="bottom-right" richColors />
    </QueryClientProvider>
  );
}
