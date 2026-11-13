-- Remove only known stock replacements; keep cases and their source identifiers.
UPDATE cases SET image_url = NULL
WHERE image_url ~ '/(default_cover|ig_cover_comuna6|ig_cover_malecon|ig_cover_ceibas|ig_cover_salud)\.jpg([?].*)?$'
   OR image_url LIKE 'https://images.unsplash.com/%';

UPDATE meta_posts SET cover_image = NULL
WHERE cover_image ~ '/(default_cover|ig_cover_comuna6|ig_cover_malecon|ig_cover_ceibas|ig_cover_salud)\.jpg([?].*)?$'
   OR cover_image LIKE 'https://images.unsplash.com/%';
