/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ENGINE?: string;
  readonly VITE_API?: "fixtures" | "live" | "mock";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
