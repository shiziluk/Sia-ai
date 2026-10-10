/**
 * Live2D 舞台配置 —— 单一配置源（"模型可替换结构"）。
 *
 * 换模型（例如把官方示例 Haru 换成希亚的专属模型）时**只改这个文件**，不用动组件：
 *   1) MODEL_URL 指向新模型的 .model3.json
 *   2) MOOD_EXPRESSION 按新模型的表情名（Expressions[].Name）重填
 *   3) HIT_REACTION 按新模型的命中区（HitAreas）重填
 *   4) 若新模型没有"闭眼造型"类表情，BLINK_OFF_EXPRESSIONS 留空即可
 */
import type { Mood } from '@/utils/emotionAnim'

/**
 * 模型入口文件（.model3.json）。
 * 当前为官方免费示例 Haru（Cubism 3，Free Material License，一般用户/小企业可商用）。
 * ⚠️ 希亚的专属 Live2D 模型尚在制作中；模型就绪后把这里换成希亚模型路径即可，例如：
 *   export const MODEL_URL = '/live2d/sia/sia.model3.json'
 */
export const MODEL_URL = '/live2d/haru/haru_greeter_t03.model3.json'

/**
 * 心情 → 表情名（model3.json 里 Expressions[].Name）。
 * ✅ 下表语义已由 2026-10-11 实机逐一点按截图确认（括号内为实测观感，非参数推测）：
 *   f00 微张嘴 ｜ f01 张嘴笑(开心) ｜ f02 压低眉+张嘴(不满/喊) ｜ f03 皱眉抿嘴(失落/忧伤)
 *   f04 笑眼(闭眼微笑 ^_^) —— 依赖关眨眼才可见，见下方 BLINK_OFF_EXPRESSIONS
 *   f05 睁大眼(惊愕) ｜ f06 腮红(害羞) ｜ f07 闭眼+嘴角下撇(难过)
 * ⚠️ 这是 **Haru 专属** 的映射；换模型后必须按新模型的表情集重填。
 */
export const MOOD_EXPRESSION: Record<Exclude<Mood, ''>, string> = {
  happy: 'f01',
  sad: 'f07',
  angry: 'f02',
  anxious: 'f03',
  sleepy: 'f03',
  shy: 'f06',
  surprised: 'f05',
  tsundere: 'f02'
}

/**
 * 需要「闭眼」造型的表情 id：这些表情把 ParamEyeLOpen/ROpen 乘成 0（f04 笑眼就是 ^_^ 的闭眼）。
 * ⚠️ 为什么必须特殊处理：库的更新时序是「应用表情 → 眨眼控制器再跑」，而眨眼用的是
 * setParameterValueById（**覆写**而非相乘），每帧把眼睑参数硬写回 1，表情的闭眼会被冲掉。
 * 对策：这些表情生效期间临时关掉自动眨眼（眼睛本就闭着，无需再眨）。
 */
export const BLINK_OFF_EXPRESSIONS = new Set<string>(['f04'])

/**
 * 点击命中区（model3.json 的 HitAreas）→ 反应表情名。
 * Haru 有两个命中区：Head / Body —— 摸头她害羞，戳身上她嘴硬不满。
 */
export const HIT_REACTION: Record<string, string> = { Head: 'f06', Body: 'f02' }

/** 点击反应的持续时长（ms），到点自动回到当前心情 */
export const REACTION_MS = 2000
