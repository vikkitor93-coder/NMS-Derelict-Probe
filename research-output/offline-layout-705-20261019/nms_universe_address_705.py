"""NMS 7.05 galaxy-address packing used by derelict generation.

This is a pure port of ``FUN_140583A90`` for the canonical 64-bit universe
address encoding recorded by the Probe. The game reads the fields of its
``GcGalaxyAddress`` at offsets +0x860 (planet), +0x864 (system), +0x868
(voxel X), +0x86C (voxel Y), +0x870 (voxel Z), and +0x874 (reality), clamps
them, and packs the result back into the address bit layout. The top eight
bits are not emitted by the native function.

Exact-build sources:
* NMS 7.05 executable SHA-256:
  13D5060D4EFB9D2A6A6B1B349BC4257231056CC2A055DF4BB15D816262CC3499
* Ghidra decompile and instruction listing for ``FUN_140583A90``:
  D:/Orca/Temp/nms-ghidra-targeted-20261016/generator_helpers.txt
* Generator call site (the address passed to this function):
  D:/Orca/Temp/nms-ghidra-targeted-20261016/generator_caller.txt
* Fixture address and result recorded in:
  research-output/KNOWN_DERELICT_BACKWARD_TRACE_20261019.md

The bit-field interpretation follows the saved Probe address serializer at
``research-output/probe-layout-capture-0.3.55/derelict_baseline_probe.py``;
the native function independently confirms the same field widths and clamps.
This helper only prepares the packed input for the seed mixer. It does not
resolve a preset or claim that a runtime seed-override global was observed.
"""

from __future__ import annotations

from typing import TypeAlias


U64_MASK = 0xFFFFFFFFFFFFFFFF
ADDRESS_HEX_DIGITS = 16


UniverseAddressInput: TypeAlias = int | str


def _checked_address(value: UniverseAddressInput) -> int:
    if isinstance(value, bool):
        raise ValueError("universe address must be an integer or hexadecimal string")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str):
        text = value.strip()
        if text[:2].lower() == "0x":
            text = text[2:]
        if not text or len(text) > ADDRESS_HEX_DIGITS:
            raise ValueError("universe address must contain 1 to 16 hexadecimal digits")
        if any(char not in "0123456789abcdefABCDEF" for char in text):
            raise ValueError("universe address must be hexadecimal")
        try:
            number = int(text, 16)
        except ValueError as exc:
            raise ValueError("universe address must be hexadecimal") from exc
    else:
        raise ValueError("universe address must be an integer or hexadecimal string")
    if not 0 <= number <= U64_MASK:
        raise ValueError("universe address must fit in 64 bits")
    return number


def _signed_field(value: int, width: int) -> int:
    sign_bit = 1 << (width - 1)
    return value - (1 << width) if value & sign_bit else value


def _clamp_signed(value: int, minimum: int, maximum: int) -> int:
    return min(max(value, minimum), maximum)


def pack_universe_address_705(address: UniverseAddressInput) -> int:
    """Port ``FUN_140583A90`` over a canonical packed galaxy address.

    Field bits follow the serializer used by the Probe:
    X[0:12], Z[12:24], Y[24:32], reality[32:40], system[40:52],
    planet[52:56]. Native clamps signed X/Z to [-2047, 2047] and signed Y
    to [-127, 127], so the reserved minimum coordinate values (-2048/-128)
    normalize upward by one. The serialized planet/system/reality fields use
    4/12/8 bits respectively; bits 56..63 are dropped.
    """
    raw = _checked_address(address)

    x = _signed_field(raw & 0xFFF, 12)
    y = _signed_field((raw >> 24) & 0xFF, 8)
    z = _signed_field((raw >> 12) & 0xFFF, 12)
    x = _clamp_signed(x, -0x7FF, 0x7FF)
    y = _clamp_signed(y, -0x7F, 0x7F)
    z = _clamp_signed(z, -0x7FF, 0x7FF)

    # These masks isolate the serialized fields. Do not read a wider word and
    # clamp it: that would accidentally fold neighboring address fields in.
    planet = (raw >> 52) & 0xF
    system = (raw >> 40) & 0xFFF
    reality = (raw >> 32) & 0xFF

    low = (x & 0xFFF) | ((z & 0xFFF) << 12) | ((y & 0xFF) << 24)
    high = reality | (system << 8) | (planet << 20)
    return (high << 32) | low

