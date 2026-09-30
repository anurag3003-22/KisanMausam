import { describe, expect, it } from 'vitest';
import { distKm, nearest, searchState, statesForPoint } from './data';
import type { Manifest, Panchayat, StateIdx } from './types';

const mk = (name: string, code: string, lat: number, lng: number): Panchayat => ({
  code, name, block: 'B', district: 'D', state: 'S', stateSlug: 's', lat, lng, area: 1, blockLat: lat, blockLng: lng, codeSystem: 'LGD',
});
const all = [mk('Agra', '100', 22.8, 75.6), mk('Bagra', '101', 22.9, 75.7), mk('Sagar', '102', 23.5, 76.0), mk('Ajanda', '103', 22.7, 75.5)];
const idx = { all, lower: all.map((p) => p.name.toLowerCase()) } as unknown as StateIdx;

describe('searchState', () => {
  it('needs 2+ characters', () => expect(searchState(idx, 'a')).toEqual([]));
  it('ranks prefix matches before substring matches', () => {
    expect(searchState(idx, 'ag').map((p) => p.name)).toEqual(['Agra', 'Bagra', 'Sagar']);
  });
  it('is case-insensitive and trims', () => expect(searchState(idx, '  AJA ').map((p) => p.name)).toEqual(['Ajanda']));
  it('finds by LGD code prefix', () => expect(searchState(idx, '102').map((p) => p.name)).toEqual(['Sagar']));
  it('respects the limit', () => expect(searchState(idx, 'ag', 2)).toHaveLength(2));
});

describe('geo helpers', () => {
  it('distKm is ~111 km per degree of latitude', () => expect(distKm(20, 75, 21, 75)).toBeCloseTo(111.2, 0));
  it('nearest picks the closest point', () => expect(nearest(all, 22.71, 75.51)?.p.name).toBe('Ajanda'));
  it('nearest handles an empty list', () => expect(nearest([], 1, 1)).toBeNull());
  it('statesForPoint prefers states whose box contains the point', () => {
    const m = { states: [
      { slug: 'a', name: 'A', bbox: [70, 20, 75, 25] }, { slug: 'b', name: 'B', bbox: [76, 20, 80, 25] },
    ] } as unknown as Manifest;
    expect(statesForPoint(m, 22, 72).map((s) => s.slug)).toEqual(['a']);
    expect(statesForPoint(m, 22, 75.5)[0].slug).toBeDefined();
  });
});
