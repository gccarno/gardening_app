import { describe, expect, it } from 'vitest';
import { centerSquare, toNchw } from './plantid';

describe('centerSquare', () => {
  it('crops the centred square of a landscape image', () => {
    expect(centerSquare(400, 300)).toEqual({ left: 50, top: 0, side: 300 });
  });

  it('crops the centred square of a portrait image, flooring odd margins', () => {
    // Matches Python's (width - side) // 2.
    expect(centerSquare(300, 401)).toEqual({ left: 0, top: 50, side: 300 });
  });
});

describe('toNchw', () => {
  it('splits RGBA pixels into planar RGB scaled to [0, 1], dropping alpha', () => {
    // 2x2 image: red, green, blue, white (alpha varies and must be ignored).
    const rgba = new Uint8ClampedArray([
      255, 0, 0, 255,   0, 255, 0, 128,
      0, 0, 255, 0,     255, 255, 255, 255,
    ]);
    const out = Array.from(toNchw(rgba, 2));
    expect(out).toEqual([
      1, 0, 0, 1,    // R plane
      0, 1, 0, 1,    // G plane
      0, 0, 1, 1,    // B plane
    ]);
  });
});
