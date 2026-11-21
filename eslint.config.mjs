export default [
  { ignores: ['**/node_modules/**', '**/dist/**'] },
  {
    files: ['frontend/**/*.{js,jsx}'],
    languageOptions: {
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: {
        AbortController: 'readonly',
        Blob: 'readonly',
        document: 'readonly',
        Event: 'readonly',
        fetch: 'readonly',
        FormData: 'readonly',
        setTimeout: 'readonly',
        URL: 'readonly',
        URLSearchParams: 'readonly',
        window: 'readonly'
      }
    },
    rules: {
      'no-unreachable': 'error',
      'no-dupe-keys': 'error',
      'no-undef': 'error',
      'no-unused-expressions': 'error'
    }
  }
]
