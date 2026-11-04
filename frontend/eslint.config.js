import js from '@eslint/js';
import tseslint from 'typescript-eslint';

const config = [
  { ignores: ['dist/', 'node_modules/'] },
  js.configs.recommended,
  ...tseslint.configs.strict,
  {
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
      eqeqeq: ['error', 'always'],
    },
  },
  {
    files: ['scripts/**/*.mjs'],
    languageOptions: {
      globals: {
        console: 'readonly',
        document: 'readonly',
        process: 'readonly',
        window: 'readonly',
      },
    },
  },
];

export default config;
