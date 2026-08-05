'use strict'

const { existsSync, writeFileSync } = require('node:fs')
const { join } = require('node:path')

/**
 * Garante que o `app-update.yml` exista no pacote do Windows.
 *
 * O electron-builder só grava esse arquivo quando a configuração de publicação
 * é resolvida, o que não acontece em `--publish never`. Um instalador gerado
 * localmente ficava então sem nenhuma referência ao repositório e o
 * electron-updater falhava logo na verificação — foi assim que uma instalação
 * ficou presa na 2.0.0 sem nunca avisar. Aqui preenchemos apenas a lacuna: se o
 * arquivo já veio da build de release, nada é sobrescrito.
 */
exports.default = async function afterPack(context) {
  if (context.electronPlatformName !== 'win32') return

  const target = join(context.appOutDir, 'resources', 'app-update.yml')
  if (existsSync(target)) return

  const { build, name } = require('../package.json')
  const publish = Array.isArray(build.publish) ? build.publish[0] : build.publish
  if (!publish || publish.provider !== 'github') return

  const lines = [
    'provider: github',
    `owner: ${publish.owner}`,
    `repo: ${publish.repo}`,
    `updaterCacheDirName: ${name.toLowerCase()}-updater`,
    ''
  ]
  writeFileSync(target, lines.join('\n'), 'utf8')
  console.log(`  • app-update.yml gerado para build local (${publish.owner}/${publish.repo})`)
}
