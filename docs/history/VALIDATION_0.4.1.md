# PSF 0.4.1 validation

The release was checked against the user-supplied original-game, Kaiserreich,
The New Order and Pax Britannica scripts and the pinned Rust CWTools 2.3.0.
Original user screenshots informed the overlap and attachment repairs. Current
geometry was rendered for internal inspection; it is not an HOI4 screenshot.

**The final gate has zero new errors and zero new warnings.** Raw CWTools still
exits 1 with **367 errors and 117 warnings**. Exact original-source comparisons
and declared original-texture dependencies account for these diagnostics below.
The raw reports and severity levels have not been changed to claim a clean run.

**HOI4 itself was not available for a launch or rendering test.** Actual native
attachment origins, DDS pixels, font/texticon baselines, first-frame ordering and
scrollbar mouse input remain outside these checks.

## Completed release gates

| Gate | Observed result |
| --- | --- |
| Complete Python suite | 244 tests passed, 150.087 seconds, exit 0 |
| Real CWTools positive and negative controls | 20 passed |
| Generated-script validation | 0 new errors, 0 new warnings, gate exit 0 |
| Raw CWTools result | 367 errors, 117 warnings, engine exit 1 |
| Loader preflight | 456 text files, 3 native GUI roots, 0 errors |
| Generated script discovery | 453 staged files, 252 stock-localisation imports |
| History reconstruction | All 364 country histories matched their source transform |
| Generic political reconstruction | Both originals matched; 3 opinion and 13 peace definitions changed |
| GUI geometry and bindings | 32,461 checks, 339 windows, 0 failures |
| Installer CRC | All 795 entries passed |
| Isolated installed-wheel rebuild | 795 files matched; 0 missing, extra or changed |
| Isolated installer reproduction | Byte-identical to the distributed installer |
| HOI4 launch and in-game interaction | Not performed |

The suite includes all thirty new choices, each also repeated to check source
idempotence. An independent review verified all 61 define names and namespaces
against the supplied `00_defines.lua` and exercised repeated policy transitions.

Reports are in `build/validation-0.4.1/`, `build/validation-041-controls/`,
`build/layout-0.4.1.json` and `build/wheel-verification-0.4.1.json`.
The previous release has a separate [0.4.0 record](VALIDATION_0.4.0.md).

## Raw diagnostic accounting

### Original texture payloads: 272 errors

The script archive declares original sprites but omits their DDS payloads.
These CW113 occurrences reference 14 exact original texture paths. Only an
exact declared missing-texture message/path from a GFX declaration qualifies;
unknown paths and spelling mistakes fail. Declaration provenance is retained
in `stock-texture-dependencies.json`. No placeholder DDS or forged cache is used.
A full `--vanilla` run does not apply this script-only dependency classification.
This does not prove rendering in an arbitrary installation.

### Original country history: 94 errors and 117 warnings

The same complete staged environment runs once with emitted histories and once
with independently verified originals. File inventory, pinned source hashes,
complete output reconstruction, source-line mapping, diagnostic identity and
surrounding original text must match. Each baseline occurrence can justify only
one inherited diagnostic. The originals contribute **94 errors, 117 warnings
and 83 informational diagnostics**. Missing references and rule/snapshot
differences are not collectively described as harmless or false positives.

`cwtools.json`, `native-history-baseline.json` and
`inherited-native-history-diagnostics.json` retain the raw results and proof.
New bootstrap statements and changed original statements cannot inherit an
error merely by occurring in the same file. The explicit Norway source repair
remains separately recorded and tested.

### Original generic peace source: one error

The supplied `defensive_war_take_state` definition contains
`peace_action_type = take_state`; the pinned rules diagnose this original enum.
The adapter leaves the original statement intact. Both new political snapshots
are independently pinned, and their complete generated transformations and
changed-definition inventories are verified before a baseline is permitted.

The original source reproduces the same error in the same staged environment.
Matching includes original line, surrounding text, code, severity, full message
and multiplicity. Every line inside a PSF-rewritten definition is excluded,
even if its text happens to be unchanged or repeated elsewhere.
`inherited-native-politics-diagnostics.json` records this separate proof.
The diagnostic is not called harmless, a validator false positive, or a clean
engine result. A new invalid PSF peace trigger fails the real negative control.

## Behavior and layout coverage

The strict interpreter executes emitted Clausewitz effects and rejects commands
outside its supported subset. It does not emulate the whole engine or renderer.

- Government checks cover independent organizations, concurrent alliances,
  caretakers, live membership within transactions, zero-influence cleanup,
  stable election ties, legitimacy and immediate derived-value refresh.
- Initialization covers original histories, 1939 overrides, fallback countries
  and idempotent bootstrap without advancing modifier timers.
- Policy checks execute partial overrides and repeated institution transitions,
  including resetting old thresholds and Boolean rules.
- Identity checks cover coalition leaders, manual/resume/release APIs, exact
  cosmetic-slot ownership, all native-name variants and three authored flag sizes.
- UI checks cover domestic/foreign scopes, equal-revision country switching,
  exclusive pages, all current alliance memberships, institution/program markers,
  scroll bounds, direct callbacks, independent icons and bilingual localization.
- Content checks execute all new choices, early activation where needed,
  membership preservation, nonstacking sources, expiry, late-bookmark retention
  and the actual weekly scheduling hook.
- Source controls reject changed pins, forged metadata, modified PSF overrides,
  unrelated original edits and new errors in rewritten definitions.

Domestic summary bottom is Y=382, before the original management area at Y=383.
Foreign summary bottom is native-window Y=246, before the focus area at Y=248.
Pie fill remains inset within the 63-pixel overlay. The important-country
political column is 305 pixels wide; original portrait/title positions make
room while history anchors remain. These are coordinate/script facts, not
measured game pixels.

## Distributed artifact and independent rebuild

| Field | Value |
| --- | --- |
| Installer | `distributions/psf-0.4.1.zip` |
| Archive size | 3,405,066 bytes |
| Entries | 795 |
| Uncompressed size | 64,873,707 bytes |
| SHA-256 | `f36806a02a8bb0af7e047cbb2265d805de36e82e96def5a7c1f16512961d6523` |
| Compiler wheel | `hoi4_psf-0.4.1-py3-none-any.whl`, 684,006 bytes |

The wheel was installed into an isolated target. Compilation ran under Python
`-I` outside the repository, with assertions that loaded PSF modules came from
that installation. This exercises packaged GUI, history, ideology and generic
political snapshots. All 795 file hashes matched the repository build; packing
the isolated output produced the same archive bytes and SHA-256.

To reproduce the source gates:

```sh
python -m unittest discover -s tests -v
python -m psf compile examples/vanilla/manifest.json --output dist
python tools/ci/validate.py --root dist --reports build/validation-0.4.1 --self-test
python tools/ui/audit_layout.py dist/psf_vanilla_example --report build/layout-0.4.1.json
python -m psf pack --root dist --output build/psf-0.4.1.zip
cmp distributions/psf-0.4.1.zip build/psf-0.4.1.zip
```

Remaining original story conditions, country-specific peace logic and hardcoded
branches are documented in [NATIVE_MECHANICS.md](../NATIVE_MECHANICS.md).
No percentage of complete game replacement or successful game launch is inferred.
