# GT6 cockpit head motion: recon notes

Target: **EU BCES01893 1.22 `EMAIN.SELF`** (`PPU-638ef307e2b3…`). Addresses are PS3 virtual addresses.

## Camera classes

`GTCamera::OnboardImplement` (constructor 0x2FB9D8) builds the onboard views: `RigidCamera`, `RigidCameraXY`,
`TopviewCamera`, `GroundPlaneCamera` and two `ImpactBlurCamera` (constructor 0x2F60CC, vtable 0x158EB50).
The everyday cockpit view is rigid; the head motion lives in `ImpactBlurCamera`.

## ImpactBlurCamera

Update 0x2F8F0C, apply 0x2F8A08. Per frame:

1. Car position (target `+0x10`, virtual slot 8) -> velocity -> acceleration (divided by dt); previous values
   at `+0x20 / +0x30 / +0x40`.
2. **Jerk** = acceleration - previous acceleration (`vsubfp` at 0x2F90B0) and the acceleration, both rotated into
   the car's frame.
3. Per axis: the jerk only counts above **200 m/s^2** (0x1130078), then `clamp(+-500) / 500` (0x113007C / 0x1130080)
   -> input vector. A separate vector is acceleration / 19.62 (2 G), clamped +-1.
4. If any axis passed, the car is asked whether it collided this frame (virtual slot 0x2C at 0x2F94C4); if not,
   the inputs are zeroed (and only every other frame passes, flag `+0x1E4`).
5. Cockpit (`+0xC == 1`): inputs x gains -> springs, applied around a neck pivot:

| Channel | Spring | Input | Gain (constant) |
|---|---|---|---|
| `+0x1E8` DriverHeadDamper (fore/aft slide) | critical, k=30 | longitudinal x gain (x0.1 on one side, 0x113009C) + 2 G term | -10 (0x1130098, shared) |
| `+0x228` DriverHeadDamper (side slide) | critical, k=15 | lateral x gain | -10 (same load) |
| `+0x15C` pitch | k=350 c=-22 m=2 | longitudinal | -1.0472 (0x11300A8) |
| `+0x1B4` yaw | k=270 c=-27 m=1.38 | lateral | 1.3963 (0x11300AC, shared) |
| `+0x188` roll | k=350 c=-22 m=2 | lateral | 0.8727 (0x11300B0) |

Spring tables at 0x1640328..0x1640388 (k, c, mass, rate limit, limits). DriverHeadDamper setup 0x2D22D8 stores k and
2*sqrt(k) (critical damping). Neck pivot: translate (0, -0.15, 0.06), rotate pitch/yaw/roll, translate back.
Other onboard views (`+0xC != 1`) use `+0x54` / `+0xAC` only.

So stock GT6 uses the rig for crashes only: jerk, a 20 G threshold and a collision check.

## The patch (gt6launcher/head_motion.py)

* NOP 0x2F90B0 (rig gets acceleration), branch over the collision check at 0x2F949C, threshold 0, normaliser
  500 / strength.
* Yaw and slide gain loads redirected (`lis r9,0x156` + `lfs ...,-0x7c0/-0x7bc(r9)`) to 0x155F840 / 0x155F844,
  in the zeroed tail of the text segment's last 64 KiB page (segment ends 0x1550868, page ends 0x1560000);
  the engine color patch uses 0x155F800..0x155F827.
* Emulator patch 16 rewrites normaliser and the four gains every frame from `Video/Head Motion`.

## Tools

`tools/re/` plus emulator patch 15 (`gt6_live.txt` bridge) for live reads/writes while driving.
