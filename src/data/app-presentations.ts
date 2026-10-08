import field from './presentations/field.ru.json';
import classifier from './presentations/classifier.en.json';
import petrography from './presentations/petrography.ru.json';

const presentations: Record<string, { key: string; slides: number; carousels?: boolean }> = {
  'rocksurv-field': { key: 'field', slides: field.slides.length },
  classifier: { key: 'classifier', slides: classifier.slides.length, carousels: true },
  'rocksurv-petrography': { key: 'petrography', slides: petrography.slides.length, carousels: true },
  'rocksurv-core': { key: 'core', slides: 14 },
};

export function appPresentation(slug: string) {
  const presentation = presentations[slug];
  if (!presentation) throw new Error(`Missing presentation for ${slug}`);
  return presentation;
}
