SADA ALQUANTUM - AGENTS
=======================

Twenty (or fewer) agents share one field of particles. They listen, fall into
superposition, collapse - and a quantum draw decides which one answers.
Sound: none. Everything is driven from the CONTROL panel - by mouse or by a MIDI
controller (see MIDI below).


RUN IT
------
0. Three windows open with the file: CONTROL (Ctrl+1), the HOW TO guide (Ctrl+2,
   or the GUIDE button) and the FINAL IMAGE preview (Ctrl+3).
1. The CONTROL panel opens by itself when the file opens. Closed it? Ctrl+1.
   (Or right-click CONTROL > View.)
2. START   from A (territory) the board first becomes bodies (10 s),
           then rounds loop on their own.
3. STOP    whatever is happening relaxes, everyone goes home, the stage idles.
4. RESET   stop + back to A + clear the curtain's memory (the look then
           needs a while to grow back).
5. Ctrl+9 opens the output window (on the 2nd screen if there is one), Ctrl+0 closes it. Ctrl+8 video, Ctrl+7 still.
   THE FINAL IMAGE is FINAL_OUTPUT (yellow node in /project1) = Pop_glsl_sort/out_ajan.
   The window and both recorders show exactly this image.


ONE ROUND
---------
  1 LISTENING       agents lean to the middle, breaths fall into sync
  2 SUPERPOSITION   short, chaotic: radius flicker, random kicks
  3 COLLAPSE        the qubits draw the winner; it inflates, the others flow into it
  4 ANSWER          the winner fills the board (8 s)
  5 RETURN          everyone home, same particles, nothing reborn (5 s)
  -> next round

TIME on the panel = LISTENING + SUPERPOSITION + COLLAPSE (base 21 s, the three keep
their proportions 15 : 2.5 : 3.5).
  mode 1  RANDOM RANGE   every round draws a length between shortest and longest
  mode 2  FIXED TIME     every round lasts exactly that

AGENTS on the panel = how many are on stage (2-20). It changes at once when idle
or listening, otherwise from the next round. Fewer agents = bigger agents (same
coverage). Nobody's particles are deleted: an agent leaving the stage shrinks into
another one (slot i goes to agent i % N); when it returns its own material comes back.

MIDI (any controller - pads, buttons, knobs, faders)
----
Plug the controller in BEFORE opening TouchDesigner. On the panel's MIDI card:
1. DEVICE   click until your controller's name shows.
2. LEARN    the button lights up.
3. Click a control on the panel (START, STOP, RESET, 1 RANDOM RANGE, 2 FIXED TIME,
   a knob, or the A <-> B bar). In learn mode a click only selects it.
4. Press / move the control on your device. A small gold label (e.g. "cc 21")
   appears next to the panel control.
5. Repeat 3-4, then LEARN again to finish. FORGET removes the selected binding.
Buttons answer to a pad (note) or a button (CC). Knobs and the bar need a knob or
fader (CC 0-127 = the full range). The bindings are saved with the file.

THE DRAW: Qiskit Aer (a simulator, not quantum hardware), just enough qubits for the
number of agents (5 agents = 3 qubits, 10 = 4, 20 = 5). Out-of-range results are
drawn again. Without Qiskit it falls back to Python random (the WINNERS list then
says 'python').


THE MAP
-------
/project1
  CONTROL            the panel. Logic: CONTROL/actions (one Python module),
                     MIDI: CONTROL/midi + midi_map
  Pop_glsl_sort      the piece. Open it: numbered bands with signs
     1 STAGE         STAGE_KUME (round manager), ajan_par (dials), kume_log (draws)
     2 AGENT CENTRES CPU: 20 discs, social forces (ajan_merkez_py)
     3 QUANTUM FIELD the qubit state behind the texture (qsim)
     4 PARTICLES     GPU: glsl1 + glsl1_compute (SADA FIELD, our own shader)
     5 RENDER
     6 CURTAIN       feedback loop that builds the image (single colour only)
     7 COLOUR+OUTPUT ajan_renk -> out_ajan = THE COLOURED IMAGE
     8 TOOLS         measuring scripts
     9 UNUSED / OLD  kept, nothing reads them
  FINAL_OUTPUT       THE FINAL IMAGE (coloured), what the audience sees
  cntrl              keyboard shortcuts, output window, recorders
  control_preview, guide_preview   pictures of the panel and the guide, not part of the show


RULES THAT KEEP IT ALIVE
------------------------
- The image is an ACCUMULATION. Do not reset feedback2 (particle memory) during a
  show: a rebirth takes minutes to look right. RESET only clears the curtain.
- Never push several colours through the curtain (comp1/feedback1/level1): it
  splits into RGB confetti. Colour is added after it, in ajan_renk.
- Editing the STAGE_KUME text reloads it: a running round stops (round numbers
  continue from kume_log).
