/**
 * Build the correct static URL for a plant image filename.
 *
 * Legacy images (PlantLibrary.image_filename, PlantLibraryImage rows from
 * Wikimedia/iNaturalist) store bare filenames like "tomato.jpg" and live under
 * /static/plant_images/.
 *
 * AI-generated images store a subdirectory-prefixed filename like
 * "plant_ai_images/1_tomato.png" and live under /static/plant_ai_images/.
 *
 * If the filename already contains a "/" we treat it as a path relative to
 * /static/; otherwise we prepend /static/plant_images/.
 */
export function plantImageUrl(filename: string | null | undefined): string | null {
  if (!filename) return null;
  return filename.includes('/') ? `/static/${filename}` : `/static/plant_images/${filename}`;
}
