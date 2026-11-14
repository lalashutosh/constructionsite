/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API?: "fixtures" | "live";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
