/**
 * 舞台立绘与动效参数 —— 单一配置源。
 * 换立绘、调视差/发晕手感只改这个文件，不用碰组件。
 */

/** 主立绘（全屏舞台底图） */
export const MAIN_SPRITE = '/avatars/stage-main.png'

/**
 * 情绪差分立绘：mood → 图片路径。
 * 目前差分用 CSS 滤镜近似；以后有同构图的表情差分图，在这里填路径即可自动启用换图。
 */
export const EXPRESSION_DIFFS: Partial<Record<string, string>> = {
  // happy: '/avatars/stage-happy.png',
  // sad: '/avatars/stage-sad.png'
}

/** 视差参数（伪视线跟随的手感） */
export const PARALLAX = {
  maxRotateY: 6, // 水平方向最大旋转角（deg）
  maxRotateX: 4, // 垂直方向最大旋转角（deg）
  maxTranslateX: 12, // 水平最大位移（px）
  maxTranslateY: 8, // 垂直最大位移（px）
  lerp: 0.08, // 平滑系数（越小越"跟手但慵懒"）
  settleEpsilon: 0.001 // 视为停止追值的误差阈值
}

/** 发晕检测参数 */
export const DIZZY = {
  speedThreshold: 2500, // 指针瞬时速度阈值（px/s）
  windowMs: 500, // 采样时间窗口
  hitsNeeded: 3, // 窗口内超速次数达到即触发
  dizzyMs: 2500, // 眩晕动画时长
  cooldownMs: 8000 // 冷却时长（眩晕结束后计）
}
