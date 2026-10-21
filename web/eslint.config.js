// ESLint: checks the web code for mistakes (unused or undefined names, missing list keys, hooks used
// wrongly or with missing dependencies, and the plain mistakes and React traps listed below). `npm run build` runs it with --max-warnings 0, so the build
// stops on any warning. A deliberate exception gets an eslint-disable comment that says why.
import react from 'eslint-plugin-react'
import hooks from 'eslint-plugin-react-hooks'
import globals from 'globals'

export default [
  {
    files: ['src/**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest', sourceType: 'module', globals: { ...globals.browser },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { react, 'react-hooks': hooks },
    settings: { react: { version: '19' } },
    rules: {
      'no-unused-vars': ['warn', { varsIgnorePattern: '^_', argsIgnorePattern: '^_' }],
      'no-undef': 'error',
      'react/jsx-uses-vars': 'error',
      'react/jsx-uses-react': 'off',
      'react/jsx-key': 'error',
      'react/jsx-no-undef': 'error',
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      // (2026-10-21 review) plain mistakes: a key twice, code that can't run, a test that's always true or false...
      'no-dupe-keys': 'error', 'no-duplicate-case': 'error', 'no-dupe-else-if': 'error', 'no-unreachable': 'error',
      'no-self-assign': 'error', 'no-self-compare': 'error', 'no-constant-condition': ['error', { checkLoops: false }],
      'no-constant-binary-expression': 'error', 'no-unsafe-optional-chaining': 'error', 'no-cond-assign': 'error',
      'valid-typeof': 'error', 'use-isnan': 'error', 'no-fallthrough': 'error', 'no-sparse-arrays': 'error',
      'no-unused-expressions': ['error', { allowShortCircuit: true, allowTernary: true }],
      // ...and React ones: a component made inside another (rebuilt on every render - Shopping mode's rows were),
      // a new-tab link without rel="noreferrer", class= for className, a prop twice
      'react/no-unstable-nested-components': ['error', { allowAsProps: true }],
      'react/jsx-no-target-blank': 'error', 'react/no-unknown-property': 'error', 'react/jsx-no-duplicate-props': 'error',
      'react/no-children-prop': 'error', 'react/void-dom-elements-no-children': 'error', 'react/jsx-no-comment-textnodes': 'error',
      'react/no-danger-with-children': 'error', 'react/jsx-no-useless-fragment': ['error', { allowExpressions: true }],
    },
  },
]
