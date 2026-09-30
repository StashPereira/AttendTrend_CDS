import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./styles.css";
export const client = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (count, error: any) =>
        error.status !== 401 && error.status !== 404 && count < 2,
      staleTime: 15000,
      refetchOnWindowFocus: true,
    },
  },
});
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
