  /// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Endereço da API (backend FastAPI). Ex.: http://localhost:8000 */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
