// Port of jumpnrun/core/actions.py: player input for one frame (human or bot).

export interface Action {
  readonly left: boolean;
  readonly right: boolean;
  readonly jump: boolean;
  readonly shoot: boolean;
}

export function action(left = false, right = false, jump = false, shoot = false): Action {
  return { left, right, jump, shoot };
}

export const NOOP = action();

export const BOT_ACTIONS: readonly Action[] = [
  NOOP,
  action(true),
  action(false, true),
  action(false, false, true),
  action(false, true, true),
  action(false, false, false, true),
];
export const BOT_ACTION_NAMES = ["noop", "left", "right", "jump", "right+jump", "shoot", "left+jump"];
export const BOT_ACTIONS_V3: readonly Action[] = [...BOT_ACTIONS, action(true, false, true)];
export const ACTION_REPEAT = 4;
export const DEFAULT_REPEAT = 2;

/** Ghost encoding of progress.py: one hex digit per frame, bits left=1, right=2, jump=4, shoot=8. */
export function actionBits(a: Action): number {
  return (a.left ? 1 : 0) | (a.right ? 2 : 0) | (a.jump ? 4 : 0) | (a.shoot ? 8 : 0);
}

export function actionFromBits(bits: number): Action {
  return action((bits & 1) !== 0, (bits & 2) !== 0, (bits & 4) !== 0, (bits & 8) !== 0);
}
