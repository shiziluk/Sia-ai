import stylistic from '@stylistic/eslint-plugin'
import parserTs from '@typescript-eslint/parser'
import globals from 'globals'
import parserVue from 'vue-eslint-parser'
import pluginVue from 'eslint-plugin-vue'

export default [
  {
    // 忽略构建产物
    ignores: ['dist/**', 'dev-dist/**', 'node_modules/**']
  },
  ...pluginVue.configs['flat/essential'],
  {
    // 普通 TS 文件：直接用 TS 解析器
    files: ['**/*.ts'],
    languageOptions: {
      parser: parserTs,
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.es2021 }
    },
    rules: {
      'no-console': 'warn'
    }
  },
  {
    // Vue SFC：vue 解析器 + <script> 内用 TS 解析器
    files: ['**/*.vue'],
    languageOptions: {
      parser: parserVue,
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.es2021 },
      parserOptions: {
        parser: parserTs,
        ecmaVersion: 'latest',
        sourceType: 'module',
        extraFileExtensions: ['.vue']
      }
    },
    rules: {
      'no-console': 'warn',
      'vue/multi-word-component-names': 'off'
    }
  },
  {
    // 注册 stylistic 插件（eslint-plugin-vue 的 peer 依赖）
    plugins: { '@stylistic': stylistic }
  }
]
