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

/** 2.5D 深度视差的日/夜场景标识（对应 ui store 的 theme） */
export type StageSceneKey = 'day' | 'night'

/**
 * 2.5D 深度视差资源：日/夜各一套「插画 + 深度图」。
 * 深度图规格：与插画同源同分辨率、8 位灰度 PNG、白=近（前端读 R 通道）。
 * ⚠️ 正式希亚日/夜立绘就位前，先用已验证的母版及其深度图跑通管线（日/夜暂同源）。
 */
export const PARALLAX_SCENES: Record<StageSceneKey, { src: string; depth: string }> = {
  night: { src: MAIN_SPRITE, depth: '/avatars/stage-main-depth.png' },
  day: { src: MAIN_SPRITE, depth: '/avatars/stage-main-depth.png' }
}

/** 2.5D 深度视差参数（PixiJS 自定义着色器的手感） */
export const PARALLAX_2D5 = {
  strength: 0.035, // 深度视差强度（画面归一化坐标比例，上限建议 3%~5%）
  pointerGain: 1.6, // 鼠标视差相对深度视差的倍数
  breathAmp: 0.006, // 呼吸微动幅度
  breathPeriodMs: 5200, // 呼吸周期
  margin: 0.08, // 四边形相对视口的外扩边距（边缘保护，避免视差采样露边）
  objectPositionY: 0.3 // 与现有立绘 object-position: 50% 30% 对齐
}

/** 发晕检测参数 */
export const DIZZY = {
  speedThreshold: 2500, // 指针瞬时速度阈值（px/s）
  windowMs: 500, // 采样时间窗口
  hitsNeeded: 3, // 窗口内超速次数达到即触发
  dizzyMs: 2500, // 眩晕动画时长
  cooldownMs: 8000 // 冷却时长（眩晕结束后计）
}
