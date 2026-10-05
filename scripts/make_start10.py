"""Phase 10 start model: phase8_final + view v3 + 7th action left+jump, initialised exactly like "left".

    python3 scripts/make_start10.py          # -> runs/phase10/start_p8_v3.zip (+ .json)

In phase 9 left+jump started ~50x less likely than "left" and was never tried; now its logit equals "left".
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    from stable_baselines3.common.vec_env import DummyVecEnv

    from jumpnrun.core.level import Level
    from jumpnrun.rl.env import JumpNRunEnv, fixed_levels
    from jumpnrun.rl.modelinfo import grow_v3, write_model_config
    from jumpnrun.rl.ppo_demos import PPOWithDemos

    level = Level.from_file(ROOT / "levels/handmade8/abgrund.txt")
    env = DummyVecEnv([lambda: JumpNRunEnv(fixed_levels([level]), action_repeat=2, overview=True, obs_v3=True)])
    model = grow_v3(ROOT / "models/phase8_final.zip", env, PPOWithDemos, a6_bias_offset=0.0)
    out = ROOT / "runs/phase10/start_p8_v3.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(out))
    write_model_config(out, action_repeat=2, overview=True, arch="grid", obs_v3=True,
                       source="phase8_final + grow_v3 (a6 bias = left)")
    print("saved", out, model.num_timesteps)


if __name__ == "__main__":
    main()
