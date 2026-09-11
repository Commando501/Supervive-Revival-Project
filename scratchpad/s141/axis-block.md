  drop the candidate.**
  ★★★★★ **AND S141 FOUND THE DISCRIMINATOR: IT IS THE KICK AXIS** (`docs/s141-tier3-settled.md`
  §4.1b). **[M] engine `PhysFalling` brackets only ONE of its four `CalcVelocity` calls with
  `Velocity.Z = 0` / restore** (`0x035ECBD8` bracketed; `0x035ECB75` and `0x035ED549` NOT;
  `0x035ED5D5` NOT ESTABLISHED). So (i) a clamp on an unbracketed call zeroes Z **permanently**, and
  (ii) **inside the bracketed call a Z-only velocity is INVISIBLE to `IsExceedingMaxSpeed`**
  (`SizeSquared() > MaxInputSpeed² × 1.01`): horizontal 600 gives `360000 > 252500` ⇒ TRUE ⇒ compares
  `|V| = 600` ⇒ normal clamp ⇒ **scaled to 500, exactly what flight 3 measured**; vertical −600 has
  its Z zeroed by the bracket ⇒ `SizeSq = 0` ⇒ FALSE ⇒ compares `MaxInputSpeed` ⇒ if `< 1e-4`,
  **ZeroVector on all three.** **ONE hypothesis retrodicts BOTH flights, `[I]`** (the table is [M];
  the composition needs `MaxInputSpeed < 1e-4`, never read).
  ⇒ ★★ **FLY IT AS A TWO-ARM A/B ON THE AXIS IN ONE SITTING** — same arm, kick horizontally (must
  sustain ~500) and vertically (must zero). **If both behave the same the hypothesis is dead.**
  ⇒ **And S142's read is ONE READ:
