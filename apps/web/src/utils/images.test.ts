import { describe, expect, it } from 'vitest';
import { plantImageUrl } from './images';

describe('plantImageUrl', () => {
  it('returns null for empty input', () => {
    expect(plantImageUrl(null)).toBeNull();
    expect(plantImageUrl(undefined)).toBeNull();
    expect(plantImageUrl('')).toBeNull();
  });

  it('prefixes bare filenames with the plant_images directory', () => {
    expect(plantImageUrl('tomato.jpg')).toBe('/static/plant_images/tomato.jpg');
  });

  it('treats filenames with a slash as static-relative paths', () => {
    expect(plantImageUrl('plant_ai_images/1_tomato.png'))
      .toBe('/static/plant_ai_images/1_tomato.png');
  });
});
