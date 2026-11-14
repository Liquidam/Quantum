Pop_glsl_sort - THE PIECE, band by band  (overview: /project1/README)
=====================================================================

Signal path, top to bottom:

  CONTROL panel --settings--> 1 STAGE --dials (ajan_par)--> 2 AGENT CENTRES
        --u_kA/u_kB/u_kC arrays--> 4 PARTICLES <--q_re/q_im-- 3 QUANTUM FIELD
        --> 5 RENDER --> 6 CURTAIN (comp1) --> 7 COLOUR (ajan_renk) --> out_ajan

1 STAGE
  STAGE_KUME       round manager (Python module). basla() start, bitir() stop,
                   durum() raw state, bilgi() what the panel shows
  STAGE_KUME_exec  calls adim() every frame; onStart -> bitir() (opens at rest)
  ajan_par         the dials it writes: form (follows CONTROL's A/B bar),
                   tension, chaos, winner, collapse, n_active
  kume_log         one row per draw: round, time, agents, length, winner, source

2 AGENT CENTRES  (CPU, numpy, 20 points - costs nothing)
  ajan_merkez      Script CHOP, one sample per agent: cx cy r vx vy ang pitch hue
                   conv alias + previous frame
  ajan_merkez_py   AgentCentres: contact, asymmetric attraction (Particle Life),
                   wander, home seat (A), dish, listening, chaos, collapse.
                   n_active = agents on stage; an off-stage slot shrinks into
                   its alias (i % N) and hands it its particles
  ajan_A/B/C       pack the channels into the shader's uniform arrays
                   u_kA (cx cy r hue)  u_kB (previous)  u_kC (ang pang conv alias)

3 QUANTUM FIELD
  qsim             n-qubit state (Qiskit) -> q_re, q_im = amplitudes for the
                   interference field in the particle shader

4 PARTICLES  (GPU)
  pointgen1 -> attribute1 -> size -> rot -> feedback2 -> glsl1 -> sort1 -> null3
  glsl1_compute    SADA FIELD, our own shader: SPH fluid, each agent's basin (a
                   capped pull, not a cage), the quantum field, chip routing,
                   takeover in collapse. Copy: AJANLAR/kumeler/sada_field_v1_2026-11-14.glsl
                   Particle attribute Agent = home agent (never rewritten)
  feedback2        simulation memory. Resetting it = rebirth (minutes). Avoid live.
  field_defaults -> null4 -> math1 -> null5   base field settings (SPH radius 13.2592,
                   attraction 0.0937; flow 0, centre pull 0)

5 RENDER
  geo1 (circle1 sprite, pbr1) through cam1 (under null1), lights (light1front under
  null6), at RES.

6 CURTAIN
  rgbaDelay1 -> null8 -> comp1 = render x level1(feedback1(last comp1))
  The look accumulates here. feedback1 resetpulse = the only sanctioned reset.
  ONE colour only - colour is added in band 7.
  (the curtain itself is uncoloured - colour is band 7)

7 COLOUR + OUTPUT
  ajan_renk (code ajan_renk_pixel)  hue per agent in screen space, from the disc
                   centres; brightness from the curtain; tone curve for dense piles
  out_ajan         THE FINAL IMAGE -> out1 -> /project1 FINAL_OUTPUT + cntrl (window, recorders)
  ajan_kayit       ProRes recorder of out_ajan

8 TOOLS   KUME_OLC (cluster measurement), OLCUM, SHOT, SWEEP
9 UNUSED  kept, not deleted. See the sign.
