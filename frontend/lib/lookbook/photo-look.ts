// Mirrors MAX_IMAGE_BYTES in backend/app/services/image_service.py.
export const PHOTO_MAX_BYTES = 20 * 1024 * 1024;
export const PHOTO_MAX_MB = PHOTO_MAX_BYTES / (1024 * 1024);

export const PHOTO_ACCEPT = {
  'image/*': ['.jpeg', '.jpg', '.png', '.webp', '.heic', '.heif'],
};

export interface PhotoLookInput {
  photo: File;
  name: string;
  occasion: string;
  tags: string[];
  seasons: string[];
  weather_tags: string[];
}

// List values go out as repeated form fields, which is how the backend reads list[str] = Form().
export function buildPhotoLookFormData(input: PhotoLookInput): FormData {
  const data = new FormData();
  data.append('image', input.photo);
  data.append('name', input.name.trim());
  data.append('occasion', input.occasion);
  input.tags.forEach((tag) => data.append('tags', tag));
  input.seasons.forEach((season) => data.append('seasons', season));
  input.weather_tags.forEach((weather) => data.append('weather_tags', weather));
  return data;
}
