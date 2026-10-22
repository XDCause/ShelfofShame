// ESLint: checks the web code for mistakes (unused or undefined names, missing list keys, hooks used
// wrongly or with missing dependencies, and the plain mistakes and React traps listed below). `npm run build` runs it with --max-warnings 0, so the build
// stops on any warning. A deliberate exception gets an eslint-disable comment that says why.
// (2026-10-22) ESLint 10 understands JSX names itself (an unused or undefined component is caught by no-unused-vars /
// no-undef), and the React rules come from @eslint-react: eslint-plugin-react stopped at ESLint 9.
import react from '@eslint-react/eslint-plugin'
import hooks from 'eslint-plugin-react-hooks'
import globals from 'globals'

export default [
  {
    files: ['src/**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest', sourceType: 'module', globals: { ...globals.browser },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { '@eslint-react': react, 'react-hooks': hooks },
    rules: {
      'no-unused-vars': ['warn', { varsIgnorePattern: '^_', argsIgnorePattern: '^_' }],
      'no-undef': 'error',
      '@eslint-react/no-missing-key': 'error',
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      // (2026-10-21 review) plain mistakes: a key twice, code that can't run, a test that's always true or false...
      'no-dupe-keys': 'error', 'no-duplicate-case': 'error', 'no-dupe-else-if': 'error', 'no-unreachable': 'error',
      'no-self-assign': 'error', 'no-self-compare': 'error', 'no-constant-condition': ['error', { checkLoops: false }],
      'no-constant-binary-expression': 'error', 'no-unsafe-optional-chaining': 'error', 'no-cond-assign': 'error',
      'valid-typeof': 'error', 'use-isnan': 'error', 'no-fallthrough': 'error', 'no-sparse-arrays': 'error',
      'no-unused-expressions': ['error', { allowShortCircuit: true, allowTernary: true }],
      // ...and React ones: a component made inside another (rebuilt on every render - Shopping mode's rows were),
      // a new-tab link without rel="noreferrer", class= for className
      '@eslint-react/no-nested-component-definitions': 'error',
      '@eslint-react/dom-no-unsafe-target-blank': 'error', '@eslint-react/dom-no-unknown-property': 'error',
      '@eslint-react/jsx-no-children-prop': 'error', '@eslint-react/dom-no-void-elements-with-children': 'error',
      '@eslint-react/jsx-no-comment-textnodes': 'error', '@eslint-react/dom-no-dangerously-set-innerhtml-with-children': 'error',
      '@eslint-react/jsx-no-useless-fragment': ['error', { allowExpressions: true }],
    },
  },
]
